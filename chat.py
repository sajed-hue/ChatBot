import os
import threading
import pandas as pd
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

SHEET_ID = "1eX0HjdZKYD9TvvavRWzL1uQ0sCFv_u_X-38vNholUeA"

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive!"


def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)




cache_links = {}
last_update = 0
CACHE_TIME = 28805   # 8 houres


def load_links():

    global cache_links, last_update

    if cache_links and time.time() - last_update < CACHE_TIME:
        return cache_links

    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(url)

        links_dict = {}

        for _, row in df.iterrows():

            if pd.isna(row["keywords"]) or pd.isna(row["link"]):
                continue

            keywords = str(row["keywords"]).lower().split(",")

            for keyword in keywords:
                links_dict[keyword.strip()] = row["link"]

        cache_links = links_dict
        last_update = time.time()

    except Exception as e:
        print("Sheet error:", e)
        cache_links = {}

    return cache_links




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("البوت شغال 🔥")


async def replay_with_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text.lower().strip()

    links = load_links()

    best_match = ""
    best_link = ""

    for keyword, link in links.items():

        if keyword in user_message and len(keyword) > len(best_match):
            best_match = keyword
            best_link = link

    if best_link:
        await update.message.reply_text(best_link)
    else:
        await update.message.reply_text("عذرًا، لم أجد أي رابط لهذا الطلب.")




app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), replay_with_link))


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run_polling()
