from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import random
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

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