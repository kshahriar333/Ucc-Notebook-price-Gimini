import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

from src.config import HEADERS, URLS, CACHE_TTL_SECONDS
from src.spec_parser import parse_laptop_specs, LaptopSpecs

logger = logging.getLogger(__name__)

_CACHE: Dict[str, object] = {
    "timestamp": 0.0,
    "data": None,
}


def parse_price_value(price_text: str) -> Optional[int]:
    """Extracts integer BDT price from text. Returns None if Out of Stock / TBA / Call."""
    if not price_text:
        return None
    lower = price_text.lower()
    if any(k in lower for k in ["out of stock", "upcoming", "tba", "call", "discontinued"]):
        return None

    # Find numbers like 65,000 or 125000
    matches = re.findall(r"\d[\d,]{3,}", price_text)
    if not matches:
        return None

    # Usually the first or lowest active price is the selling price
    values = []
    for m in matches:
        num = int(m.replace(",", ""))
        if 15000 <= num <= 1000000:  # Valid laptop price range in BDT
            values.append(num)

    return values[0] if values else None


def format_bdt(amount: Optional[int]) -> str:
    if amount is None:
        return "Out of Stock / TBA"
    return f"৳{amount:,}"


def _build_product(store: str, name: str, price_text: str, url: str) -> dict:
    price_num = parse_price_value(price_text)
    specs: LaptopSpecs = parse_laptop_specs(name)
    return {
        "store": store,
        "name": name.strip(),
        "price_num": price_num,
        "price_str": format_bdt(price_num),
        "url": url.strip(),
        "specs": specs,
    }


def scrape_ucc() -> List[dict]:
    products = []
    try:
        res = requests.get(URLS["UCC"], headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")

        items = soup.select(".product-layout, .product-thumb")
        for item in items:
            name_tag = item.select_one(".name a, h4 a, .caption a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if "acer" not in name.lower():
                continue

            price_tag = item.select_one(".price-new, .price")
            price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
            url = name_tag.get("href", "")
            products.append(_build_product("UCC", name, price_text, url))
    except Exception as exc:
        logger.error("Failed scraping UCC: %s", exc)
    return products


def scrape_startech() -> List[dict]:
    products = []
    try:
        res = requests.get(URLS["StarTech"], headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")

        for item in soup.select(".p-item"):
            name_tag = item.select_one(".p-item-name a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            price_tag = item.select_one(".p-item-price span, .p-item-price")
            price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
            url = name_tag.get("href", "")
            products.append(_build_product("StarTech", name, price_text, url))
    except Exception as exc:
        logger.error("Failed scraping StarTech: %s", exc)
    return products


def scrape_ryans() -> List[dict]:
    products = []
    try:
        res = requests.get(URLS["Ryans"], headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")

        for item in soup.select(".category-single-product, .product-home-card"):
            name_tag = item.select_one(".card-title a, .product-title-grid a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            price_tag = item.select_one(".pr-text, .price")
            price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
            url = name_tag.get("href", "")
            products.append(_build_product("Ryans", name, price_text, url))
    except Exception as exc:
        logger.error("Failed scraping Ryans: %s", exc)
    return products


def scrape_techland() -> List[dict]:
    products = []
    try:
        res = requests.get(URLS["Techland"], headers=HEADERS, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "lxml")

        for item in soup.select(".product-layout, .product-thumb"):
            name_tag = item.select_one(".name a, h4 a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            price_tag = item.select_one(".price-new, .price")
            price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
            url = name_tag.get("href", "")
            products.append(_build_product("Techland", name, price_text, url))
    except Exception as exc:
        logger.error("Failed scraping Techland: %s", exc)
    return products


def fetch_all_stores(force_refresh: bool = False) -> Dict[str, List[dict]]:
    """Fetches products from all 4 stores concurrently with in-memory TTL caching."""
    now = time.time()
    if (
        not force_refresh
        and _CACHE["data"] is not None
        and (now - float(_CACHE["timestamp"])) < CACHE_TTL_SECONDS
    ):
        return _CACHE["data"]  # type: ignore

    scrapers = {
        "UCC": scrape_ucc,
        "StarTech": scrape_startech,
        "Ryans": scrape_ryans,
        "Techland": scrape_techland,
    }

    results: Dict[str, List[dict]] = {k: [] for k in scrapers}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(fn): name for name, fn in scrapers.items()}
        for future in as_completed(future_map):
            store_name = future_map[future]
            try:
                results[store_name] = future.result()
            except Exception as exc:
                logger.error("Error in worker %s: %s", store_name, exc)

    _CACHE["timestamp"] = now
    _CACHE["data"] = results
    return results
