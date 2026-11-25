import logging
import html
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import TELEGRAM_BOT_TOKEN
from src.scraper import fetch_all_stores, format_bdt
from src.matcher import compare_acer_catalog

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
    return "
".join(lines)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "👋 <b>Acer Laptop Price Comparator (BD)</b>

"
        "UCC-এর প্রতিটি Acer ল্যাপটপের <b>SKU, Processor, RAM ও SSD</b> মিলিয়ে "
        "<b>Star Tech, Ryans এবং Techland</b>-এর দামের সাথে তুলনা করুন:

"
        "📌 <b>কমান্ডসমূহ:</b>
"
        "• /all — UCC-এর সব Acer ল্যাপটপের তুলনামূলক দাম
"
        "• /matched — শুধু যেগুলো অন্য সাইটেও পাওয়া গেছে
"
        "• /search <code>&lt;model/spec&gt;</code> — নির্দিষ্ট মডেল খুঁজুন (যেমন: <code>/search Nitro 16GB</code> বা <code>/search A315-59</code>)
"
        "• /refresh — ক্যাশ ক্লিয়ার করে লাইভ ডাটা আনুন"
    )
    await update.message.reply_text(msg, parse_mode="HTML", disable_web_page_preview=True)


async def _send_results(
    update: Update,
    query: str | None = None,
    only_matched: bool = False,
    force_refresh: bool = False,
) -> None:
    status_msg = await update.message.reply_text(
        "⏳ UCC, Star Tech, Ryans এবং Techland থেকে Acer ল্যাপটপের ডাটা মিলিয়ে দেখা হচ্ছে..."
    )

    data = fetch_all_stores(force_refresh=force_refresh)
    comparisons = compare_acer_catalog(data, query=query, only_matched=only_matched)

    if not comparisons:
        await status_msg.edit_text("❌ দুঃখিত, আপনার সার্চ অনুযায়ী কোনো Acer ল্যাপটপ পাওয়া যায়নি।")
        return

    summary = (
        f"✅ মোট <b>{len(comparisons)}</b>টি Acer ল্যাপটপ পাওয়া গেছে "
        f"(UCC: {len(data['UCC'])}, StarTech: {len(data['StarTech'])}, "
        f"Ryans: {len(data['Ryans'])}, Techland: {len(data['Techland'])})
"
    )
    await status_msg.edit_text(summary, parse_mode="HTML")

    # Send in chunks of 5 cards per Telegram message to respect 4096 char limit
    chunk_size = 5
    for idx in range(0, len(comparisons), chunk_size):
        chunk = comparisons[idx : idx + chunk_size]
        body = "

────────────────────

".join(format_comparison_card(c) for c in chunk)
        await update.message.reply_text(
            body,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


async def all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_results(update, query=None, only_matched=False)


async def matched_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_results(update, query=None, only_matched=True)


async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "⚠️ মডেলের নাম বা স্পেসিফিকেশন লিখুন। যেমন:
"
            "<code>/search Aspire 5 16GB</code> বা <code>/search ANV15-51</code>",
            parse_mode="HTML",
        )
        return
    await _send_results(update, query=query, only_matched=False)


async def refresh_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_results(update, query=None, only_matched=False, force_refresh=True)


def run_bot() -> None:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing! Set it in your .env file before running."
        )

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", start_cmd))
    app.add_handler(CommandHandler("all", all_cmd))
    app.add_handler(CommandHandler("matched", matched_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("refresh", refresh_cmd))

    logger.info("Acer Price Comparator Telegram Bot started polling...")
    app.run_polling()


if __name__ == "__main__":
    run_bot()
