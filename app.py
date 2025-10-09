from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    TemplateSendMessage, ButtonsTemplate, MessageAction,
    PostbackEvent, PostbackAction
)
import os, random, urllib.parse

app = Flask(__name__)

# مفاتيح LINE من Render Environment Variables
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print("❌ تأكد من وضع متغيرات البيئة في Render")
    exit(1)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# قواعد بيانات مؤقتة
user_asked = {"صراحة":{}, "اعتراف":{}, "تحدي":{}}
user_analysis = {}

# الأسئلة
truth_qs = ["هل قد خبيت شي مهم؟", "وش أكثر شي ندمت عليه؟", "هل قد كذبت على شخص قريب؟"] * 34
confess_qs = ["اعترف بشي محد يدري عنه", "اعترف بأول حب في حياتك", "اعترف بأكبر غلطة سويتها"] * 34
challenges = ["ارسل مقطع صوت تقول فيه كلمة تحبها", "قول صفة في شريكك بصوت عالي"] * 34

analysis_qs = [
    {"q": "لو زعلت، وش أول ردّة فعلك؟",
     "opts": [("أسكت", "calm"), ("أزعل", "sensitive"), ("أتناقش", "strong"), ("أطنّش", "social")]}
] * 20

# القائمة الرئيسية
def main_menu():
    return TemplateSendMessage(
        alt_text="القائمة الرئيسية",
        template=ButtonsTemplate(
            title="🎮 القائمة الرئيسية",
            text="اختر نوع اللعبة:",
            actions=[
                MessageAction(label="💬 صراحة", text="صراحة"),
                MessageAction(label="🗣️ اعترافات", text="اعتراف"),
                MessageAction(label="🔥 تحديات", text="تحدي"),
                MessageAction(label="🎯 تحليل الشخصية", text="تحليل"),
                MessageAction(label="❓ مساعدة", text="مساعدة")
            ]
        )
    )

# تحليل الشخصية
def start_analysis(uid):
    pool = list(range(len(analysis_qs)))
    random.shuffle(pool)
    user_analysis[uid] = {"q": pool, "i": 0, "s": {"calm":0, "sensitive":0, "strong":0, "social":0}}
    return build_question(uid)

def build_question(uid):
    data = user_analysis[uid]
    qid = data["q"][data["i"]]
    q = analysis_qs[qid]
    actions = []
    for label, trait in q["opts"]:
        d = urllib.parse.urlencode({"a":"ans","t":trait})
        actions.append(PostbackAction(label=label, data=d))
    return TemplateSendMessage(
        alt_text="سؤال تحليل",
        template=ButtonsTemplate(
            title=f"سؤال {data['i']+1}/{len(data['q'])}",
            text=q["q"],
            actions=actions
        )
    )

def analysis_result(scores):
    t = max(scores, key=scores.get)
    desc = {
        "calm": "تحب الهدوء وتفكر قبل ما تتصرف.",
        "sensitive": "عاطفي وتحس بسرعة، وتقدّر التفاصيل.",
        "strong": "شخصيتك قوية وواثقة بنفسها.",
        "social": "تحب الناس والضحك والجو الحلو."
    }
    return f"🎯 تحليلك:\n{desc[t]}"

# Webhook
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
def on_message(event):
    uid = event.source.user_id
    msg = event.message.text.strip().lower()

    if msg in ["ابدأ", "ابدا", "start"]:
        line_bot_api.reply_message(event.reply_token, main_menu()); return

    if "مساعدة" in msg:
        txt = ("📘 الأوامر المتاحة:\n"
               "- صراحة: سؤال جريء\n"
               "- اعتراف: قول شي ما يعرفه أحد\n"
               "- تحدي: تحدي عشوائي\n"
               "- تحليل: اختبار شخصية بالأزرار\n"
               "اكتب أي منها أو اضغط زر.")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=txt)); return

    if "صراحة" in msg:
        asked = user_asked["صراحة"].get(uid, set())
        available = [q for q in truth_qs if q not in asked]
        q = random.choice(available); asked.add(q)
        user_asked["صراحة"][uid] = asked
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"💬 {q}")); return

    if "اعتراف" in msg:
        asked = user_asked["اعتراف"].get(uid, set())
        available = [q for q in confess_qs if q not in asked]
        q = random.choice(available); asked.add(q)
        user_asked["اعتراف"][uid] = asked
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🗣️ {q}")); return

    if "تحدي" in msg:
        asked = user_asked["تحدي"].get(uid, set())
        available = [q for q in challenges if q not in asked]
        q = random.choice(available); asked.add(q)
        user_asked["تحدي"][uid] = asked
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"🔥 {q}")); return

    if "تحليل" in msg:
        msg = start_analysis(uid)
        line_bot_api.reply_message(event.reply_token, msg); return

@handler.add(PostbackEvent)
def on_postback(event):
    uid = event.source.user_id
    data = dict(urllib.parse.parse_qsl(event.postback.data))
    if data.get("a") == "ans":
        trait = data.get("t")
        if uid not in user_analysis: return
        user_analysis[uid]["s"][trait] += 1
        user_analysis[uid]["i"] += 1
        if user_analysis[uid]["i"] >= len(user_analysis[uid]["q"]):
            res = analysis_result(user_analysis[uid]["s"])
            del user_analysis[uid]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=res))
        else:
            q = build_question(uid)
            line_bot_api.reply_message(event.reply_token, q)

# لازم هذا السطر عشان يشتغل على Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
