from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, typing

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# --- تحميل الملفات ---
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personality.txt")
game_file = load_file_lines("game_file.txt")  # ملف الألعاب الجديد
more_file = load_file_lines("more_file.txt")  # ملف محتوى أمر أكثر

# --- مؤشرات لكل مستخدم ---
user_indices = {"سؤال":{}, "تحدي":{}, "اعتراف":{}, "شخصي":{}, "لعبه":{}, "أكثر":{}}
global_indices = {"سؤال":0, "تحدي":0, "اعتراف":0, "شخصي":0, "لعبه":0, "أكثر":0}

# --- قاموس المرادفات لكل أمر ---
commands_map = {
    "سؤال": ["سؤال", "اسأله", "اسئلة"],
    "تحدي": ["تحدي", "تحديات", "تحد"],
    "اعتراف": ["اعتراف", "اعترافات"],
    "شخصي": ["شخصي", "شخصية", "شخصيات"],
    "أكثر": ["أكثر", "اكثر"],
    "لعبه": ["لعبه", "اللعبة"]
}

@app.route("/", methods=["GET"])
def home():
    return "البوت يعمل", 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip().lower()
    user_id = event.source.user_id

    # --- تحديد الأمر بناء على المرادفات ---
    command = None
    for key, variants in commands_map.items():
        if text in [v.lower() for v in variants]:
            command = key
            break

    # --- مساعدة ---
    if text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال (اسأله / اسئلة)\n"
            "- تحدي (تحديات / تحد)\n"
            "- اعتراف (اعترافات)\n"
            "- شخصي (شخصية / شخصيات)\n"
            "- أكثر (اكثر)\n"
            "- لعبه (اللعبة)"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # --- تنفيذ الأمر ---
    if command:
        if command == "سؤال":
            file_list = questions_file
        elif command == "تحدي":
            file_list = challenges_file
        elif command == "اعتراف":
            file_list = confessions_file
        elif command == "شخصي":
            file_list = personal_file
        elif command == "أكثر":
            file_list = more_file
        else:  # لعبه
            file_list = game_file

        if not file_list:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"لا توجد بيانات في {command} حالياً."))
            return

        index = global_indices[command]
        msg = file_list[index]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        global_indices[command] = (index + 1) % len(file_list)
        user_indices[command][user_id] = global_indices[command]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
