import os

import tempfile

import shutil

import logging

import sqlite3

import subprocess

from dotenv import load_dotenv

from pathlib import Path

from yt_dlp import YoutubeDL

from telegram import (

    Update,

    InlineKeyboardButton,

    InlineKeyboardMarkup

)

from telegram.ext import (

    ApplicationBuilder,

    CommandHandler,

    MessageHandler,

    CallbackQueryHandler,

    ContextTypes,

    filters

)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS").split(",")}   # Telegram Admin ID

DB_FILE = "users.db"

TEMP_PREFIX = "media_bot_"

MAX_VIDEO_MB = 50

MAX_AUDIO_MB = 20

logging.basicConfig(

    format="%(asctime)s | %(levelname)s | %(message)s",

    level=logging.INFO

)

logger = logging.getLogger(__name__)

# ================= DATABASE =================

def init_db():

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("""

        CREATE TABLE IF NOT EXISTS users (

            user_id INTEGER PRIMARY KEY,

            username TEXT,

            first_name TEXT

        )

    """)

    conn.commit()

    conn.close()

def save_user(user_id: int, username: str, first_name: str):

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("""

        INSERT INTO users (user_id, username, first_name) 

        VALUES (?, ?, ?)

        ON CONFLICT(user_id) DO UPDATE SET 

            username=excluded.username,

            first_name=excluded.first_name

    """, (user_id, username, first_name))

    conn.commit()

    conn.close()

def get_all_users():

    conn = sqlite3.connect(DB_FILE)

    cur = conn.cursor()

    cur.execute("SELECT user_id, username, first_name FROM users")

    users = cur.fetchall()

    conn.close()

    return users

# ================= UTILS =================

def is_admin(update: Update) -> bool:

    return update.effective_user.id in ADMIN_IDS

def human_mb(size: int) -> str:

    return f"{size / (1024 * 1024):.2f} MB"

def compress_video(inp, out):

    try:

        subprocess.run(

            ["ffmpeg", "-y", "-i", inp,

             "-vcodec", "libx264", "-crf", "28",

             "-acodec", "aac", "-b:a", "128k", out],

            check=True,

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL

        )

        return out

    except:

        return inp

def compress_audio(inp, out):

    try:

        subprocess.run(

            ["ffmpeg", "-y", "-i", inp,

             "-vn", "-b:a", "128k", out],

            check=True,

            stdout=subprocess.DEVNULL,

            stderr=subprocess.DEVNULL

        )

        return inp

    except:

        return inp

# ================= YTDLP =================

def ytdl_opts(fmt):

    return {

        "format": fmt,

        "quiet": True,

        "noplaylist": True,

        "merge_output_format": "mp4",

    }

def download_media(url, tmpdir, fmt):

    opts = ytdl_opts(fmt)

    opts["outtmpl"] = os.path.join(tmpdir, "%(id)s.%(ext)s")

    try:

        with YoutubeDL(opts) as ydl:

            info = ydl.extract_info(url, download=True)

            title = info.get("title", "NoTitle")

    except:

        return None, None

    files = list(Path(tmpdir).glob("*"))

    if not files:

        return None, None

    file_path = str(max(files, key=lambda f: f.stat().st_size))

    return file_path, title

# ================= HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    save_user(

        update.effective_user.id,

        update.effective_user.username or "NoUsername",

        update.effective_user.first_name or "NoName"

    )

    start_text = (

        "👋 សួស្តី!\n\n"

        "🤖 *PT Bot* អាចទាញយក:\n"

        "• YouTube (MP3 / MP4)\n"

        "• TikTok (MP4)\n"

        "• Facebook (MP4)\n"

        "• Instagram (MP4)\n\n"

        "📌 ផ្ញើ link មកដើម្បី Download\n\n"

        "Bot made by @PTmcplay"

    )

    help_button = InlineKeyboardMarkup([

        [InlineKeyboardButton("💡 ជំនួយ / Help", callback_data="help")]

    ])

    await update.message.reply_text(

        start_text,

        parse_mode="Markdown",

        reply_markup=help_button

    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    save_user(

        update.effective_user.id,

        update.effective_user.username or "NoUsername",

        update.effective_user.first_name or "NoName"

    )

    help_text = (

        "📚 *របៀបប្រើ Bot*\n\n"

        "1️⃣ ផ្ញើ link YouTube / TikTok / Facebook / Instagram\n"

        "2️⃣ ជ្រើសរើស MP4 / MP3 (YouTube MP3/MP4)\n"

        "3️⃣ Bot នឹងទាញយក និងបង្ហាញទំហំ\n\n"

        "✅ YouTube MP3/MP4\n"

        "✅ TikTok, Facebook, Instagram MP4 only\n\n"

        "Bot by PT"

    )

    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    save_user(

        update.effective_user.id,

        update.effective_user.username or "NoUsername",

        update.effective_user.first_name or "NoName"

    )

    url = update.message.text.strip()

    tmpdir = tempfile.mkdtemp(prefix=TEMP_PREFIX)

    preparing_msg = await update.message.reply_text("⏳ កំពុងត្រួតពិនិត្យ link...")

    try:

        # YouTube menu

        if "youtube.com" in url or "youtu.be" in url:

            try:

                await preparing_msg.delete()

            except:

                pass

            keyboard = [[

                InlineKeyboardButton("🎬 MP4 វីដេអូ", callback_data=f"yt|mp4|{url}"),

                InlineKeyboardButton("🎵 MP3 សំឡេង", callback_data=f"yt|mp3|{url}")

            ]]

            await update.message.reply_text(

                "📌 សូមជ្រើសរើសទ្រង់ទ្រាយ YouTube:",

                reply_markup=InlineKeyboardMarkup(keyboard)

            )

            return

        # TikTok / Facebook / Instagram

        if any(x in url for x in ["tiktok.com", "facebook.com", "fb.watch", "instagram.com", "reel"]):

            try:

                await preparing_msg.edit_text("⏳ កំពុងទាញយក…")

            except:

                pass

            file_path, title = download_media(url, tmpdir, "best")

            if not file_path:

                await preparing_msg.edit_text("❌ មិនអាចទាញយកបាន")

                return

            # Compress if too large

            size = os.path.getsize(file_path)

            if size > MAX_VIDEO_MB * 1024 * 1024:

                file_path = compress_video(file_path, os.path.join(tmpdir, f"{title}.mp4"))

            size_mb = human_mb(os.path.getsize(file_path))

            await preparing_msg.edit_text(f"✅ រួចរាល់ ({size_mb})")

            with open(file_path, "rb") as f:

                await update.message.reply_video(f, filename=f"{title}.mp4")

            return

        # Unsupported link

        await preparing_msg.edit_text("❌ Link មិនគាំទ្រ")

    finally:

        shutil.rmtree(tmpdir, ignore_errors=True)

        try:

            await preparing_msg.delete()

        except:

            pass

async def button_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):

    q = update.callback_query

    await q.answer()

    save_user(

        q.from_user.id,

        q.from_user.username or "NoUsername",

        q.from_user.first_name or "NoName"

    )

    data = q.data

    # Help button

    if data == "help":

        help_text = (

            "📚 *របៀបប្រើ Bot*\n\n"

            "1️⃣ ផ្ញើ link YouTube / TikTok / Facebook / Instagram\n"

            "2️⃣ ជ្រើសរើស MP4 / MP3\n"

            "3️⃣ Bot នឹងទាញយក និងបង្ហាញទំហំ\n\n"

            "✅ YouTube MP3/MP4\n"

            "✅ TikTok, Facebook, Instagram MP4 only\n"

        )

        await q.message.reply_text(help_text, parse_mode="Markdown")

        return

    # YouTube buttons

    if "|" in data:

        try:

            site, typ, url = data.split("|", 2)

        except ValueError:

            await q.message.reply_text("❌ Error: invalid callback data")

            return

        # Delete only old YouTube menu

        try:

            await q.message.delete()

        except:

            pass

        tmpdir = tempfile.mkdtemp(prefix=TEMP_PREFIX)

        msg = await q.message.reply_text("⏳ កំពុងទាញយក…")

        try:

            fmt = "bestvideo+bestaudio/best" if typ == "mp4" else "bestaudio/best"

            file_path, title = download_media(url, tmpdir, fmt)

            if not file_path:

                await msg.edit_text("❌ ទាញយកបរាជ័យ")

                return

            # Compress if too large

            size = os.path.getsize(file_path)

            if typ == "mp4" and size > MAX_VIDEO_MB * 1024 * 1024:

                file_path = compress_video(file_path, os.path.join(tmpdir, f"{title}.mp4"))

            if typ == "mp3" and size > MAX_AUDIO_MB * 1024 * 1024:

                file_path = compress_audio(file_path, os.path.join(tmpdir, f"{title}.mp3"))

            size_mb = human_mb(os.path.getsize(file_path))

            await msg.edit_text(f"✅ រួចរាល់ ({size_mb})")

            with open(file_path, "rb") as f:

                if typ == "mp4":

                    await q.message.reply_video(f, filename=f"{title}.mp4")

                else:

                    await q.message.reply_audio(f, filename=f"{title}.mp3")

        finally:

            shutil.rmtree(tmpdir, ignore_errors=True)

# ================= ADMIN =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update):

        await update.message.reply_text("❌ អ្នកមិនមែនជា Admin ទេ")

        return

    users = get_all_users()

    text = f"📊 *ស្ថិតិ Bot*\n\n👥 ចំនួនអ្នកប្រើ: {len(users)}\n\n"

    for u_id, uname, fname in users:

        text += f"• {fname} (@{uname}) — `{u_id}`\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not is_admin(update):

        await update.message.reply_text("❌ អ្នកមិនមែនជា Admin ទេ")

        return

    if not context.args:

        await update.message.reply_text("📣 ប្រើ:\n/broadcast សាររបស់អ្នក")

        return

    text = " ".join(context.args)

    users = get_all_users()

    sent = 0

    for u_id, uname, fname in users:

        try:

            await context.bot.send_message(u_id, text)

            sent += 1

        except:

            pass

    await update.message.reply_text(f"✅ ផ្ញើបាន {sent} នាក់")

# ================= MAIN =================

def main():

    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    # Commands

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(CommandHandler("stats", stats))

    app.add_handler(CommandHandler("broadcast", broadcast))

    # Callback buttons

    app.add_handler(CallbackQueryHandler(button_cb, pattern=".*"))

    # Message handler

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    logger.info("BOT STARTED")

    app.run_polling()

if __name__ == "__main__":

    main()