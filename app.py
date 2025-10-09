
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random, os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def load_list(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

questions = load_list("questions.txt")
love_challenges = load_list("challenges.txt")
confessions = load_list("confessions.txt")
personality_questions = load_list("personality.txt")

user_sessions = {}

def analyze_personality(answers):
    score_active = 0
    score_calm = 0
    score_love = 0
    for a in answers:
        t = a.strip().lower()
        if any(x in t for x in ["نشاط", "تجمع", "قائد", "اجتماعي", "عفوي"]):
            score_active += 1
        if any(x in t for x in ["هدوء", "تفكر", "سكوت", "وحدي", "صبر"]):
            score_calm += 1
        if any(x in t for x in ["عاطفي", "حب", "مشاعر", "اشتاق", "قلب"]):
            score_love += 1
    if score_love > max(score_active, score_calm):
        return "شخصية عاطفية حساسة 💗"
    elif score_active > score_calm:
        return "شخصية منفتحة ونشيطة 🔥"
    elif score_calm > score_active:
        return "شخصية هادئة ومتزنة 🌿"
    else:
        return "شخصية متوازنة 👌"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip().lower()
    if "سؤال" in text or "سوال" in text:
        asked = user_sessions.get(user_id, {}).get("asked", set())
        available = [q for q in questions if q not in asked]
        if not available:
            asked = set()
            available = questions.copy()
        q = random.choice(available)
        user_sessions.setdefault(user_id, {})["asked"] = asked | {q}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return
    elif "تحدي" in text:
        c = random.choice(love_challenges)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💌 {c}"))
        return
    elif "اعتراف" in text:
        conf = random.choice(confessions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🩷 {conf}"))
        return
    elif "تحليل" in text:
        user_sessions[user_id] = {"step":0,"answers":[]}
        q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"🧠 نبدأ تحليل شخصيتك!\nالسؤال 1:\n{q}"
        ))
        return
    elif user_id in user_sessions and "answers" in user_sessions[user_id]:
        session = user_sessions[user_id]
        session["answers"].append(text)
        session["step"] += 1
        if session["step"] >= 10:
            try:
                profile = line_bot_api.get_profile(user_id)
                name = profile.display_name
            except:
                name = "مشارك"
            analysis = analyze_personality(session["answers"])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"🔍 تحليل شخصية {name}:\n{analysis}"
            ))
            del user_sessions[user_id]
        else:
            q = random.choice([x for x in personality_questions if x not in session["answers"]])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text=f"السؤال {session['step']+1}:\n{q}"
            ))
        return
    elif "مساعدة" in text:
        help_text = (
            "❤️ أوامر البوت:\n"
            "- 'سؤال' أو 'سوال' → سؤال حب أو صراحة.\n"
            "- 'تحدي' → تحدي حب.\n"
            "- 'اعتراف' → اعتراف صريح.\n"
            "- 'تحليل' → تحليل شخصيتك.\n"
            "- 'مساعدة' → عرض الأوامر.\n"
            "كل مرة الأسئلة تتغير تلقائيًا 💫"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
