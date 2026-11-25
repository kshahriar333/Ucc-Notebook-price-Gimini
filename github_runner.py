import os
import sys
import glob
import html
import types
import importlib.util
import asyncio

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

# মেমোরিতে 'src' প্যাকেজ তৈরি করে প্রয়োজনীয় মডিউলগুলো অটোমেটিক লোড করা হচ্ছে
src_pkg = types.ModuleType("src")
src_pkg.__path__ = []
sys.modules["src"] = src_pkg

for py_file in glob.glob(os.path.join(base_dir, "**", "*.py"), recursive=True):
    mod_name = os.path.splitext(os.path.basename(py_file))[0]
    if mod_name in {"config", "spec_parser", "scraper", "matcher"}:
        full_mod_name = f"src.{mod_name}"
        spec = importlib.util.spec_from_file_location(full_mod_name, py_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_mod_name] = module
            setattr(src_pkg, mod_name, module)

for mod_name in ["config", "spec_parser", "scraper", "matcher"]:
    full_mod_name = f"src.{mod_name}"
    if full_mod_name in sys.modules:
        mod = sys.modules[full_mod_name]
        mod.__spec__.loader.exec_module(mod)

from telegram import Bot
from src.scraper import fetch_all_stores
from src.matcher import compare_acer_catalog

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "").strip() or None
ONLY_MATCHED = os.getenv("ONLY_MATCHED", "false").lower() == "true"


def _format_specs_badge(specs) -> str:
    parts = []
    if specs.sku:
        parts.append(f"SKU: {specs.sku}")
    if specs.cpu_model:
        parts.append(specs.cpu_model)
    if specs.ram_gb:
        parts.append(f"{specs.ram_gb}GB RAM")
    if specs.ssd_gb:
        ssd_label = f"{specs.ssd_gb // 1024}TB" if specs.ssd_gb >= 1024 else f"{specs.ssd_gb}GB"
        parts.append(f"{ssd_label} SSD")
    if specs.gpu:
        parts.append(specs.gpu)
    return " | ".join(parts) if parts else "Specs detected from title"


def _format_store_line(prefix: str, store_label: str, item: dict | None, is_lowest: bool) -> str:
    if not item:
        return f"{prefix} <b>{store_label}:</b> <i>Not Listed</i>"
    price = html.escape(item["price_str"])
    crown = " 🏆 <b>(Lowest)</b>" if is_lowest else ""
    url = item.get("url", "")
    link = f'<a href="{html.escape(url)}">{price}</a>' if url else price
    return f"{prefix} <b>{store_label}:</b> {link}{crown}"


def format_comparison_card(comp: dict) -> str:
    ucc = comp["ucc"]
    specs = ucc["specs"]
    lowest_store = comp["lowest_store"]

    title = html.escape(ucc["name"])
    ucc_url = ucc.get("url", "")
    title_html = f'<a href="{html.escape(ucc_url)}"><b>{title}</b></a>' if ucc_url else f"<b>{title}</b>"
    badge = html.escape(_format_specs_badge(specs))

    lines = [
        f"💻 {title_html}",
        f"⚙️ <code>{badge}</code>",
        _format_store_line("├", "UCC", ucc, lowest_store == "UCC"),
        _format_store_line("├", "Star Tech", comp["StarTech"], lowest_store == "StarTech"),
        _format_store_line("├", "Ryans", comp["Ryans"], lowest_store == "Ryans"),
        _format_store_line("└", "Techland", comp["Techland"], lowest_store == "Techland"),
    ]
    return "\n".join(lines)


async def send_report():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN এবং TELEGRAM_CHAT_ID সেট করা আবশ্যক!")

    tg_bot = Bot(token=BOT_TOKEN)
    data = fetch_all_stores(force_refresh=True)
    comparisons = compare_acer_catalog(
        data, query=SEARCH_QUERY, only_matched=ONLY_MATCHED
    )

    if not comparisons:
        await tg_bot.send_message(
            chat_id=CHAT_ID,
            text="❌ কোনো ম্যাচিং Acer ল্যাপটপ পাওয়া যায়নি।",
        )
        return

    header = (
        f"📊 <b>Acer Laptop Price Report (UCC vs Others)</b>\n"
        f"✅ মোট <b>{len(comparisons)}</b>টি মডেল পাওয়া গেছে "
        f"(UCC: {len(data['UCC'])}, StarTech: {len(data['StarTech'])}, "
        f"Ryans: {len(data['Ryans'])}, Techland: {len(data['Techland'])})\n"
    )
    await tg_bot.send_message(chat_id=CHAT_ID, text=header, parse_mode="HTML")

    chunk_size = 5
    for idx in range(0, len(comparisons), chunk_size):
        chunk = comparisons[idx : idx + chunk_size]
        body = "\n\n────────────────────\n\n".join(
            format_comparison_card(c) for c in chunk
        )
        await tg_bot.send_message(
            chat_id=CHAT_ID,
            text=body,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


if __name__ == "__main__":
    asyncio.run(send_report())
