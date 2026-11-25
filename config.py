import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "900"))
MIN_MATCH_SCORE = int(os.getenv("MIN_MATCH_SCORE", "72"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

URLS = {
    "UCC": "https://www.ucc.com.bd/acer-brand-laptops?limit=100",
    "StarTech": "https://www.startech.com.bd/acer-laptop?limit=100",
    "Ryans": "https://www.ryans.com/category/all-laptop-acer?limit=100",
    "Techland": "https://www.techlandbd.com/shop-laptop-computer/brand-laptops/shop-acer-laptop?limit=100",
}
