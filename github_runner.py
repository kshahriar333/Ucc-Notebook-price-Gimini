import os
import sys
import asyncio

# বর্তমান ফোল্ডারকে Python Path-এ যুক্ত করা হচ্ছে যাতে src মডিউল সহজেই পাওয়া যায়
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Bot
from src.scraper import fetch_all_stores
from src.matcher import compare_acer_catalog
from src.bot import format_comparison_card

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "").strip() or None
ONLY_MATCHED = os.getenv("ONLY_MATCHED", "false").lower() == "true"


async def send_report():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN এবং TELEGRAM_CHAT_ID সেট করা আবশ্যক!")

    bot = Bot(token=BOT_TOKEN)
    data = fetch_all_stores(force_refresh=True)
    comparisons = compare_acer_catalog(
        data, query=SEARCH_QUERY, only_matched=ONLY_MATCHED
    )

    if not comparisons:
        await bot.send_message(
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
    await bot.send_message(chat_id=CHAT_ID, text=header, parse_mode="HTML")

    chunk_size = 5
    for idx in range(0, len(comparisons), chunk_size):
        chunk = comparisons[idx : idx + chunk_size]
        body = "\n\n────────────────────\n\n".join(
            format_comparison_card(c) for c in chunk
        )
        await bot.send_message(
            chat_id=CHAT_ID,
            text=body,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


if __name__ == "__main__":
    asyncio.run(send_report())
