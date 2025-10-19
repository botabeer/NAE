from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, json, typing

app = Flask(__name__)

# مفاتيح LINE من البيئة
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يرجى تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------------
# تحميل الملفات الخارجية
# -----------------------------
def load_json(filename: str) -> dict:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def load_list(filename: str) -> list:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

games = load_json("games.json")
characters = load_json("characters.json")

questions_file = load_list("questions.txt")
challenges_file = load_list("challenges.txt")
confessions_file = load_list("confessions.txt")
personality_file = load_list("personality.txt")

# -----------------------------
# تتبع تقدم المستخدمين
# -----------------------------
user_progress = {}

# -----------------------------
# الردود على الأوامر فقط
# -----------------------------
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
    user_id = event.source.user_id
    text = event.message.text.strip()
    user_name = "@" + user_id[-4:]  # اسم رمزي بسيط

    # ✅ أوامر محددة فقط
    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            "الأوامر المتاحة:\n- سؤال\n- تحدي\n- اعتراف\n- شخصي\n- وأسماء الألعاب (مثلاً: لعبه1, لعبه2, ...)"
        ))
        return

    if text == "سؤال":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(random.choice(questions_file)))
        return

    if text == "تحدي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(random.choice(challenges_file)))
        return

    if text == "اعتراف":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(random.choice(confessions_file)))
        return

    if text == "شخصي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(random.choice(personality_file)))
        return

    # ✅ بدء لعبة
    if text in games:
        user_progress[user_id] = {"game": text, "step": 0, "answers": []}
        first_q = games[text][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{user_name} بدأ {text} 🎮\n\n{first_q}"))
        return

    # ✅ متابعة اللعبة
    if user_id in user_progress:
        data = user_progress[user_id]
        if text in characters:  # يعني المستخدم كتب رقم من 1 إلى 4 أو أكثر حسب الشخصيات
            data["answers"].append(text)
            data["step"] += 1

            if data["step"] < len(games[data["game"]]):
                next_q = games[data["game"]][data["step"]]
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{user_name}، {next_q}"))
            else:
                result = analyze_personality(data["answers"])
                line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{user_name} انتهيت من {data['game']} 🎯\n\n{result}"))
                del user_progress[user_id]
        else:
            pass  # تجاهل أي رد غير معروف
        return

    # 🚫 تجاهل الأوامر الغريبة تمامًا
    return

# -----------------------------
# التحليل المنطقي للشخصية
# -----------------------------
def analyze_personality(answers: typing.List[str]) -> str:
    if not answers or not characters:
        return "لا توجد بيانات كافية لتحليل الشخصية."

    points = {}
    for ans in answers:
        if ans in characters:
            char_name = characters[ans]["name"]
            points[char_name] = points.get(char_name, 0) + 1

    if not points:
        return "لم يتمكن البوت من تحديد شخصيتك."

    top_char = max(points, key=points.get)
    desc = ""
    for c in characters.values():
        if c["name"] == top_char:
            desc = c["description"]
            break

    return f"شخصيتك الأقرب هي: {top_char}\n\n{desc}"

# -----------------------------
# تشغيل التطبيق
# -----------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
