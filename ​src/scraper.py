import re
import json
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
        if 20000 <= num <= 1000000:
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


def _is_laptop_title(name: str) -> bool:
    low = name.lower()
    if "acer" not in low or len(name) < 15:
        return False
    # মনিটর, প্রজেক্টর, ব্যাগ বা চার্জার বাদ দেওয়ার ফিল্টার
    exclude = ["monitor", "projector", "bag", "backpack", "adapter", "charger", "mouse", "keyboard", "desktop", "all in one", "all-in-one"]
    if any(ex in low for ex in exclude):
        return False
    # ল্যাপটপ সিরিজ বা স্পেক কিওয়ার্ড চেক
    include = ["laptop", "notebook", "aspire", "nitro", "predator", "swift", "extensa", "travelmate", "chromebook", "spin", "ryzen", "core", "celeron", "ssd", "ram"]
    return any(inc in low for inc in include)


def scrape_ucc() -> List[dict]:
    products = []
    base_urls = [
        "https://www.ucc.com.bd/acer-brand-laptops?limit=100&page={page}",
        "https://www.ucc.com.bd/laptop?limit=100&page={page}",
    ]
    for base_url in base_urls:
        for page in range(1, 5):
            try:
                soup = BeautifulSoup(_get_html(base_url.format(page=page)), "lxml")
                items = soup.select(".product-layout, .product-thumb")
                if not items:
                    break
                before = len(products)
                for item in items:
                    name_tag = item.select_one(".name a, h4 a, .caption a")
                    if not name_tag:
                        continue
                    name = name_tag.get_text(strip=True)
                    if not _is_laptop_title(name):
                        continue
                    price_tag = item.select_one(".price-new, .price")
                    price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                    products.append(_build_product("UCC", name, price_text, name_tag.get("href", "")))
                products = _deduplicate(products)
                if len(products) == before:
                    break
            except Exception as exc:
                logger.error("UCC error page %s: %s", page, exc)
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
            before = len(products)
            for item in items:
                name_tag = item.select_one(".p-item-name a")
                if not name_tag:
                    continue
                name = name_tag.get_text(strip=True)
                if not _is_laptop_title(name):
                    continue
                price_tag = item.select_one(".p-item-price span, .p-item-price")
                price_text = price_tag.get_text(" ", strip=True) if price_tag else ""
                products.append(_build_product("StarTech", name, price_text, name_tag.get("href", "")))
            products = _deduplicate(products)
            if len(products) == before:
                break
        except Exception as exc:
            logger.error("StarTech error page %s: %s", page, exc)
            break
    return products


def scrape_ryans() -> List[dict]:
    products = []
    base_urls = [
        "https://www.ryans.com/brand/acer?page={page}",
        "https://www.ryans.com/category/all-laptop-acer?page={page}",
    ]
    for base_url in base_urls:
        for page in range(1, 8):
            try:
                soup = BeautifulSoup(_get_html(base_url.format(page=page)), "lxml")
                before = len(products)

                # ১. কার্ড সিলেক্টর দিয়ে খোঁজা
                cards = soup.select(".category-single-product, .product-home-card, .card")
                for card in cards:
                    a_tag = card.select_one("a[href*='ryans.com/'], a[href^='/']")
                    if not a_tag:
                        continue
                    # কার্ডের ভেতরে সবচেয়ে লম্বা টেক্সট বা title নেওয়া
                    title_el = card.select_one(".card-title a, .product-title-grid a, h4 a, h5 a") or a_tag
                    name = title_el.get_text(" ", strip=True)
                    if not _is_laptop_title(name):
                        continue
                    price_el = card.select_one(".pr-text, .price, [class*='price']")
                    price_text = price_el.get_text(" ", strip=True) if price_el else card.get_text(" ", strip=True)
                    href = title_el.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.ryans.com" + href
                    products.append(_build_product("Ryans", name, price_text, href))

                # ২. ফলব্যাক: সরাসরি প্রোডাক্ট লিংক স্ক্যান করা
                if len(products) == before:
                    for a_tag in soup.select("a[href]"):
                        name = a_tag.get_text(" ", strip=True)
                        if not _is_laptop_title(name):
                            continue
                        parent = a_tag.find_parent(["div", "li", "article"])
                        price_text = parent.get_text(" ", strip=True) if parent else ""
                        href = a_tag.get("href", "")
                        if href.startswith("/"):
                            href = "https://www.ryans.com" + href
                        products.append(_build_product("Ryans", name, price_text, href))

                products = _deduplicate(products)
                if len(products) == before:
                    break
            except Exception as exc:
                logger.error("Ryans error page %s: %s", page, exc)
                break
        if products:
            break
    return products


def scrape_techland() -> List[dict]:
    products = []
    urls = [
        "https://www.techlandbd.com/shop-laptop-computer/brand-laptops/shop-acer-laptop",
        "https://www.techlandbd.com/acer-aspire-laptop",
        "https://www.techlandbd.com/acer-ryzen-laptop",
        "https://www.techlandbd.com/acer-intel-laptop",
        "https://www.techlandbd.com/acer-swift-laptop",
    ]
    for url in urls:
        try:
            html_text = _get_html(url)
            soup = BeautifulSoup(html_text, "lxml")

            # ১. HTML কার্ড এবং লিংক থেকে খোঁজা
            for a_tag in soup.select("a[href]"):
                name = a_tag.get_text(" ", strip=True)
                if not _is_laptop_title(name):
                    continue
                parent = a_tag.find_parent(["div", "li", "article"])
                price_text = parent.get_text(" ", strip=True) if parent else ""
                href = a_tag.get("href", "")
                if href.startswith("/"):
                    href = "https://www.techlandbd.com" + href
                products.append(_build_product("Techland", name, price_text, href))

            # ২. Next.js JSON (__NEXT_DATA__) থেকে খোঁজা
            next_script = soup.find("script", id="__NEXT_DATA__")
            if next_script and next_script.string:
                raw_json = next_script.string
                for m in re.finditer(r'"name"\s*:\s*"([^"]*Acer[^"]*)"', raw_json, re.IGNORECASE):
                    title = m.group(1)
                    if not _is_laptop_title(title):
                        continue
                    window = raw_json[m.start(): m.start() + 600]
                    price_m = re.search(r'"(?:price|special_price|sale_price)"\s*:\s*"?(\d{5,6})"?', window)
                    slug_m = re.search(r'"slug"\s*:\s*"([^"]+)"', window)
                    p_str = price_m.group(1) if price_m else ""
                    p_url = f"https://www.techlandbd.com/{slug_m.group(1)}" if slug_m else url
                    products.append(_build_product("Techland", title, p_str, p_url))

        except Exception as exc:
            logger.error("Techland error %s: %s", url, exc)

    return _deduplicate(products)


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
