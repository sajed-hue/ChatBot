import pandas as pd
from telegram import Update
from telegram.ext import MessageHandler, CommandHandler, ApplicationBuilder, ContextTypes, filters
import os

Token = os.getenv("TELEGRAM_BOT_TOKEN")
if not Token:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

Sheet_ID = "1eX0HjdZKYD9TvvavRWzL1uQ0sCFv_u_X-38vNholUeA"

def load_links():
    url = f"https://docs.google.com/spreadsheets/d/{Sheet_ID}/export?format=csv"
    try:
        df = pd.read_csv(url)
        if df.empty or 'keywords' not in df.columns or 'link' not in df.columns:
            return pd.DataFrame(columns=['keywords', 'link'])
        return df
    except Exception as e:
        print(f"Error loading Google Sheet: {e}")
        return pd.DataFrame(columns=['keywords', 'link'])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحبًا! البوت جاهز للاستخدام ")

async def replay_with_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text.lower().strip()
    df = load_links()
    
    if df.empty:
        await update.message.reply_text("عذرًا، لا توجد روابط متاحة حاليًا.")
        return

    found = False
    for _, row in df.iterrows():
        if pd.isna(row['keywords']) or pd.isna(row['link']):
            continue    
        keywords = [k.strip().lower() for k in str(row['keywords']).split(',')]
        for keyword in keywords:
            if keyword in user_message:
                await update.message.reply_text(f"Link: {row['link']}")
                found = True
                break
        if found:
            break

    if not found:
        await update.message.reply_text("عذرًا، لم أجد أي رابط لهذا الطلب.")


app = ApplicationBuilder().token(Token).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), replay_with_link))

if __name__ == "__main__":
    app.run_polling()
