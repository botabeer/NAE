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

user_indices = {
    "سؤال": {},
    "تحدي": {},
    "اعتراف": {},
    "شخصي": {}
}

# فهارس عامة لكل نوع (مشتركة بين جميع المستخدمين)
global_indices = {
    "سؤال": 0,
    "تحدي": 0,
    "اعتراف": 0,
    "شخصي": 0
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
    text = event.message.text.strip()
    user_id = event.source.user_id

    if text == "مساعدة":
        help_text = (
            "الأوامر المتاحة:\n"
            "- سؤال\n"
            "- تحدي\n"
            "- اعتراف\n"
            "- شخصي"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if text in ["سؤال", "تحدي", "اعتراف", "شخصي"]:
        if text == "سؤال":
            file_list = questions_file
        elif text == "تحدي":
            file_list = challenges_file
        elif text == "اعتراف":
            file_list = confessions_file
        else:
            file_list = personal_file

        if not file_list:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="لا توجد بيانات في هذا القسم حالياً."))
            return

        # المؤشر العام المشترك
        index = global_indices[text]

        msg = file_list[index]

        # إرسال الرسالة
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

        # تحديث المؤشر العام
        global_indices[text] = (index + 1) % len(file_list)

        # تحديث المؤشر الفردي للمستخدم أيضاً (يبقى متوافق مع السابق)
        user_indices[text][user_id] = global_indices[text]
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
