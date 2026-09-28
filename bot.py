import os
import re
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ARU_YT_API = os.getenv("ARU_YT_API", "https://aru.up.railway.app").rstrip("/")
ARU_API_KEY = os.getenv("ARU_API_KEY")
ARU_ENDPOINT = os.getenv("ARU_ENDPOINT", "/download")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in .env")

if not ARU_API_KEY:
    raise RuntimeError("ARU_API_KEY missing in .env")


bot = Bot(BOT_TOKEN)
dp = Dispatcher()

youtube_regex = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=[\w-]+|youtu\.be/[\w-]+|"
    r"youtube\.com/shorts/[\w-]+)",
    re.IGNORECASE
)


def main_buttons():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎬 Video",
                    callback_data="download_video"
                ),
                InlineKeyboardButton(
                    text="🎵 Music",
                    callback_data="download_audio"
                )
            ]
        ]
    )


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "👋 <b>YouTube Downloader</b>\n\n"
        "🎬 YouTube Video → MP4\n"
        "🎵 YouTube Music → Audio\n\n"
        "YouTube link bhejo:",
        parse_mode="HTML"
    )


@dp.message(F.text)
async def receive_url(message: Message):
    url = message.text.strip()

    if not youtube_regex.search(url):
        await message.answer(
            "❌ Valid YouTube URL bhejo.\n\n"
            "Example:\n"
            "https://youtube.com/watch?v=..."
        )
        return

    # URL ko temporarily message ke saath store karne ke liye
    # callback_data mein URL directly nahi bhej sakte.
    # Isliye bot message ID ko callback data mein use karenge.
    await message.answer(
        "Link received ✅\n\n"
        "Kya download karna hai?",
        reply_markup=main_buttons()
    )

    # Simple in-memory storage
    URLS[message.chat.id] = url


URLS = {}


@dp.callback_query(F.data.in_({"download_video", "download_audio"}))
async def download_callback(callback: CallbackQuery):

    chat_id = callback.message.chat.id
    url = URLS.get(chat_id)

    if not url:
        await callback.answer("❌ Pehle YouTube link bhejo.", show_alert=True)
        return

    download_type = (
        "video"
        if callback.data == "download_video"
        else "audio"
    )

    await callback.answer()

    status = await callback.message.edit_text(
        "⏳ <b>Processing...</b>\n\n"
        "YouTube media prepare ho raha hai.",
        parse_mode="HTML"
    )

    try:
        result = await call_aru_api(url, download_type)

        if not result["success"]:
            await status.edit_text(
                "❌ <b>Download failed</b>\n\n"
                f"{result['error']}",
                parse_mode="HTML"
            )
            return

        download_url = result["url"]
        title = result.get("title", "YouTube Download")

        await status.edit_text(
            "✅ <b>Ready!</b>\n\n"
            f"🎵/🎬 {escape_html(title)}\n\n"
            "📥 Sending file...",
            parse_mode="HTML"
        )

        # Telegram URL se directly file bhejne ki koshish
        if download_type == "audio":
            await bot.send_audio(
                chat_id=chat_id,
                audio=download_url,
                caption=f"🎵 {title}"
            )
        else:
            await bot.send_video(
                chat_id=chat_id,
                video=download_url,
                caption=f"🎬 {title}"
            )

        await status.delete()

    except Exception as e:
        await status.edit_text(
            "❌ <b>Error</b>\n\n"
            f"{escape_html(str(e))}",
            parse_mode="HTML"
        )


async def call_aru_api(url: str, media_type: str):

    endpoint = f"{ARU_YT_API}{ARU_ENDPOINT}"

    headers = {
        "X-API-Key": ARU_API_KEY,
        "Authorization": f"Bearer {ARU_API_KEY}",
        "Accept": "application/json"
    }

    params = {
        "url": url,
        "type": media_type
    }

    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async with session.get(
            endpoint,
            params=params,
            headers=headers
        ) as response:

            raw = await response.text()

            try:
                data = await response.json()
            except Exception:
                return {
                    "success": False,
                    "error": f"Invalid API response: {raw[:500]}"
                }

            if response.status != 200:
                return {
                    "success": False,
                    "error": str(
                        data.get("error")
                        or data.get("message")
                        or data
                    )
                }

            # Different common API response formats
            download_url = (
                data.get("download_url")
                or data.get("downloadUrl")
                or data.get("url")
                or data.get("download")
            )

            title = (
                data.get("title")
                or data.get("name")
                or "YouTube Download"
            )

            if not download_url:

                # Nested response support
                result = data.get("result")

                if isinstance(result, dict):
                    download_url = (
                        result.get("download_url")
                        or result.get("url")
                        or result.get("download")
                    )

                    title = (
                        result.get("title")
                        or title
                    )

            if not download_url:
                return {
                    "success": False,
                    "error": f"Download URL nahi mila: {data}"
                }

            return {
                "success": True,
                "url": download_url,
                "title": title
            }


def escape_html(text):
    text = str(text)
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


async def main():
    print("================================")
    print(" YouTube Downloader Bot Started")
    print("================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
