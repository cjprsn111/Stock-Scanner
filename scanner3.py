import os
import re
import time
import json
import sqlite3
import requests
import feedparser
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

FINNHUB = os.getenv("FINNHUB_API_KEY")
FMP = os.getenv("FMP_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "StockScanner contact@example.com")
DISCORD = os.getenv("DISCORD_WEBHOOK_URL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")

SCAN_INTERVAL = 60
SEC_SCAN_EVERY_CYCLES = 10
MAX_SEC_COMPANIES = 300

seen = set()

NEWS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US",
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
]

KEYWORDS = {
    "VERY_BULLISH": [
        "fda approval", "approval", "merger", "acquisition", "buyout",
        "contract", "partnership", "phase 3", "positive results",
        "strategic agreement", "breakthrough", "patent", "record revenue"
    ],
    "BULLISH": [
        "upgrade", "guidance raise", "launches", "collaboration",
        "expands", "new order", "earnings beat"
    ],
    "BEARISH": [
        "offering", "registered direct", "private placement", "dilution",
        "reverse split", "bankruptcy", "delisting", "nasdaq deficiency",
        "sec investigation", "earnings miss"
    ],
}


def setup_db():
    conn = sqlite3.connect("scanner_results.db")
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            symbol TEXT,
            alert_type TEXT,
            session TEXT,
            score INTEGER,
            price REAL,
            gap_percent REAL,
            volume REAL,
            rel_volume REAL,
            float_shares REAL,
            headline TEXT,
            keywords TEXT,
            url TEXT
        )
    """)

    conn.commit()
    conn.close()


def save_alert(data):
    conn = sqlite3.connect("scanner_results.db")
    c = conn.cursor()

    c.execute("""
        INSERT INTO alerts
        (time, symbol, alert_type, session, score, price, gap_percent, volume,
         rel_volume, float_shares, headline, keywords, url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        data.get("symbol"),
        data.get("alert_type"),
        data.get("session"),
        data.get("score"),
        data.get("price"),
        data.get("gap_percent"),
        data.get("volume"),
        data.get("rel_volume"),
        data.get("float_shares"),
        data.get("headline"),
        json.dumps(data.get("keywords", [])),
        data.get("url"),
    ))

    conn.commit()
    conn.close()


def send_message(message):
    print(message)

    if DISCORD:
        try:
            requests.post(DISCORD, json={"content": message}, timeout=10)
        except Exception as e:
            print(f"Discord error: {e}")

    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(
                url,
                data={"chat_id": TELEGRAM_CHAT, "text": message},
                timeout=10
            )
        except Exception as e:
            print(f"Telegram error: {e}")


def detect_session():
    now = datetime.now().time()

    premarket_start = datetime.strptime("04:00", "%H:%M").time()
    regular_start = datetime.strptime("09:30", "%H:%M").time()
    regular_end = datetime.strptime("16:00", "%H:%M").time()
    afterhours_end = datetime.strptime("20:00", "%H:%M").time()

    if premarket_start <= now < regular_start:
        return "PREMARKET"

    if regular_start <= now < regular_end:
        return "REGULAR"

    if regular_end <= now < afterhours_end:
        return "AFTERHOURS"

    return "CLOSED"


def alert_type_for_session(session):
    if session == "PREMARKET":
        return "PREMARKET_MOVER"

    if session == "REGULAR":
        return "REGULAR_MOVER"

    if session == "AFTERHOURS":
        return "AFTERHOURS_MOVER"

    return None


def fmp_get(endpoint, params=None):
    if not FMP:
        return None

    params = params or {}
    params["apikey"] = FMP

    url = f"https://financialmodelingprep.com/stable/{endpoint}"

    try:
        r = requests.get(url, params=params, timeout=15)

        if r.status_code != 200:
            print(f"FMP error {endpoint}: HTTP {r.status_code}")
            return None

        if not r.text.strip():
            print(f"FMP error {endpoint}: empty response")
            return None

        return r.json()

    except Exception as e:
        print(f"FMP error {endpoint}: {e}")
        return None


def finnhub_get(endpoint, params=None):
    if not FINNHUB:
        return None

    params = params or {}
    params["token"] = FINNHUB

    try:
        r = requests.get(
            f"https://finnhub.io/api/v1/{endpoint}",
            params=params,
            timeout=15
        )

        if r.status_code != 200:
            print(f"Finnhub error {endpoint}: HTTP {r.status_code}")
            return None

        return r.json()

    except Exception as e:
        print(f"Finnhub error {endpoint}: {e}")
        return None


def extract_tickers(text):
    patterns = [
        r"\$([A-Z]{1,5})",
        r"\(([A-Z]{1,5})\)",
        r"NASDAQ:\s?([A-Z]{1,5})",
        r"NYSE:\s?([A-Z]{1,5})",
        r"AMEX:\s?([A-Z]{1,5})",
    ]

    blacklist = {
        "CEO", "CFO", "COO", "SEC", "FDA", "USA", "IPO", "ETF", "EPS",
        "THE", "AND", "FOR", "ARE", "INC", "LLC", "NEW", "AI"
    }

    found = set()

    for pattern in patterns:
        found.update(re.findall(pattern, text))

    return [x for x in found if x not in blacklist]


def score_text(text):
    text = text.lower()
    score = 0
    hits = []

    for group, words in KEYWORDS.items():
        for word in words:
            if word in text:
                hits.append(word)

                if group == "VERY_BULLISH":
                    score += 7
                elif group == "BULLISH":
                    score += 3
                elif group == "BEARISH":
                    score -= 10

    return score, hits


def get_finnhub_quote(symbol):
    data = finnhub_get("quote", {"symbol": symbol})

    if not isinstance(data, dict):
        return {}

    price = data.get("c")
    prev = data.get("pc")

    gap = 0

    if price and prev:
        gap = round(((price - prev) / prev) * 100, 2)

    return {
        "price": price,
        "previous_close": prev,
        "gap_percent": gap,
        "open": data.get("o"),
        "high": data.get("h"),
        "low": data.get("l"),
    }


def get_fmp_quote(symbol):
    data = fmp_get("quote-short", {"symbol": symbol})

    if isinstance(data, list) and data:
        row = data[0]

        return {
            "price": row.get("price"),
            "volume": row.get("volume"),
        }

    return {}


def get_float(symbol):
    data = fmp_get("shares-float", {"symbol": symbol})

    if isinstance(data, list) and data:
        return data[0].get("floatShares") or data[0].get("freeFloat")

    if isinstance(data, dict):
        return data.get("floatShares") or data.get("freeFloat")

    return None


def get_extended_hours_movers():
    """
    This is the important fix.

    It tries the FMP pre/post market endpoint.
    If unavailable, it returns [] instead of falling back to biggest gainers.

    This prevents fake CLOSED_MOVER alerts.
    """

    data = fmp_get("pre-post-market")

    if isinstance(data, list) and data:
        return data

    print("Premarket/after-hours endpoint unavailable. No fallback used.")
    return []


def get_regular_market_movers():
    data = fmp_get("biggest-gainers")

    if isinstance(data, list):
        return data[:100]

    return []


def calculate_relative_volume(symbol, current_volume):
    if not current_volume:
        return None

    profile = fmp_get("profile", {"symbol": symbol})

    avg_volume = None

    if isinstance(profile, list) and profile:
        avg_volume = profile[0].get("volAvg") or profile[0].get("avgVolume")

    if not avg_volume:
        return None

    try:
        return round(float(current_volume) / float(avg_volume), 2)
    except Exception:
        return None


def professional_score(symbol, base_score=0, keywords=None):
    keywords = keywords or []

    quote = get_finnhub_quote(symbol)
    fmp_quote = get_fmp_quote(symbol)

    price = quote.get("price") or fmp_quote.get("price")
    volume = fmp_quote.get("volume")
    gap = quote.get("gap_percent", 0)

    float_shares = get_float(symbol)
    rel_volume = calculate_relative_volume(symbol, volume)

    score = base_score

    try:
        price_float = float(price) if price is not None else None
    except Exception:
        price_float = None

    try:
        gap_float = float(gap) if gap is not None else 0
    except Exception:
        gap_float = 0

    try:
        volume_float = float(volume) if volume is not None else 0
    except Exception:
        volume_float = 0

    if price_float and 0.50 <= price_float <= 20:
        score += 5

    if price_float and 0.05 <= price_float < 0.50:
        score += 2

    if gap_float >= 10:
        score += 5

    if gap_float >= 25:
        score += 8

    if gap_float >= 50:
        score += 10

    if volume_float >= 250_000:
        score += 3

    if volume_float >= 1_000_000:
        score += 5

    if volume_float >= 5_000_000:
        score += 8

    if float_shares:
        try:
            fs = float(float_shares)

            if fs <= 50_000_000:
                score += 3

            if fs <= 20_000_000:
                score += 5

            if fs <= 10_000_000:
                score += 6

            if fs <= 5_000_000:
                score += 8

        except Exception:
            pass

    if rel_volume:
        if rel_volume >= 3:
            score += 4

        if rel_volume >= 5:
            score += 6

        if rel_volume >= 10:
            score += 8

    bearish_terms = [
        "offering",
        "registered direct",
        "private placement",
        "dilution",
        "reverse split",
    ]

    if any(term in keywords for term in bearish_terms):
        score -= 15

    if any(term in keywords for term in ["fda approval", "merger", "acquisition", "buyout"]):
        score += 10

    return {
        "symbol": symbol,
        "score": score,
        "price": price,
        "gap_percent": gap,
        "volume": volume,
        "rel_volume": rel_volume,
        "float_shares": float_shares,
    }


def fire_alert(data):
    save_alert(data)

    msg = f"""
🚨 STOCK SCANNER ALERT

Type: {data.get("alert_type")}
Session: {data.get("session")}
Ticker: {data.get("symbol")}
Score: {data.get("score")}
Price: {data.get("price")}
Gap %: {data.get("gap_percent")}
Volume: {data.get("volume")}
Relative Volume: {data.get("rel_volume")}
Float: {data.get("float_shares")}

Headline:
{data.get("headline")}

Keywords:
{", ".join(data.get("keywords", []))}

URL:
{data.get("url")}
"""

    send_message(msg)


def scan_movers():
    session = detect_session()
    alert_type = alert_type_for_session(session)

    if session == "CLOSED":
        print("Market is closed. Skipping mover scan. News and SEC still scan.")
        return []

    if session in ["PREMARKET", "AFTERHOURS"]:
        movers = get_extended_hours_movers()
    else:
        movers = get_regular_market_movers()

    symbols_for_news = []

    for item in movers:
        symbol = item.get("symbol") or item.get("ticker")

        if not symbol:
            continue

        symbols_for_news.append(symbol)

        key = f"{alert_type}-{symbol}-{date.today()}"

        if key in seen:
            continue

        price = item.get("price") or item.get("lastSalePrice")
        volume = item.get("volume")

        raw_change = (
            item.get("changesPercentage")
            or item.get("changePercentage")
            or item.get("changesPercent")
            or item.get("percent")
            or 0
        )

        try:
            change_percent = float(str(raw_change).replace("%", ""))
        except Exception:
            change_percent = 0

        data = professional_score(symbol, base_score=5, keywords=["mover"])

        if price:
            data["price"] = price

        if volume:
            data["volume"] = volume

        if change_percent:
            data["gap_percent"] = change_percent

            if change_percent >= 10:
                data["score"] += 5

            if change_percent >= 25:
                data["score"] += 8

            if change_percent >= 50:
                data["score"] += 10

        if data["score"] >= 15:
            seen.add(key)

            data.update({
                "alert_type": alert_type,
                "session": session,
                "headline": f"{symbol} moving during {session}",
                "keywords": [session.lower(), "momentum", "mover"],
                "url": "FMP mover feed",
            })

            fire_alert(data)

    return symbols_for_news


def scan_news_rss():
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                url = entry.link

                if url in seen:
                    continue

                seen.add(url)

                headline = entry.title
                summary = getattr(entry, "summary", "")
                text = f"{headline} {summary}"

                tickers = extract_tickers(text)
                base_score, keywords = score_text(text)

                if not tickers or not keywords:
                    continue

                for symbol in tickers:
                    data = professional_score(symbol, base_score, keywords)

                    if abs(data["score"]) >= 10:
                        data.update({
                            "alert_type": "NEWS",
                            "session": detect_session(),
                            "headline": headline,
                            "keywords": keywords,
                            "url": url,
                        })

                        fire_alert(data)

        except Exception as e:
            print(f"RSS news error: {e}")


def scan_finnhub_company_news(symbols):
    today = date.today()
    yesterday = today - timedelta(days=1)

    for symbol in symbols[:50]:
        try:
            news = finnhub_get("company-news", {
                "symbol": symbol,
                "from": str(yesterday),
                "to": str(today),
            })

            if not isinstance(news, list):
                continue

            for article in news[:5]:
                url = article.get("url")
                headline = article.get("headline", "")
                summary = article.get("summary", "")

                if not url or url in seen:
                    continue

                seen.add(url)

                text = f"{headline} {summary}"
                base_score, keywords = score_text(text)

                if not keywords:
                    continue

                data = professional_score(symbol, base_score, keywords)

                if abs(data["score"]) >= 10:
                    data.update({
                        "alert_type": "NEWS",
                        "session": detect_session(),
                        "headline": headline,
                        "keywords": keywords,
                        "url": url,
                    })

                    fire_alert(data)

        except Exception as e:
            print(f"Company news error for {symbol}: {e}")


def scan_sec_filings():
    headers = {"User-Agent": SEC_USER_AGENT}

    try:
        ticker_map = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=headers,
            timeout=15
        ).json()

        checked = 0

        for _, item in ticker_map.items():
            symbol = item["ticker"]
            cik = str(item["cik_str"]).zfill(10)

            checked += 1

            if checked > MAX_SEC_COMPANIES:
                break

            r = requests.get(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers=headers,
                timeout=15
            )

            data = r.json()
            recent = data.get("filings", {}).get("recent", {})

            forms = recent.get("form", [])
            accessions = recent.get("accessionNumber", [])
            dates = recent.get("filingDate", [])

            for form, acc, filing_date in zip(forms[:5], accessions[:5], dates[:5]):
                if form not in ["8-K", "S-1", "S-3", "424B5", "SC 13G", "SC 13D"]:
                    continue

                key = f"SEC-{symbol}-{form}-{acc}"

                if key in seen:
                    continue

                seen.add(key)

                base = 4
                keywords = [form]

                if form in ["S-1", "S-3", "424B5"]:
                    base -= 10
                    keywords.append("dilution risk")

                if form == "8-K":
                    base += 5
                    keywords.append("material event")

                result = professional_score(symbol, base, keywords)

                if abs(result["score"]) >= 8:
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/"

                    result.update({
                        "alert_type": "SEC",
                        "session": detect_session(),
                        "headline": f"{symbol} filed {form} on {filing_date}",
                        "keywords": keywords,
                        "url": filing_url,
                    })

                    fire_alert(result)

            time.sleep(0.12)

    except Exception as e:
        print(f"SEC scan error: {e}")


def run():
    setup_db()

    print("Better-fix stock scanner started.")
    print("Only valid alert types will be saved:")
    print("PREMARKET_MOVER, REGULAR_MOVER, AFTERHOURS_MOVER, NEWS, SEC")
    print("No CLOSED_MOVER alerts will be created.\n")

    cycle = 0

    while True:
        session = detect_session()

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Session: {session}")

        mover_symbols = scan_movers()
        scan_news_rss()

        if mover_symbols:
            scan_finnhub_company_news(mover_symbols)

        if cycle % SEC_SCAN_EVERY_CYCLES == 0:
            scan_sec_filings()

        cycle += 1
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    run()
