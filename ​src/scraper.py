import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional
import cloudscraper
from bs4 import BeautifulSoup

from src.config import HEADERS, CACHE_TTL_SECONDS
from src.spec_parser import parse_laptop_specs, LaptopSpecs

logger = logging.getLogger(__name__)

_CACHE: Dict[str, object] = {"timestamp": 0.0, "data": None}


def _get_html(url: str) -> str:
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    res = scraper.get(url, headers=HEADERS, timeout=30)
    res.raise_for_status()
    return res.text


def parse_price_value(price_text: str) -> Optional[int]:
    if not price_text:
        return None
    lower = price_text.lower()
    if any(k in lower for k in ["out of stock", "upcoming", "tba", "call", "discontinued"]):
        return None

    matches = re.findall(r"\d[\d,]{3,}", price_text)
    values = []
    for m in matches:
        num = int(m.replace(",", ""))
        if 15000 <= num <= 1000000:
            values.append(num)
    return values[0] if values else None


def format_bdt(amount: Optional[int]) -> str:
    return f"৳{amount:,}" if amount is not None else "Out of Stock / TBA"


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


def _deduplicate(products: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for p in products:
        key = p["url"] or p["name"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def scrape_ucc() -> List[dict]:
    products = []
    for page in range(1, 6):
        url = f"https://www.ucc.com.bd/acer-brand-laptops?limit=100&page={page}"
        try:
            soup = BeautifulSoup(_get_html(url), "lxml")
            items = soup.select(".product-layout, .product-thumb")
            if not items:
                break
            before_count = len(products)
            for item in items:
                name_tag = item.select_one(".name a, h4 a, .caption a")
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                if "acer" not in name.lower():
                    continue
                price_tag = item.select_one(".price-new, .price")
                price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                products.append(_build_product("UCC", name, price_text, name_tag.get("href", "")))
            products = _deduplicate(products)
            if len(products) == before_count:
                break
        except Exception as exc:
            logger.error("Failed scraping UCC page %s: %s", page, exc)
            break
    return products


def scrape_startech() -> List[dict]:
    products = []
    for page in range(1, 6):
        url = f"https://www.startech.com.bd/acer-laptop?limit=90&page={page}"
        try:
            soup = BeautifulSoup(_get_html(url), "lxml")
            items = soup.select(".p-item")
            if not items:
                break
            before_count = len(products)
            for item in items:
                name_tag = item.select_one(".p-item-name a")
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                if "acer" not in name.lower():
                    continue
                price_tag = item.select_one(".p-item-price span, .p-item-price")
                price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                products.append(_build_product("StarTech", name, price_text, name_tag.get("href", "")))
            products = _deduplicate(products)
            if len(products) == before_count:
                break
        except Exception as exc:
            logger.error("Failed scraping StarTech page %s: %s", page, exc)
            break
    return products


def scrape_ryans() -> List[dict]:
    products = []
    urls_to_try = [
        "https://www.ryans.com/category/all-laptop-acer?limit=100&page={page}",
        "https://www.ryans.com/category/laptop-all-laptop?limit=100&brand=acer&page={page}",
    ]
    for base_url in urls_to_try:
        for page in range(1, 6):
            url = base_url.format(page=page)
            try:
                soup = BeautifulSoup(_get_html(url), "lxml")
                items = soup.select(".category-single-product, .product-home-card, .card-body")
                if not items:
                    break
                before_count = len(products)
                for item in items:
                    name_tag = item.select_one(".card-title a, .product-title-grid a, a.product-title")
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)
                    if "acer" not in name.lower():
                        continue
                    price_tag = item.select_one(".pr-text, .price, .tk")
                    price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                    href = name_tag.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.ryans.com" + href
                    products.append(_build_product("Ryans", name, price_text, href))
                products = _deduplicate(products)
                if len(products) == before_count:
                    break
            except Exception as exc:
                logger.error("Failed scraping Ryans page %s: %s", page, exc)
                break
        if products:
            break
    return products


def scrape_techland() -> List[dict]:
    products = []
    urls_to_try = [
        "https://www.techlandbd.com/shop-laptop-computer/brand-laptops/shop-acer-laptop?limit=100&page={page}",
        "https://www.techlandbd.com/acer-laptop?limit=100&page={page}",
    ]
    for base_url in urls_to_try:
        for page in range(1, 6):
            url = base_url.format(page=page)
            try:
                soup = BeautifulSoup(_get_html(url), "lxml")
                items = soup.select(".product-layout, .product-thumb, .product-grid, .single-product")
                if not items:
                    break
                before_count = len(products)
                for item in items:
                    name_tag = item.select_one(".name a, h4 a, .product-title a, a[href*='acer']")
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)
                    if "acer" not in name.lower() or len(name) < 10:
                        continue
                    price_tag = item.select_one(".price-new, .price, .special-price")
                    price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                    href = name_tag.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.techlandbd.com" + href
                    products.append(_build_product("Techland", name, price_text, href))
                products = _deduplicate(products)
                if len(products) == before_count:
                    break
            except Exception as exc:
                logger.error("Failed scraping Techland page %s: %s", page, exc)
                break
        if products:
            break
    return products


def fetch_all_stores(force_refresh: bool = False) -> Dict[str, List[dict]]:
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
