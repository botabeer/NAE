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

# -------------------------
# تحميل الملفات
# -------------------------
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

# -------------------------
# تتبع مؤشر كل مستخدم لكل نوع
# -------------------------
user_indices = {
    "سؤال": {},
    "تحدي": {},
    "اعتراف": {},
    "شخصي": {}
}

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
# التعامل مع الرسائل
# -------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id

    if text == "مساعدة":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text="الأوامر المتاحة:\n- سؤال\n- تحدي\n- اعتراف\n- شخصي"
        ))
        return

    if text in ["سؤال", "تحدي", "اعتراف", "شخصي"]:
        # اختيار الملف المناسب
        if text == "سؤال":
            file_list = questions_file
        elif text == "تحدي":
            file_list = challenges_file
        elif text == "اعتراف":
            file_list = confessions_file
        else:
            file_list = personal_file

        # مؤشر المستخدم
        index = user_indices[text].get(user_id, 0)
        msg = file_list[index]

        # إرسال السؤال أو التحدي أو الاعتراف أو الشخصي
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))

        # تحديث المؤشر بشكل دائري
        index = (index + 1) % len(file_list)
        user_indices[text][user_id] = index
        return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
