from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os, random, typing, re

app = Flask(__name__)

# LINE credentials from environment
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("Set LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET environment variables")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Utility to load optional external lists
def load_file_lines(filename: str) -> typing.List[str]:
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception:
        return []

questions_file = load_file_lines("questions.txt")
challenges_file = load_file_lines("challenges.txt")
confessions_file = load_file_lines("confessions.txt")
personal_file = load_file_lines("personal.txt")

# Defaults if files missing
if not questions_file:
    questions_file = [
        "ما أكثر صفة تحبها في شريك حياتك؟",
        "ما أول شعور جاءك لما شفته لأول مرة؟",
        "لو تقدر تغير شيء في علاقتك، وش هو؟"
    ]
if not challenges_file:
    challenges_file = [
        "اكتب رسالة قصيرة تبدأ بـ: أحبك لأن...",
        "ارسل له صورة تمثل أجمل ذكرى عندك معه."
    ]
if not confessions_file:
    confessions_file = [
        "اعترف بأول شخص جذبك في حياتك.",
        "اعترف بأكثر عادة سيئة عندك."
    ]
if not personal_file:
    personal_file = [
        "تحب تبدأ يومك بالنشاط ولا بالهدوء؟",
        "هل تعتبر نفسك اجتماعي أم انطوائي؟"
    ]

# -------------------------
# Games data (نفسها كما هي)
# -------------------------
games: typing.Dict[str, typing.List[str]] = { ... نفس محتوى الألعاب كما في الكود السابق ... }

# -----------------------------
# Group sessions structure
# -----------------------------
group_sessions: typing.Dict[str, typing.Dict] = {}

# -----------------------------
# Keyword maps for smart scoring
# -----------------------------
KEYWORDS = {
    "قيادية": [
        r"\bتدخل\b", r"\bتقترب\b", r"\bتسرع\b", r"\bتركض\b", r"\bأهاجم\b", r"\bأقبل\b",
        r"\bأذهب\b", r"\bأقوم\b", r"\bأبدأ\b", r"\bأقود\b", r"\bأواجه\b", r"\bأتحرك\b"
    ],
    "تعبيرية": [
        r"\bأتحدث\b", r"\bأتواصل\b", r"\bأشارك\b", r"\bألوّح\b", r"\bأضحك\b", r"\bأغني\b",
        r"\bأعبر\b", r"\bأتعاطف\b", r"\bأتقابل\b", r"\bأتفاعل\b", r"\bأقترب\b"
    ],
    "تحليلية": [
        r"\bأبحث\b", r"\bأخطط\b", r"\bأفحص\b", r"\bأدرس\b", r"\bأقيس\b", r"\bأتحقق\b",
        r"\bأستخدم\b", r"\bأحسب\b", r"\bأحلل\b", r"\bأجرب\b", r"\bأختبر\b"
    ],
    "داعمة": [
        r"\bأساعد\b", r"\bأساند\b", r"\bأنتظر\b", r"\bأعتني\b", r"\bأدعم\b", r"\bأحمي\b",
        r"\bأحفظ\b", r"\bأحتفظ\b", r"\bأقف مع\b", r"\bأهتم\b", r"\bأشارك\b"
    ]
}

DESCRIPTIONS = {
    "قيادية": "الشخصية القيادية...\n(النص كما في الكود السابق)",
    "تعبيرية": "الشخصية التعبيرية...\n(النص كما في الكود السابق)",
    "تحليلية": "الشخصية التحليلية...\n(النص كما في الكود السابق)",
    "داعمة": "الشخصية الداعمة...\n(النص كما في الكود السابق)"
}

# -----------------------------
# extract_option_text / scoring / analysis functions (نفسها كما هي)
# -----------------------------

def extract_option_text(game_key: str, q_index: int, chosen: int) -> str:
    try:
        q = games[game_key][q_index]
    except Exception:
        return ""
    lines = q.splitlines()
    pattern = re.compile(rf"^\s*{chosen}\s*[\.\)\-:]\s*(.+)$")
    for line in lines:
        m = pattern.match(line)
        if m:
            return m.group(1).strip()
    opts = re.findall(r"\n\s*\d+\s*[\.\)\-:]\s*([^\n]+)", q)
    if opts and 1 <= chosen <= len(opts):
        return opts[chosen-1].strip()
    return ""

def score_answers_to_personality(answers: typing.List[typing.Tuple[int,int,str]]) -> str:
    scores = {"قيادية":0, "تعبيرية":0, "تحليلية":0, "داعمة":0}
    for q_index, chosen_num, chosen_text in answers:
        txt = (chosen_text or "").lower()
        matched = False
        for trait, kws in KEYWORDS.items():
            for kw in kws:
                if re.search(kw, txt):
                    scores[trait] += 1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            if chosen_num == 1:
                scores["قيادية"] += 1
            elif chosen_num == 2:
                scores["تحليلية"] += 1
            elif chosen_num == 3:
                scores["تعبيرية"] += 1
            elif chosen_num == 4:
                scores["داعمة"] += 1
    sorted_by_score = sorted(scores.items(), key=lambda x: (-x[1], ["قيادية","تعبيرية","تحليلية","داعمة"].index(x[0])))
    top_trait, top_score = sorted_by_score[0]
    if top_score == 0:
        return "تعبيرية"
    return top_trait

def build_final_analysis_text(name: str, trait_key: str) -> str:
    desc = DESCRIPTIONS.get(trait_key, "")
    return f"{name}\n\n{desc}"

# -----------------------------
# Webhook
# -----------------------------
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# -----------------------------
# Message handler (معدل لإزالة سطر الرد بالأرقام)
# -----------------------------
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    source = event.source
    user_id = source.user_id
    group_id = getattr(source, "group_id", None)
    text_raw = event.message.text.strip()
    text = text_raw.strip()

    # أوامر عامة
    if text == "مساعدة":
        help_text = (
            "أوامر البوت:\n"
            "- سؤال → سؤال.\n"
            "- تحدي → تحدي.\n"
            "- اعتراف → اعتراف.\n"
            "- اسئلة شخصية → سؤال شخصي عشوائي.\n"
            "- لعبه (مثال: لعبه1) → يبدأ جلسة لعبة جماعية في القروب.\n"
            "  بعد بدء اللعبة: كل عضو يكتب 'ابدأ' للانضمام ثم يجيب بالأرقام 1-4.\n"
            "البوت سيعطي تحليل مفصّل باسم كل لاعب بعد إكماله للأسئلة."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    # اختصارات عادية
    if text == "سؤال":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(questions_file)))
        return
    if text == "تحدي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(challenges_file)))
        return
    if text == "اعتراف":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(confessions_file)))
        return
    if text == "اسئلة شخصية":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(personal_file)))
        return

    # بدء لعبة
    if group_id and text.startswith("لعبه"):
        if text not in games:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب لعبه1 حتى لعبه10 لبدء لعبة."))
            return
        group_sessions[group_id] = {"game": text, "players": {}, "state": "joining"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=(f"تم بدء الجلسة: {text}\n"
                  "كل عضو يرسل 'ابدأ' للانضمام. بعد الانضمام أجب بالأرقام 1 إلى 4.\n"
                  "البوت سيعطي تحليل مفصّل باسم كل لاعب بعد الانتهاء.")
        ))
        return

    # انضمام
    if group_id and text == "ابدأ":
        gs = group_sessions.get(group_id)
        if not gs or gs.get("state") != "joining":
            return
        players = gs["players"]
        if user_id in players:
            player = players[user_id]
            step = player["step"]
            q = games[gs["game"]][step]
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q}"))
            return
        players[user_id] = {"step": 0, "answers": []}
        try:
            name = line_bot_api.get_profile(user_id).display_name
        except:
            name = "عضو"
        q0 = games[gs["game"]][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q0}"))
        return

    # الإجابات
    if group_id and group_id in group_sessions and user_id in group_sessions[group_id]["players"]:
        gs = group_sessions[group_id]
        player = gs["players"][user_id]
        ans_num = None
        txt = text.strip()
        if txt.isdigit() and 1 <= int(txt) <= 4:
            ans_num = int(txt)
        else:
            m = re.search(r"\b([1-4])\b", txt)
            if m:
                ans_num = int(m.group(1))
        if ans_num is None:
            # تجاهل فقط بدون "الرجاء الرد برقم..."
            return

        q_index = player["step"]
        game_key = gs["game"]
        chosen_text = extract_option_text(game_key, q_index, ans_num)
        player["answers"].append((q_index, ans_num, chosen_text))
        player["step"] += 1

        if player["step"] < len(games[game_key]):
            next_q = games[game_key][player["step"]]
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{next_q}"))
            return
        else:
            try:
                name = line_bot_api.get_profile(user_id).display_name
            except:
                name = "عضو"
            trait = score_answers_to_personality(player["answers"])
            final_text = build_final_analysis_text(name, trait)
            line_bot_api.push_message(group_id, TextSendMessage(text=final_text))
            del gs["players"][user_id]
            return

    return

# -----------------------------
# Run server
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
