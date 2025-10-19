from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, typing, json

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -------------------------
# تحميل الملفات
# -------------------------
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

def load_games_from_txt(filename: str) -> dict:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.loads(f.read())
    except Exception:
        return {}

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personality.txt")
games = load_games_from_txt("games.txt")

# قراءة الشخصيات من ملف characters.txt
try:
    with open("characters.txt", "r", encoding="utf-8") as f:
        personalities = f.read().split("\n\n")
except Exception:
    personalities = []

# -------------------------
# الجلسات
# -------------------------
group_sessions = {}

# -------------------------
# Webhook
# -------------------------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# -------------------------
# المنطق الأساسي
# -------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    global group_sessions
    text = event.message.text.strip()
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)

    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="الأوامر:
سؤال
تحدي
اعتراف
شخصي
لعبه1 إلى لعبه10"
        ))
        return

    if text == "سؤال":
        q = random.choice(questions_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    if text == "تحدي":
        c = random.choice(challenges_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=c))
        return

    if text == "اعتراف":
        cf = random.choice(confessions_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=cf))
        return

    if text == "شخصي":
        p = random.choice(personal_file)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=p))
        return

    # بدء اللعبة
    if group_id and text.startswith("لعبه"):
        if text not in games:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب لعبه1 حتى لعبه10 لبدء لعبة."))
            return
        group_sessions[group_id] = {"game": text, "players": {}, "state": "joining"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"بدأت {text}! كل عضو يرسل 'ابدأ' للانضمام."
        ))
        return

    # انضمام لاعب جديد
    if group_id in group_sessions and text == "ابدأ":
        session = group_sessions[group_id]
        player_name = f"لاعب {len(session['players'])+1}"
        session["players"][user_id] = {"answers": [], "index": 0, "name": player_name}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=f"{player_name} تم تسجيلك! أجب بالأرقام 1-4."
        ))
        first_q = games[session["game"]][0]
        line_bot_api.push_message(user_id, TextSendMessage(text=f"{player_name}\n{first_q}"))
        return

    # تسجيل الإجابة
    if group_id in group_sessions:
        session = group_sessions[group_id]
        if user_id in session["players"] and text in ["1", "2", "3", "4"]:
            player = session["players"][user_id]
            player["answers"].append(int(text))
            player["index"] += 1

            if player["index"] < len(games[session["game"]]):
                next_q = games[session["game"]][player["index"]]
                line_bot_api.push_message(user_id, TextSendMessage(text=f"{player['name']}\n{next_q}"))
            else:
                # تحليل نهائي بسيط
                result = random.choice(personalities) if personalities else "تحليل غير متوفر"
                line_bot_api.push_message(user_id, TextSendMessage(
                    text=f"{player['name']}\nنتيجتك الشخصية:\n{result}"
                ))
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
