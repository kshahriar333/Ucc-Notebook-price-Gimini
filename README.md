# Acer Laptop Price Tracker & Comparator Bot (BD)

A modular Python Telegram Bot that scrapes live **Acer Laptop** listings from **UCC** (official distributor) and compares their prices side-by-side with **Star Tech**, **Ryans Computers**, and **Techland BD** using strict hardware specification matching (**SKU / Model Code, CPU, RAM, SSD, and GPU**).

---

## Features

- **Spec-Aware Accurate Matching (`src/spec_parser.py` & `src/matcher.py`):**
  - Extracts exact **Acer SKU / Part Numbers** (e.g., `A315-59-562P`, `ANV15-51-532J`, `NX.K6TSI.002`).
  - Parses **Processor** (`i5-1235U`, `i5-13420H`, `Ultra 7 155H`, `Ryzen 5 7520U`), **RAM** (`8GB`, `16GB`, `32GB`), **SSD** (`256GB`, `512GB`, `1TB`), and **GPU** (`RTX 3050`, `RTX 4050`).
  - **Zero False Positives:** Automatically rejects mismatched configurations (e.g., an `8GB/512GB` model will never match a `16GB/512GB` or `8GB/1TB` variant).
- **Concurrent Scraping + TTL Caching (`src/scraper.py`):**
  - Fetches all 4 websites simultaneously via `ThreadPoolExecutor` and caches results for 15 minutes (`CACHE_TTL_SECONDS`) for instant responses.
- **Lowest Price Highlighter (`src/bot.py`):**
  - Automatically identifies the cheapest store (`🏆 Lowest`) with clickable product links.

---

## Project Structure

```text
acer-laptop-price-tracker-bot/
├── src/
│   ├── __init__.py
│   ├── config.py        # Environment & URL configurations
│   ├── spec_parser.py   # Regex extractor for SKU, CPU, RAM, SSD, GPU
│   ├── scraper.py       # Concurrent scrapers for UCC, StarTech, Ryans, Techland
│   ├── matcher.py       # Spec-validated scoring & comparison engine
│   └── bot.py           # Telegram bot command handlers
├── tests/
│   └── test_matcher.py  # Unit tests for spec extraction & matching accuracy
├── main.py              # Entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/acer-laptop-price-tracker-bot.git
   cd acer-laptop-price-tracker-bot
   ```

2. **Create virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Telegram Bot Token:**
   - Message `@BotFather` on Telegram and run `/newbot` to get your API token.
   - Copy `.env.example` to `.env` and add your token:
     ```bash
     cp .env.example .env
     ```
     Edit `.env`:
     ```env
     TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
     ```

4. **Run Unit Tests (Optional):**
   ```bash
   python -m unittest discover tests
   ```

5. **Start the Bot:**
   ```bash
   python main.py
   ```

---

## Telegram Commands

| Command | Description |
| :--- | :--- |
| `/start` | Show welcome message and available commands |
| `/all` | Compare all UCC Acer laptops against Star Tech, Ryans & Techland |
| `/matched` | Show only UCC models that have matching listings in at least one other store |
| `/search <query>` | Filter by model name, SKU, or spec (e.g., `/search Nitro 16GB`, `/search A315-59`) |
| `/refresh` | Bypass cache and fetch fresh live prices from all 4 websites |
