from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random
import os
import re

app = Flask(__name__)

# مفاتيح LINE
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("⚠️ تأكد من وضع LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET في متغيرات البيئة")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# الأسئلة
questions = {
    "حب": [
        "من أكثر شخص تحبه في حياتك؟",
        "هل سبق أن أحببت من النظرة الأولى؟",
        "كيف تعرف أنك تحب شخص ما؟"
    ],
    "شخصية": [
        "ما هي أسوأ عادة لديك؟",
        "إذا كان بإمكانك تغيير شيء واحد في نفسك، ماذا سيكون؟",
        "هل أنت شخص منطقي أم عاطفي أكثر؟"
    ],
    "صداقة": [
        "من هو أقرب صديق لديك ولماذا؟",
        "هل سبق أن خذلت صديقك؟",
        "ما أكثر شيء تحبه في أصدقائك؟"
    ],
    "جنس": [
        "هل تؤمن بالحب قبل الجنس؟",
        "ما أكثر شيء يلفت انتباهك في الشخص الآخر؟",
        "هل سبق أن وقعت في علاقة سرية؟"
    ],
    "من_الأكثر": [
        "من الأكثر مرحًا بين أصدقائك؟",
        "من الأكثر كذبًا؟",
        "من الأكثر رومانسية؟",
        "من الأكثر غموضًا؟",
        "من الأكثر طيبة؟",
        "من الأكثر عصبية؟",
        "من الأكثر فوضى؟",
        "من الأكثر أنانية؟",
        "من الأكثر خوفًا؟",
        "من الأكثر تفكيرًا بالمستقبل؟",
        "من الأكثر هدوءًا؟",
        "من الأكثر ضحكًا؟",
        "من الأكثر نسيانًا؟"
    ]
}

# رسالة المساعدة
help_message = """
📘 أوامر البوت:
- حب → أسئلة عن الحب ❤️
- شخصية → أسئلة عن شخصيتك 🧠
- صداقة → أسئلة عن الأصدقاء 🤝
- جنس → أسئلة جريئة ⚡️
- من الأكثر → لعبة من الأكثر 🎯
- مساعدة → عرض هذه القائمة 🧾
"""

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ خطأ في التوقيع")
        return 'Invalid signature', 200
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return 'Error', 200
    return 'OK', 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.strip().lower()

    # --- من الأكثر (أي كتابة قريبة منها)
    if re.search(r"(من|مين)?\s*ال?اكثر", text):
        q = random.choice(questions["من_الأكثر"])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # --- حب
    if re.search(r"حب", text):
        q = random.choice(questions["حب"])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # --- شخصية
    if re.search(r"شخص", text):
        q = random.choice(questions["شخصية"])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # --- صداقة
    if re.search(r"صداق", text):
        q = random.choice(questions["صداقة"])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # --- جنس
    if re.search(r"جنس", text):
        q = random.choice(questions["جنس"])
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # --- مساعدة
    if re.search(r"مساعد", text):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_message))
        return

    # --- أي شيء آخر (يتجاهله تمامًا)
    return


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
