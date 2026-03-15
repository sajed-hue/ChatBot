import os
import threading
import pandas as pd
import time
from difflib import SequenceMatcher
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
CACHE_TIME = 28000  # 8h

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


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
        print("Error loading sheet:", e)
        cache_links = {}

    return cache_links




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً \n"
        "أنا Mubtaker Bot\n"
        "اكتب اسم المادة كما في البورتال بالانجيزيه وسأعطيك الرابط المناسب."
    )


async def replay_with_link(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_message = update.message.text.lower().strip()

    links = load_links()

    best_score = 0
    best_link = ""

    words = user_message.split()

    for keyword, link in links.items():

        for word in words:

            score = similarity(word, keyword)

            if score > best_score:
                best_score = score
                best_link = link

    if best_score > 0.4:
        await update.message.reply_text(best_link)
    else:
        await update.message.reply_text(
            "لم أجد رابط مناسب \n"
            "حاول كتابة كلمة مختلفة."
        )




app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), replay_with_link))


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run_polling()
