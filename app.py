from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random
import os

app = Flask(__name__)

# التوكن والسكرت
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("خطأ: تأكد من وضع LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET في متغيرات البيئة")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# أسئلة حسب الفئة
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
        "من الأكثر جرأة في حياتك؟",
        "من الأكثر كذبًا بين أصدقائك؟"
    ]
}

welcome_message = "أهلا! اختر نوع الأسئلة: حب، شخصية، صداقة، جنس، أو لعبة من الأكثر."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')

    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("خطأ: التوقيع غير صحيح")
        return 'Invalid signature', 200  # لا يزال LINE يحتاج 200
    except Exception as e:
        print(f"خطأ: {e}")
        return 'Error', 200  # أي خطأ آخر أيضًا يرجع 200

    return 'OK', 200  # دائمًا 200

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    text = event.message.text.lower()

    if text in questions:
        q = random.choice(questions[text])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=q)
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=welcome_message)
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
