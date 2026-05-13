# Real-Time Stock Scanner

An advanced Python-based stock market scanner designed to monitor:

- Premarket movers
- Regular market movers
- After-hours momentum
- SEC filings
- Real-time financial news
- Relative volume spikes
- Gap percentage movement
- Float rotation opportunities

Built using:

- Python
- Streamlit
- SQLite
- Finnhub API
- Financial Modeling Prep API
- Polygon API
- Telegram Bot API
- Discord Webhooks

---

# Features

## Real-Time Market Monitoring

Scans:
- Premarket
- Regular trading hours
- After-hours trading

Tracks:
- Momentum stocks
- Gap-up movers
- Volume spikes
- Low-float runners
- News catalysts
- SEC filings

---

# Alert System

Supports:
- Discord alerts
- Telegram alerts
- Local dashboard alerts

Alert types:
- PREMARKET_MOVER
- REGULAR_MOVER
- AFTERHOURS_MOVER
- NEWS
- SEC

---

# Dashboard

Built with Streamlit.

Displays:
- Latest alerts
- Highest momentum scores
- Premarket movers
- News catalysts
- SEC filing alerts
- Bearish dilution warnings

---

# Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core scanner engine |
| Streamlit | Dashboard UI |
| SQLite | Alert database |
| Finnhub API | Market/news data |
| FMP API | Market movers |
| Polygon API | Extended-hours market data |
| Telegram API | Mobile alerts |
| Discord Webhooks | Alert notifications |

---

# Installation

## Clone Repository

```bash
git clone https://github.com/YOUR_USERNAME/Stock-Scanner.git
cd Stock-Scanner
```

---

## Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Variables

Create a `.env` file:

```env
POLYGON_API_KEY=YOUR_KEY
FINNHUB_API_KEY=YOUR_KEY
FMP_API_KEY=YOUR_KEY

SEC_USER_AGENT=StockScanner/1.0 your_email@gmail.com

DISCORD_WEBHOOK_URL=YOUR_WEBHOOK

TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
```

---

# Run Scanner

```bash
python scanner3.py
```

---

# Run Dashboard

```bash
streamlit run dashboard3.py
```

---

# Future Improvements

Planned upgrades:
- AI sentiment analysis
- NLP news scoring
- Insider trading tracking
- Options flow tracking
- Dark pool monitoring
- Machine learning momentum ranking
- Multi-timeframe technical analysis
- Mobile app integration

---

# Educational Purpose

This project was built for:
- Python automation practice
- API integration learning
- Financial data analysis
- Cybersecurity/Linux environment development
- Real-time alert system design

---

# Author

Charles Pearson
Cybersecurity Student | Python Automation | Linux & Security Labs
