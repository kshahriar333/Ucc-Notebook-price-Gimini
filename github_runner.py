import os
import sys
import glob
import asyncio

# রিপোজিটরির যেকোনো ফোল্ডারে scraper.py থাকলে তা অটোমেটিক খুঁজে বের করে path-এ যুক্ত করবে
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

for found_file in glob.glob(os.path.join(base_dir, "**", "scraper.py"), recursive=True):
    folder_path = os.path.dirname(found_file)
    if folder_path not in sys.path:
        sys.path.insert(0, folder_path)

from telegram import Bot
import scraper
import matcher
import bot as bot_module

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_QUERY = os.getenv("SEARCH_QUERY", "").strip() or None
ONLY_MATCHED = os.getenv("ONLY_MATCHED", "false").lower() == "true"


async def send_report():
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN এবং TELEGRAM_CHAT_ID সেট করা আবশ্যক!")

    tg_bot = Bot(token=BOT_TOKEN)
    data = scraper.fetch_all_stores(force_refresh=True)
    comparisons = matcher.compare_acer_catalog(
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
            bot_module.format_comparison_card(c) for c in chunk
        )
        await tg_bot.send_message(
            chat_id=CHAT_ID,
            text=body,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )


if __name__ == "__main__":
    asyncio.run(send_report())
