from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ---------- الأسئلة والتحديات والاعترافات ----------
questions = [
    "ما أكثر شيء تحبه في شريك حياتك؟",
    "اعترف بشيء تخفيه عنه.",
    "هل سبق وندمت على تصرف مع شريكك؟",
    "هل تغار عليه كثير؟",
    "هل تشعر أنه يفهمك بدون كلام؟"
]

love_challenges = [
    "اكتب له رسالة تبدأ بكلمة (أحبك لأن...).",
    "شارك معه ذكرى ما تنساها.",
    "قل له شي تحبه فيه ما قد قلته."
]

confessions = [
    "اعترف بأول شخص جذبك في حياتك.",
    "اعترف بأكثر عادة سيئة عندك.",
    "اعترف بشي ندمت عليه."
]

personality_questions = [
    "تحب تبدأ يومك بالنشاط ولا بالهدوء؟",
    "لما تزعل، تفضل تعبر ولا تسكت؟",
    "تحب التجمعات الكبيرة ولا الجلسات الصغيرة؟"
]

# ---------- جلسات ----------
user_sessions = {}
group_sessions = {}

# ---------- تحليل الشخصية مفصل ----------
def analyze_personality(answers):
    score_active = 0
    score_calm = 0
    score_love = 0
    for a in answers:
        t = a.strip().lower()
        if any(x in t for x in ["نشاط", "تجمع", "قائد", "اجتماعي", "عفوي"]):
            score_active += 1
        if any(x in t for x in ["هدوء", "تفكر", "سكوت", "وحدي", "صبر"]):
            score_calm += 1
        if any(x in t for x in ["عاطفي", "حب", "مشاعر", "اشتاق", "قلب"]):
            score_love += 1

    analysis = ""
    if score_love > max(score_active, score_calm):
        analysis += "شخصية عاطفية حساسة، تهتم بالآخرين وتقدر التفاصيل الصغيرة. "
    if score_active > score_calm:
        analysis += "شخصية منفتحة ونشيطة، تحب التجارب الجديدة ومليان طاقة. "
    if score_calm > score_active:
        analysis += "شخصية هادئة ومتزنة، تفكر قبل اتخاذ القرار وتحب الأمان والاستقرار. "
    if not analysis:
        analysis = "شخصية متوازنة، تعرف متى تكون هادي ومتى تكون جريء. "
    
    analysis += "اختياراتك تكشف عن ميولك، علاقاتك الاجتماعية وطريقة تعاملك مع الآخرين."
    return analysis

# ---------- Webhook ----------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ---------- الرد على الرسائل ----------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    group_id = getattr(event.source, "group_id", None)
    text = event.message.text.strip()
    text_lower = text.lower()

    # ---------- سؤال حب ----------
    if "سؤال" in text_lower or "سوال" in text_lower:
        asked = user_sessions.get(user_id, {}).get('asked_questions', set())
        available = [q for q in questions if q not in asked]
        if not available:
            asked = set()
            available = questions.copy()
        q = random.choice(available)
        user_sessions.setdefault(user_id, {})['asked_questions'] = asked | {q}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=q))
        return

    # ---------- تحدي ----------
    if "تحدي" in text_lower:
        asked = user_sessions.get(user_id, {}).get('asked_challenges', set())
        available = [c for c in love_challenges if c not in asked]
        if not available:
            asked = set()
            available = love_challenges.copy()
        c = random.choice(available)
        user_sessions.setdefault(user_id, {})['asked_challenges'] = asked | {c}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=c))
        return

    # ---------- اعتراف ----------
    if "اعتراف" in text_lower:
        asked = user_sessions.get(user_id, {}).get('asked_confessions', set())
        available = [c for c in confessions if c not in asked]
        if not available:
            asked = set()
            available = confessions.copy()
        c = random.choice(available)
        user_sessions.setdefault(user_id, {})['asked_confessions'] = asked | {c}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=c))
        return

    # ---------- اسألة شخصية ----------
    if "اسألة شخصيه" in text_lower:
        user_sessions[user_id] = {"step": 0, "answers": []}
        first_q = random.choice(personality_questions)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=first_q))
        return

    # ---------- تسجيل إجابة أسئلة شخصية ----------
    if user_id in user_sessions and 'step' in user_sessions[user_id]:
        session = user_sessions[user_id]
        if text in session.get('answers', []):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="لقد أجبت على هذا من قبل، اختر إجابة أخرى أو رقم الخيار"
            ))
            return
        session["answers"].append(text)
        session["step"] += 1
        if session["step"] >= len(personality_questions):
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "المستخدم"
            analysis = analyze_personality(session["answers"])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}: {analysis}"))
            del user_sessions[user_id]
        else:
            next_q = random.choice([q for q in personality_questions if q not in session["answers"]])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=next_q))
        return

    # ---------- ألعاب جماعية ----------
    if text_lower.startswith("لعبه"):
        if not group_id:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="هذه اللعبة فقط للمجموعات"))
            return
        group_sessions.setdefault(group_id, {})
        group_sessions[group_id].setdefault(user_id, {"answers": []})

        # الألعاب مكتملة بعشر أسئلة لكل لعبة
        if text_lower == "لعبه1":
            game_qs = [f"لعبة1 سؤال {i}" for i in range(1,11)]
        elif text_lower == "لعبه2":
            game_qs = [f"لعبة2 سؤال {i}" for i in range(1,11)]
        else:
            game_qs = [f"لعبة3 سؤال {i}" for i in range(1,11)]

        group_sessions[group_id][user_id]["game_qs"] = game_qs
        group_sessions[group_id][user_id]["step"] = 0
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=game_qs[0]))
        return

    # ---------- تسجيل إجابة الألعاب ----------
    if group_id in group_sessions and user_id in group_sessions[group_id]:
        session = group_sessions[group_id][user_id]
        if text in session.get('answers', []):
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="لقد أجبت على هذا من قبل، اختر إجابة أخرى أو رقم الخيار"
            ))
            return
        session["answers"].append(text)
        session["step"] += 1
        if session["step"] >= len(session["game_qs"]):
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "مشارك"
            analysis = analyze_personality(session["answers"])
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}: {analysis}"))
            del group_sessions[group_id][user_id]
        else:
            next_q = session["game_qs"][session["step"]]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=next_q))
        return

    # ---------- مساعدة ----------
    if "مساعدة" in text_lower:
        help_text = (
            "أوامر البوت:\n"
            "- سؤال أو سوال → سؤال حب وصراحة.\n"
            "- تحدي → تحدي عاطفي.\n"
            "- اعتراف → اعتراف صريح.\n"
            "- اسألة شخصيه → أسئلة شخصية.\n"
            "- لعبه1 / لعبه2 / لعبه3 → ألعاب جماعية.\n"
            "- مساعدة → عرض الأوامر."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="الرجاء كتابة أحد الأوامر المتاحة: مساعدة"))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
