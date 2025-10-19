from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, typing, re, json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# تحميل الملفات
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personality_file = load_file_lines("personality.txt")

if not questions_file:
    questions_file = ["ما أكثر صفة تحبها في شريك حياتك؟", "ما أول شعور جاءك لما شفته لأول مرة؟"]
if not challenges_file:
    challenges_file = ["اكتب رسالة قصيرة تبدأ بـ أحبك لأن", "ارسل له صورة تمثل أجمل ذكرى عندك معه"]
if not confessions_file:
    confessions_file = ["اعترف بأول شخص جذبك في حياتك", "اعترف بأكثر عادة سيئة عندك"]
if not personality_file:
    personality_file = ["تحب تبدأ يومك بالنشاط او بالهدوء", "هل تعتبر نفسك اجتماعي أم انطوائي"]

# تحميل الألعاب من ملف JSON
try:
    with open("games.json", "r", encoding="utf-8") as f:
        games = json.load(f)
except Exception:
    games = {}

# تحميل الشخصيات من ملف JSON
try:
    with open("characters.json", "r", encoding="utf-8") as f:
        characters = json.load(f)
except Exception:
    characters = {}

# جدول النقاط يربط الإجابات بالشخصيات
personality_points = {
    "الاجتماعي": ["الصداقة", "العمل", "الاهل"],
    "العاطفي": ["الحب", "الذكريات", "العائلة"],
    "الفضولي": ["المستقبل", "الخيال", "الاكتشاف"],
    "المنطقي": ["القرارات", "العمل", "المواقف"],
    "العميق": ["الذات", "التفكير", "الماضي"],
    "الحازم": ["العمل", "القيادة", "القرارات"],
    "الداعم": ["الاهل", "الاصدقاء", "العلاقات"],
    "المبتكر": ["الخيال", "الابداع", "التغيير"],
    "المستقل": ["القرارات", "المسؤولية", "المستقبل"],
    "الكاريزمي": ["القيادة", "الاصدقاء", "التأثير"]
}

# ذاكرة مؤقتة لتخزين إجابات كل مستخدم
user_answers = {}

HELP_TEXT = (
    "أوامر البوت:\n"
    "- سؤال → عرض سؤال عام\n"
    "- تحدي → تحدي ممتع\n"
    "- اعتراف → اعتراف\n"
    "- شخصي → سؤال شخصي\n"
    "- لعبه1 إلى لعبه10 → بدء لعبة جماعية\n"
    "طريقة اللعب:\n"
    "1. بعد بدء اللعبة كل عضو يرسل 'ابدأ' للانضمام\n"
    "2. سيظهر لكل عضو 5 أسئلة بالترتيب\n"
    "3. يجيب كل عضو على كل سؤال بالرقم المناسب 1-4\n"
    "4. بعد انتهاء جميع الأسئلة سيظهر تحليل الشخصية بناءً على الإجابات"
)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    # أمر مساعدة
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(HELP_TEXT))
        return

    # ألعاب
    if text.startswith("لعبه"):
        game_number = text.replace("لعبه", "")
        game_key = f"game{game_number}"
        if game_key in games:
            question = games[game_key]["question"]
            options = games[game_key]["options"]
            msg = f"🎮 **{user_id}**، لعبتك رقم {game_number}:\n{question}\n"
            for idx, opt in enumerate(options, start=1):
                msg += f"{idx}. {opt}\n"
            msg += "\nاختر رقم الإجابة 1-4"
            user_answers[user_id] = {"game": game_number, "answers": []}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
            return
        else:
            return

    # اختيار الإجابة
    if text.isdigit() and int(text) in range(1,5):
        if user_id not in user_answers:
            return
        choice = int(text)
        game_number = user_answers[user_id]["game"]
        game_key = f"game{game_number}"
        selected_option = games[game_key]["options"][choice -1]
        user_answers[user_id]["answers"].append(selected_option)
        if len(user_answers[user_id]["answers"]) >= 10:
            result = analyze_personality(user_answers[user_id]["answers"])
            del user_answers[user_id]
            msg = f"✅ **{user_id}** انتهت اللعبة\n\n{result}"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
            return
        else:
            msg = f"✅ **{user_id}** اخترت: {selected_option}\nاكتب لعبه{int(game_number)+1} للسؤال التالي"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
            return

    # أسئلة عامة
    if text == "سؤال":
        q = random.choice(questions_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(q))
        return

    # تحدي
    if text == "تحدي":
        c = random.choice(challenges_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(c))
        return

    # اعتراف
    if text == "اعتراف":
        c = random.choice(confessions_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(c))
        return

    # شخصي
    if text == "شخصي":
        c = random.choice(personality_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(c))
        return

    # تجاهل أي أمر غير معروف
    return

def analyze_personality(answers: typing.List[str]) -> str:
    scores = {char:0 for char in characters.keys()}
    for ans in answers:
        for char, topics in personality_points.items():
            if any(keyword in ans for keyword in topics):
                scores[char] +=1
    top_character = max(scores, key=scores.get)
    description = characters[top_character]
    result = f"شخصيتك الأقرب: {top_character}\n{description['الوصف']}\nالإيجابيات: {', '.join(description['الإيجابيات'])}\nالسلبيات: {', '.join(description['السلبيات'])}"
    return result

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=True)
