import time
import threading
import requests
from flask import Flask, jsonify
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

# ================== CONFIG ==================
BOT_TOKEN = "YOUR_NEW_BOT_TOKEN"
LOG_CHANNEL_ID = "@your_log_channel"
API_BASE = "https://socialdown.itz-ashlynn.workers.dev"

# ================== FLASK APP ==================
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "telegram-downloader-bot"
    }), 200


def run_flask():
    app.run(host="0.0.0.0", port=10000)


# ================== RATE LIMIT ==================
USER_COOLDOWN = {}
COOLDOWN_SECONDS = 5


def is_rate_limited(user_id):
    now = time.time()
    last = USER_COOLDOWN.get(user_id, 0)
    if now - last < COOLDOWN_SECONDS:
        return True
    USER_COOLDOWN[user_id] = now
    return False


# ================== HELPERS ==================
def detect_platform(url: str):
    url = url.lower()
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "instagram.com" in url:
        return "instagram"
    if "x.com" in url or "twitter.com" in url:
        return "x"
    if "pinterest.com" in url:
        return "pinterest"
    return None


def call_api(endpoint, params):
    r = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=30)
    return r.json()


# ================== LOGGING ==================
async def log_event(context, user, platform, url):
    try:
        name = user.first_name or "User"
        username = f"@{user.username}" if user.username else "no username"
        profile = f"tg://user?id={user.id}"

        text = (
            "📥 New Download Request\n\n"
            f"👤 User: {name} ({username})\n"
            f"🔗 Profile: {profile}\n\n"
            f"📦 Platform: {platform.capitalize()}\n"
            f"🔍 Link:\n{url}"
        )

        await context.bot.send_message(
            chat_id=LOG_CHANNEL_ID,
            text=text,
            disable_web_page_preview=True
        )
    except Exception as e:
        print("[LOG ERROR]", e)


# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi 👋\n\n"
        "Send me a link from YouTube, Instagram, X (Twitter), or Pinterest.\n\n"
        "I’ll fetch the best available download for you."
    )


# ================== MESSAGE HANDLER ==================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()

    if is_rate_limited(user.id):
        await update.message.reply_text(
            "You’re doing that a bit too fast.\nPlease try again in a few seconds."
        )
        return

    platform = detect_platform(url)
    if not platform:
        return

    await log_event(context, user, platform, url)

    msg = await update.message.reply_text("Fetching media…")

    if platform == "youtube":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🎵 MP3", callback_data=f"yt|mp3|{url}"),
                InlineKeyboardButton("🎬 MP4", callback_data=f"yt|mp4|{url}")
            ]
        ])
        await msg.edit_text(
            "🎬 YouTube content found\n\nChoose format:",
            reply_markup=keyboard
        )
        return


# ================== CALLBACK HANDLER ==================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, fmt, url = query.data.split("|")

    if action == "yt":
        res = call_api("/yt", {"url": url, "format": fmt})
        item = res["data"][0]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬇️ Download", url=item["downloadUrl"])]
        ])

        await query.message.edit_text(
            f"Your download is ready\n\n"
            f"Format: {item['format'].upper()}\n"
            f"Size: {item['fileSize']}",
            reply_markup=keyboard
        )


# ================== BOT RUNNER ==================
def run_bot():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))

    application.run_polling()


# ================== MAIN ==================
if __name__ == "__main__":
    # Flask in background
    threading.Thread(target=run_flask).start()

    # Telegram bot
    run_bot()
