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

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

SHEET_ID = "1eX0HjdZKYD9TvvavRWzL1uQ0sCFv_u_X-38vNholUeA"
CACHE_TIME = 60 * 60 * 8  # 8 hours
GEMINI_MODEL = "gemini-2.5-flash"

try:
    from google import genai
except Exception:
    genai = None

gemini_client = None
if genai is not None and GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        gemini_client = None

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

cache_links = {}
last_update = 0


STUDY_PLAN_PROMPT = """
أنت مساعد أكاديمي عربي مخصص لطلاب قسم علم الحاسوب في الجامعة العربية الأمريكية.

مهمتك:
1) مساعدة الطالب في فهم الخطة الدراسية.
2) الإجابة عن الأسئلة المتعلقة بالمواد، ترتيبها، عدد الساعات، والفصل المناسب.
3) اقتراح جدول دراسي بشكل عام بناءً على الخطة فقط.
4) إذا لم تكن معلومات الطالب كافية، اطلب منه توضيح المواد التي أنهاها أو عدد الساعات التي يريد تسجيلها.
5) لا تخترع معلومات غير موجودة في الخطة.
6) لا تذكر مواد ليست في الخطة.
7) لا تعطِ روابط من عندك.
8) إذا سأل الطالب سؤالًا عامًا لا يعتمد على الخطة، أجب باختصار وبأسلوب لطيف.
9) إذا طلب الطالب اقتراح جدول، فاعتمد على تسلسل الخطة الدراسية، ويفضل اقتراح مواد الفصل الأقرب التالي قبل القفز إلى فصول متقدمة.
10) إذا ذكر الطالب مواد أنهاها، فخذها بعين الاعتبار بشكل منطقي عند الإجابة.

الخطة الدراسية المعتمدة لقسم علم الحاسوب:

السنة الأولى - الفصل الأول:
- 010610014: لغة انجليزية للمبتدئين (0)
- 040111001: اللغة العربية (2)
- 110411000: مهارات الحاسوب (2)
- متطلب جامعي اختياري (2)
- متطلب جامعي اختياري (2)
- 100411010: تفاضل وتكامل - 1 (3)
- 110111030: مختبر مقدمة في تكنولوجيا المعلومات (1)
- 240221010: مقدمة في تكنولوجيا المعلومات (2)
المجموع: 14

السنة الأولى - الفصل الثاني:
- 010610025: لغة إنجليزية للمتوسطين (2)
- 010610026: لغة إنجليزية للمتوسطين مختبر (1)
- 100411020: تفاضل وتكامل - 2 (3)
- 100413750: رياضيات منفصلة (3)
- 240111011: اساسيات البرمجة (++C) (3)
- 240111021: مختبر اساسيات البرمجة 1 (++C) (1)
- 110411100: تصميم المنطق الرقمي (3)
المجموع: 16

السنة الثانية - الفصل الأول:
- 010610035: لغة انجليزية للمتقدمين (2)
- 010610036: لغة انجليزية للمتقدمين مختبر (1)
- 040521301: أسس أساليب البحث (2)
- 100412040: الرياضيات لتكنولوجيا المعلومات (3)
- 110412120: مختبر اساسيات البرمجة 2 (1)
- 240112003: اساسيات البرمجة 2 (3)
- 240112111: مقدمة في هيكلية الحاسوب (3)
- مساقات حرة (3)
المجموع: 18

السنة الثانية - الفصل الثاني:
- 040511011: الدراسات الفلسطينية (2)
- متطلب جامعي اختياري (2)
- 110113220: مختبر شبكات الحاسوب (1)
- 110412130: مختبر تركيب بيانات (1)
- 240112031: تركيب البيانات (3)
- 240113121: مقدمة في قواعد البيانات (3)
- 240113132: مختبر مقدمة في قواعد البيانات (1)
- 240213480: المحادثة والكتابة التقنية (3)
المجموع: 16

السنة الثالثة - الفصل الأول:
- 240113020: تقنيات البرمجة والخوارزميات (3)
- 240113311: مقدمة في نظم التشغيل (3)
- 240212010: مبادئ برمجة الكيانات (3)
- 240213081: تطوير تطبيقات الانترنت 1 (3)
- مساقات حرة (3)
المجموع: 15

السنة الثالثة - الفصل الثاني:
- متطلب جامعي اختياري (2)
- 240113171: مقدمة في هندسة البرمجيات (3)
- 240113291: برمجة الأجهزة المحمولة (3)
- 240114471: إدارة مشاريع تكنولوجيا المعلومات (3)
- 240213010: برمجة الكيانات المتقدمة (3)
- مساقات حرة (3)
المجموع: 17

السنة الثالثة - الفصل الصيفي:
- 000011110: خدمة مجتمع (0)
- 240113990: تدريب ميداني - علم الحاسوب (3)
المجموع: 3

السنة الرابعة - الفصل الأول:
- 240113620: التحقق واختبار البرمجيات (3)
- 240114331: عمارة الحاسوب (3)
- 240114341: مختبر يونكس (1)
- 240114974: مشروع تخرج 1 (1)
- 240212100: أساسيات رسومات الحاسوب (3)
- 240213231: البرمجة المرئية (3)
- متطلب تخصص اختياري (3)
المجموع: 17

السنة الرابعة - الفصل الثاني:
- 240113221: أمن المعلومات (3)
- 240114081: نظرية الحوسبة (3)
- 240114350: الذكاء الإصطناعي (3)
- 240114982: مشروع التخرج 2 - علم الحاسوب (3)
- متطلب تخصص اختياري (3)
- متطلب تخصص اختياري (3)
المجموع: 18

قواعد الرد:
- أجب بالعربية.
- كن واضحًا ومختصرًا ومفيدًا.
- إذا سأل الطالب عن مادة، اذكر اسمها ورقمها وساعاتها إذا كانت موجودة بالخطة.
- إذا سأل عن اقتراح جدول، لا تعطِ جدولًا نهائيًا حاسمًا إذا كانت المعلومات ناقصة، بل أعطه اقتراحًا أوليًا واطلب منه ذكر المواد التي أنهاها.
- إذا كان السؤال خارج الخطة، قل ذلك بوضوح.
"""

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def normalize_text(text):
    if text is None:
        return ""

    text = str(text).strip().lower()

    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = text.replace("،", ",")
    text = re.sub(r"[^\w\s,/\-+()]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize(text):
    return [t for t in normalize_text(text).split() if t]

def looks_like_course_code(text):
    if not text:
        return False

    patterns = [
        r"\b[a-zA-Z]{2,6}\s*\d{2,4}\b",
        r"\b\d{6,12}\b"
    ]
    return any(re.search(pattern, str(text)) for pattern in patterns)


def load_links():
    global cache_links, last_update

    if cache_links and time.time() - last_update < CACHE_TIME:
        return cache_links

    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(url)

        links_dict = {}

        if "keywords" not in df.columns or "link" not in df.columns:
            cache_links = {}
            last_update = time.time()
            return cache_links

        for _, row in df.iterrows():
            if pd.isna(row["keywords"]) or pd.isna(row["link"]):
                continue

            link = str(row["link"]).strip()
            if not link:
                continue

            keywords = str(row["keywords"]).split(",")

            for keyword in keywords:
                clean_keyword = normalize_text(keyword)
                if clean_keyword:
                    links_dict[clean_keyword] = link

        cache_links = links_dict
        last_update = time.time()

    except Exception as e:
        print("Error loading sheet:", e)
        cache_links = {}

    return cache_links

def detect_intent(user_message):
    msg = normalize_text(user_message)

    general_patterns = [
        "اسمك", "من انت", "مين انت", "كيفك", "ما اسمك",
        "ساعدني", "اشرح", "كيف", "ليش", "لماذا", "شو",
        "what", "who", "how", "why"
    ]

    schedule_patterns = [
        "جدول", "سجل", "اسجل", "اقترح", "مواد الفصل", "خطة", "ساعات"
    ]

    link_patterns = [
        "رابط", "لينك", "المصدر", "البورتال", "portal",
        "محاضره", "محاضرة", "ماده", "مادة", "ملف", "ملفات"
    ]

    if looks_like_course_code(user_message):
        return "course_like"

    if any(p in msg for p in schedule_patterns):
        return "general_ai"

    if any(p in msg for p in link_patterns):
        return "course_like"

    if any(p in msg for p in general_patterns):
        return "general_ai"

    if len(msg.split()) <= 3:
        return "course_like"

    return "unknown"

def find_best_link(user_message, links):
    normalized_message = normalize_text(user_message)
    message_tokens = set(tokenize(normalized_message))

    best_score = 0.0
    best_link = ""

    for keyword, link in links.items():
        keyword_tokens = set(tokenize(keyword))

        seq_score = similarity(normalized_message, keyword)

        contains_score = 0.0
        if keyword in normalized_message or normalized_message in keyword:
            contains_score = 0.97

        overlap_score = 0.0
        if keyword_tokens:
            overlap_score = len(message_tokens & keyword_tokens) / len(keyword_tokens)

        words = normalized_message.split()
        word_scores = [similarity(word, keyword) for word in words] if words else [0]
        max_word_score = max(word_scores) if word_scores else 0

        score = max(seq_score, contains_score, overlap_score, max_word_score * 0.88)

        if score > best_score:
            best_score = score
            best_link = link

    return best_score, best_link

def ask_gemini(user_message):
    if gemini_client is None:
        return (
            "لم أجد رابطًا مناسبًا، وخدمة الذكاء الاصطناعي غير مفعلة حاليًا.\n"
            "يمكنك كتابة اسم المادة أو كودها بشكل أوضح."
        )

    prompt = f"""
{STUDY_PLAN_PROMPT}

رسالة الطالب:
{user_message}
""".strip()

    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        text = getattr(response, "text", None)
        if text and text.strip():
            return text.strip()

        return "عذرًا، لم أستطع توليد إجابة مناسبة الآن."
    except Exception as e:
        print("Gemini error:", e)
        return "حدث خطأ أثناء محاولة الإجابة بالذكاء الاصطناعي. حاول مرة أخرى لاحقًا."

def generate_reply(user_message):
    try:
        links = load_links()
    except Exception:
        links = {}

    intent = detect_intent(user_message)
    best_score, best_link = find_best_link(user_message, links)

    if intent == "general_ai":
        return ask_gemini(user_message)

    if intent == "course_like":
        if best_score >= 0.60:
            return best_link
        return ask_gemini(user_message)

    if best_score >= 0.72:
        return best_link

    
    return ask_gemini(user_message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلًا 👋\n"
        "أنا Mubtaker Bot.\n\n"
        "اكتب اسم المادة أو كودها، وسأحاول إيجاد الرابط المناسب.\n"
        "ويمكنك أيضًا سؤالي عن الخطة الدراسية أو اقتراح جدول."
    )

async def reply_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    reply = generate_reply(user_message)
    await update.message.reply_text(reply)

telegram_app = ApplicationBuilder().token(TOKEN).build()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reply_message))

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    telegram_app.run_polling()
