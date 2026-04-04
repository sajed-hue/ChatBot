import os
import re
import time
import threading
import pandas as pd
from difflib import SequenceMatcher
from flask import Flask
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN not set")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 🚀"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

try:
    from google import genai
except:
    genai = None

gemini_client = None
if genai and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except:
        gemini_client = None

SHEET_ID = "1eX0HjdZKYD9TvvavRWzL1uQ0sCFv_u_X-38vNholUeA"
CACHE_TIME = 60 * 60 * 8

cache_links = {}
last_update = 0

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def normalize(text):
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text)

def load_links():
    global cache_links, last_update

    if cache_links and time.time() - last_update < CACHE_TIME:
        return cache_links

    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(url)

        links = {}

        for _, row in df.iterrows():
            if pd.isna(row["keywords"]) or pd.isna(row["link"]):
                continue

            keywords = str(row["keywords"]).split(",")

            for k in keywords:
                k = normalize(k)
                if k:
                    links[k] = row["link"]

        cache_links = links
        last_update = time.time()

    except Exception as e:
        print("Sheet error:", e)
        cache_links = {}

    return cache_links

# --------------------------------------------------
# Find link
# --------------------------------------------------
def find_link(msg, links):
    msg = normalize(msg)

    best_score = 0
    best_link = ""

    for keyword, link in links.items():
        score = similarity(msg, keyword)

        if keyword in msg:
            score = max(score, 0.95)

        if score > best_score:
            best_score = score
            best_link = link

    return best_score, best_link

def ask_ai(message):
    if not gemini_client:
        return "⚠️ AI غير مفعل حالياً.\nاكتب اسم المادة بشكل أوضح."

    prompt = f"""
أنت مساعد جامعي.
أجب بالعربية بشكل مختصر.

السؤال:
{message}
"""

    try:
        res = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return res.text.strip()
    except:
        return "⚠️ حدث خطأ في الذكاء الاصطناعي"

def generate_reply(message):
    links = load_links()

    score, link = find_link(message, links)

    if score > 0.6:
        return link

    return ask_ai(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 أهلاً\n"
        "أنا Mubtaker Bot\n\n"
        "اكتب اسم المادة  "
    )

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text.strip()
    reply = generate_reply(msg)
    await update.message.reply_text(reply)

telegram_app = ApplicationBuilder().token(TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    telegram_app.run_polling()
