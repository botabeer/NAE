from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, typing, re

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("الرجاء ضبط مفاتيح Line بشكل صحيح")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

def load_file_lines(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personality_file = load_file_lines("personality.txt")

if not questions_file:
    questions_file = ["ما أكثر صفة تحبها في شريك حياتك؟", "ما أول شعور جاءك لما شفته أول مرة؟"]
if not challenges_file:
    challenges_file = ["اكتب رسالة تبدأ بـ: أحبك لأن...", "ارسل له صورة تمثل أجمل ذكرى."]
if not confessions_file:
    confessions_file = ["اعترف بأول شخص جذبك في حياتك.", "اعترف بعادة سيئة عندك."]
if not personality_file:
    personality_file = ["هل تعتبر نفسك اجتماعي أم انطوائي؟", "تحب تبدأ يومك بالنشاط ولا الهدوء؟"]

# -------------------------------
# الألعاب: 10 ألعاب × 5 أسئلة
# -------------------------------
games = {
    "لعبه1": [
        "تمشي في مكان غامض وترى شخص يبتسم لك. ماذا تفعل؟ 1. تقترب وتعرفه 2. تتجنب 3. تراقبه بصمت 4. تبتسم بالمقابل",
        "وجدت رسالة غامضة على الطاولة. كيف تتصرف؟ 1. تقرأها فورًا 2. تتجاهلها 3. تحفظها لوقت لاحق 4. تشاركها مع شخص تثق به",
        "شخص يعرض عليك مساعدة سرية، تقبل؟ 1. نعم مباشرة 2. لا أبدًا 3. أستفسر أولًا 4. أراقب الوضع",
        "وجدت كتابًا مغلقًا بلا عنوان، تفعل؟ 1. تفتحه فورًا 2. تتركه 3. تحمله معك 4. تعرضه للآخرين",
        "شخص يطلب رأيك في أمر حساس. ماذا تختار؟ 1. الصراحة 2. الدبلوماسية 3. التجاهل 4. المساعدة الخفية"
    ],
    "لعبه2": [
        "تستيقظ في مكان غامض وتسمع صوت موسيقى. ماذا تفعل؟ 1. تتبع الصوت 2. تهرب 3. تنتظر 4. تبحث عن مصدر آخر",
        "شخص غريب يقدم لك هدية. كيف تتصرف؟ 1. تقبل بسرور 2. ترفض بأدب 3. تسأل عن السبب 4. تراقبه أولًا",
        "رأيت شخصًا يراقبك. تتصرف؟ 1. تقترب للتحدث 2. تتجاهل 3. تبتعد 4. تراقبه أولًا",
        "تجد مفتاحًا غامضًا، تفعل؟ 1. تلتقطه 2. تتركه 3. تبحث عن صاحبه 4. تخفيه",
        "يُطلب منك قرار سريع. كيف تتصرف؟ 1. تتخذ القرار 2. تنتظر 3. تستشير أحدًا 4. تدرس الخيارات"
    ]
}

# -------------------------------
# ربط الشخصيات مع تحليل منطقي
# -------------------------------
characters = {
    "الاجتماعي": {"كلمات": ["تتحدث", "تشارك", "تتفاعل"], "وصف": "شخصية اجتماعية بطبعها، ودودة وتحب التواصل."},
    "العاطفي": {"كلمات": ["أحس", "أشعر", "أهتم"], "وصف": "شخصية حساسة وحنونة، تهتم بمشاعر الآخرين."},
    "الفضولي": {"كلمات": ["أبحث", "أستكشف", "أجرب"], "وصف": "تحب المعرفة والاكتشاف والتعلم المستمر."},
    "المنطقي": {"كلمات": ["أفكر", "أحلل", "أقرر"], "وصف": "شخصية تحليلية وواقعية تعتمد على العقل والمنطق."},
    "العميق": {"كلمات": ["أتأمل", "أراجع", "أتعمق"], "وصف": "شخصية متأملة تبحث عن المعاني والأسباب."},
    "الحازم": {"كلمات": ["أقرر", "أنفذ", "أقود"], "وصف": "شخصية قوية تعرف ما تريد وتتخذ القرارات بحزم."},
    "الداعم": {"كلمات": ["أساعد", "أدعم", "أساند"], "وصف": "تهتم بمساعدة الآخرين وتقديم الدعم باستمرار."},
    "المبتكر": {"كلمات": ["أبتكر", "أصمم", "أخلق"], "وصف": "خيالك واسع وتبحث دائمًا عن حلول جديدة."},
    "المستقل": {"كلمات": ["أعتمد", "أقرر", "أتحمل"], "وصف": "تعتمد على نفسك في كل المواقف وتحب الحرية."},
    "الكاريزمي": {"كلمات": ["ألهم", "أحفز", "أقنع"], "وصف": "شخصية جذابة تؤثر بالآخرين وتلهمهم بالحماس."}
}

user_data = {}

def analyze_personality(answers):
    scores = {k: 0 for k in characters.keys()}
    for ans in answers:
        for char, data in characters.items():
            for kw in data["كلمات"]:
                if kw in ans:
                    scores[char] += 1
    result = sorted(scores.items(), key=lambda x: x[1], reverse=True)[0][0]
    return characters[result]["وصف"]

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
    profile = line_bot_api.get_profile(user_id)
    user_name = profile.display_name

    if text == "مساعدة":
        msg = "الأوامر المتاحة:\nسؤال - تحدي - اعتراف - شخصي - لعبه1 إلى لعبه10"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
        return

    if text in ["سؤال", "تحدي", "اعتراف", "شخصي"]:
        file_map = {
            "سؤال": questions_file,
            "تحدي": challenges_file,
            "اعتراف": confessions_file,
            "شخصي": personality_file
        }
        line_bot_api.reply_message(event.reply_token, TextSendMessage(random.choice(file_map[text])))
        return

    if text in games:
        user_data[user_id] = {"game": text, "index": 0, "answers": []}
        first_q = games[text][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(f"{user_name}، لنبدأ!\n\n{first_q}"))
        return

    if user_id in user_data:
        data = user_data[user_id]
        if text.isdigit() and 1 <= int(text) <= 4:
            data["answers"].append(text)
            data["index"] += 1
            if data["index"] < len(games[data["game"]]):
                next_q = games[data["game"]][data["index"]]
                line_bot_api.reply_message(event.reply_token, TextSendMessage(next_q))
            else:
                result = analyze_personality(data["answers"])
                msg = f"النتيجة النهائية لـ {user_name}:\n{result}"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(msg))
                del user_data[user_id]
        return

    # تجاهل الأوامر غير المعروفة بدون أي رد
    return

if __name__ == "__main__":
    app.run(port=5000, debug=True)
