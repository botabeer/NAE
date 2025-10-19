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
# Games: 10 games, each 5 Qs (shortened)
# -------------------------
games: typing.Dict[str, typing.List[str]] = {
    "لعبه1": [
        "سؤال 1:\nأنت تمشي في غابة مظلمة وهادئة، فجأة تسمع صوت خطوات خلفك. ماذا تفعل؟\n1. تلتفت فورًا\n2. تسرع بخطواتك\n3. تتجاهل وتواصل طريقك\n4. تختبئ خلف شجرة",
        "سؤال 2:\nتصل إلى نهر يجري بسرعة. كيف تعبره؟\n1. تبني جسرًا صغيرًا\n2. تبحث عن مكان ضحل لعبوره\n3. تسبح من خلاله\n4. تنتظر حتى يهدأ التيار",
        "سؤال 3:\nرأيت كوخًا صغيرًا بين الأشجار. ماذا تفعل؟\n1. تقترب وتطرق الباب\n2. تدخل دون تردد\n3. تراقبه من بعيد\n4. تتجاوزه وتكمل طريقك",
        "سؤال 4:\nداخل الكوخ وجدت طاولة عليها مفتاح وورقة. ماذا تأخذ؟\n1. المفتاح\n2. الورقة\n3. كليهما\n4. لا تأخذ شيئًا",
        "سؤال 5:\nخرجت من الكوخ ووجدت طريقين. أي تختار؟\n1. طريق مضيء بالشمس\n2. طريق مظلم لكنه قصير\n3. طريق فيه أزهار\n4. طريق وعر لكنه آمن"
    ],
    "لعبه2": [
        "سؤال 1:\nاستيقظت على جزيرة غامضة لوحدك. ما أول ما تفعله؟\n1. تستكشف المكان\n2. تبحث عن ماء\n3. تصرخ طلبًا للمساعدة\n4. تجلس للتفكير",
        "سؤال 2:\nرأيت أثر أقدام على الرمل. ماذا تفعل؟\n1. تتبعها\n2. تتجاهلها\n3. تراقبها من بعيد\n4. تغطيها بالرمل",
        "سؤال 3:\nوجدت ثمرة غير معروفة. هل تأكلها؟\n1. نعم فورًا\n2. لا أقترب منها\n3. أختبرها أولًا\n4. أحتفظ بها",
        "سؤال 4:\nاقترب الليل ولا مأوى لديك. ماذا تفعل؟\n1. تبني مأوى بسيط\n2. تصعد على شجرة\n3. تشعل نارًا للحماية\n4. تظل مستيقظًا",
        "سؤال 5:\nسمعت أصوات غريبة من الغابة. ماذا تفعل؟\n1. تقترب منها\n2. تبتعد فورًا\n3. تراقب من بعيد\n4. تصرخ"
    ],
    "لعبه3": [
        "سؤال 1:\nأنت في مدينة جديدة. أول شيء تفعله؟\n1. تستكشف\n2. تبحث عن مطعم\n3. تبحث عن فندق\n4. تسأل الناس",
        "سؤال 2:\nرأيت إعلانًا غريبًا في الشارع. هل تتابعه؟\n1. نعم بحماس\n2. لا أهتم\n3. ألتقط له صورة\n4. أتجاهله",
        "سؤال 3:\nشخص عرض عليك عملًا غريبًا. هل تقبله؟\n1. نعم\n2. لا\n3. أسأله التفاصيل\n4. أؤجل القرار",
        "سؤال 4:\nأضاع طفل طريقه أمامك. ماذا تفعل؟\n1. تساعده فورًا\n2. تبحث عن والديه\n3. تتصل بالشرطة\n4. تتجاهله",
        "سؤال 5:\nضعت في أحد الأحياء. كيف تتصرف؟\n1. تسأل المارة\n2. تستخدم الخريطة\n3. تتجول حتى تجد الطريق\n4. تنتظر أحدًا يساعدك"
    ],
    # لعبه4..لعبه10 بنفس الأسلوب مع 5 أسئلة لكل لعبة
    "لعبه4": [
        "سؤال 1:\nأمامك باب قصر قديم. تدخل؟\n1. أدخل مباشرة\n2. أراقب من الخارج\n3. أدعو شخصًا معي\n4. أعود لاحقًا",
        "سؤال 2:\nوجدت درجًا يؤدي للأسفل. تنزل؟\n1. نعم\n2. لا\n3. تتأكد من الضوء\n4. تبحث عن طريق آخر",
        "سؤال 3:\nوجدت مرآة تبدو غريبة. ماذا تفعل؟\n1. تنظر فيها\n2. تكسرها\n3. تلمسها\n4. تبتعد",
        "سؤال 4:\nرأيت غرفة مليئة بالكتب. ماذا تختار؟\n1. تفتح كتابًا قديمًا\n2. تأخذ واحدًا معك\n3. تتجاهلها\n4. تدعو أحدًا للمساعدة",
        "سؤال 5:\nصوت خطوات قربك، ماذا تفعل؟\n1. تراقب\n2. تختبئ\n3. تصرخ\n4. تتبع الصوت"
    ]
}

# -----------------------------
# Group sessions structure
# -----------------------------
group_sessions: typing.Dict[str, typing.Dict] = {}

# -----------------------------
# Keyword maps for smart scoring
# -----------------------------
KEYWORDS = {
    "قيادية": [r"\bتدخل\b", r"\bتقترب\b", r"\bتسرع\b", r"\bتركض\b", r"\bأهاجم\b", r"\bأقبل\b", r"\bأذهب\b", r"\bأقوم\b", r"\bأبدأ\b", r"\bأقود\b", r"\bأواجه\b", r"\bأتحرك\b"],
    "تعبيرية": [r"\bأتحدث\b", r"\bأتواصل\b", r"\bأشارك\b", r"\bألوّح\b", r"\bأضحك\b", r"\bأغني\b", r"\bأعبر\b", r"\bأتعاطف\b", r"\bأتقابل\b", r"\bأتفاعل\b", r"\bأقترب\b"],
    "تحليلية": [r"\bأبحث\b", r"\bأخطط\b", r"\bأفحص\b", r"\bأدرس\b", r"\bأقيس\b", r"\bأتحقق\b", r"\bأستخدم\b", r"\bأحسب\b", r"\bأحلل\b", r"\bأجرب\b", r"\bأختبر\b"],
    "داعمة": [r"\bأساعد\b", r"\bأساند\b", r"\bأنتظر\b", r"\bأعتني\b", r"\bأدعم\b", r"\bأحمي\b", r"\bأحفظ\b", r"\bأحتفظ\b", r"\bأقف مع\b", r"\bأهتم\b", r"\bأشارك\b"]
}

DESCRIPTIONS = {
    "قيادية": "الشخصية القيادية\n\nربما يكون نمط الشخصية القيادية معروفاً عند الغالبية، والذي يتسم بالاستقلالية والقيادة المستمرة...",
    "تعبيرية": "الشخصية التعبيرية\n\nالمعروفة أيضاً بالشخصية الاجتماعية، وهي تتميز بقدرة صاحبها على التفاعل مع الآخرين...",
    "تحليلية": "الشخصية التحليلية\n\nعادةً ما يتميز صاحب الشخصية التحليلية بالعقلانية، وتركيزه على التفاصيل...",
    "داعمة": "الشخصية الداعمة\n\nيظن البعض أنّ الشخصيات الداعمة والشخصيات الاجتماعية تتقارب كثيراً؛ فعادة ما يظلّ أصحابها على تواصل دائم مع الآخرين..."
}

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
                try:
                    if re.search(kw, txt):
                        scores[trait] += 1
                        matched = True
                        break
                except re.error:
                    continue
            if matched:
                break
        if not matched:
            if chosen_num == 1: scores["قيادية"] += 1
            elif chosen_num == 2: scores["تحليلية"] += 1
            elif chosen_num == 3: scores["تعبيرية"] += 1
            elif chosen_num == 4: scores["داعمة"] += 1
    sorted_by_score = sorted(scores.items(), key=lambda x: (-x[1], ["قيادية","تعبيرية","تحليلية","داعمة"].index(x[0])))
    top_trait, top_score = sorted_by_score[0]
    if top_score == 0:
        return "تعبيرية"
    return top_trait

def build_final_analysis_text(name: str, trait_key: str) -> str:
    desc = DESCRIPTIONS.get(trait_key, "")
    return f"{name}\n\n{desc}"

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
    source = event.source
    user_id = source.user_id
    group_id = getattr(source, "group_id", None)
    text = event.message.text.strip()

    if text == "مساعدة":
        help_text = (
            "أوامر البوت:\n"
            "- سؤال → سؤال.\n"
            "- تحدي → تحدي.\n"
            "- اعتراف → اعتراف.\n"
            "- شخصي → سؤال شخصي عشوائي.\n"
            "- لعبه (مثال: لعبه1) → يبدأ جلسة لعبة جماعية في القروب.\n"
            "  بعد بدء اللعبة: كل عضو يكتب 'ابدأ' للانضمام ثم يجيب بالأرقام 1-4.\n"
            "- البوت يتجاهل أي رسائل خارج الأوامر أو الجلسات."
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if text == "سؤال":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(questions_file)))
        return
    if text == "تحدي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(challenges_file)))
        return
    if text == "اعتراف":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(confessions_file)))
        return
    if text == "شخصي":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=random.choice(personal_file)))
        return

    if text.startswith("لعبه"):
        if text not in games:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب لعبه1 حتى لعبه10 لبدء لعبة."))
            return
        group_sessions[group_id] = {"game": text, "players": {}, "state": "joining"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(
            text=(f"تم بدء الجلسة: {text}\n"
                  "كل عضو يرسل 'ابدأ' للانضمام. بعد الانضمام أجب بالأرقام 1-4 على كل سؤال.\n"
                  "البوت سيعطي تحليل مفصّل باسم كل لاعب مباشرة بعد إكماله للأسئلة.")
        ))
        return

    if text == "ابدأ" and group_id in group_sessions:
        gs = group_sessions[group_id]
        players = gs["players"]
        if user_id in players:
            player = players[user_id]
            step = player["step"]
            q = games[gs["game"]][step]
            try: name = line_bot_api.get_profile(user_id).display_name
            except: name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q}"))
            return
        players[user_id] = {"step": 0, "answers": []}
        try: name = line_bot_api.get_profile(user_id).display_name
        except: name = "عضو"
        q0 = games[gs["game"]][0]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{q0}"))
        return

    if group_id in group_sessions and user_id in group_sessions[group_id]["players"]:
        gs = group_sessions[group_id]
        player = gs["players"][user_id]
        ans_num = None
        txt = text.strip()
        if txt.isdigit() and 1 <= int(txt) <= 4:
            ans_num = int(txt)
        else:
            m = re.search(r"\b([1-4])\b", txt)
            if m: ans_num = int(m.group(1))
        if ans_num is None:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=""))
            return
        q_index = player["step"]
        game_key = gs["game"]
        chosen_text = extract_option_text(game_key, q_index, ans_num)
        player["answers"].append((q_index, ans_num, chosen_text))
        player["step"] += 1

        if player["step"] < len(games[game_key]):
            next_q = games[game_key][player["step"]]
            try: name = line_bot_api.get_profile(user_id).display_name
            except: name = "عضو"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{name}\n{next_q}"))
            return
        else:
            try: name = line_bot_api.get_profile(user_id).display_name
            except: name = "عضو"
            trait = score_answers_to_personality(player["answers"])
            final_text = build_final_analysis_text(name, trait)
            line_bot_api.push_message(group_id, TextSendMessage(text=final_text))
            del gs["players"][user_id]
            return

    return

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
