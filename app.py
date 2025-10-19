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

# -------------------------
# Games: 10 games, each 5 questions
# -------------------------
games: typing.Dict[str, typing.List[str]] = {
    "لعبه1": [
        "سؤال 1:\nأنت تمشي في غابة مظلمة، فجأة تسمع صوت خطوات خلفك. ماذا تفعل؟\n1. تلتفت فورًا\n2. تسرع بخطواتك\n3. تتجاهل وتواصل طريقك\n4. تختبئ خلف شجرة",
        "سؤال 2:\nرأيت كوخًا صغيرًا بين الأشجار. ماذا تفعل؟\n1. تقترب وتطرق الباب\n2. تدخل دون تردد\n3. تراقبه من بعيد\n4. تتجاوزه وتكمل طريقك",
        "سؤال 3:\nداخل الكوخ وجدت طاولة عليها مفتاح وورقة. ماذا تأخذ؟\n1. المفتاح\n2. الورقة\n3. كليهما\n4. لا تأخذ شيئًا",
        "سؤال 4:\nخرجت من الكوخ ووجدت طريقين. أي تختار؟\n1. طريق مضيء بالشمس\n2. طريق مظلم لكنه قصير\n3. طريق فيه أزهار\n4. طريق وعر لكنه آمن",
        "سؤال 5:\nسمعت صوت حيوان بري. ماذا تفعل؟\n1. تبتعد فورًا\n2. تختبئ\n3. تحاول معرفة نوع الحيوان\n4. تصرخ طلبًا للمساعدة"
    ],
    "لعبه2": [
        "سؤال 1:\nاستيقظت على جزيرة غامضة لوحدك. ما أول ما تفعله؟\n1. تستكشف المكان\n2. تبحث عن ماء\n3. تصرخ طلبًا للمساعدة\n4. تجلس للتفكير",
        "سؤال 2:\nرأيت أثر أقدام على الرمل. ماذا تفعل؟\n1. تتبعها\n2. تتجاهلها\n3. تراقبها من بعيد\n4. تغطيها بالرمل",
        "سؤال 3:\nوجدت ثمرة غير معروفة. هل تأكلها؟\n1. نعم فورًا\n2. لا أقترب منها\n3. أختبرها أولًا\n4. أحتفظ بها",
        "سؤال 4:\nاقترب الليل ولا مأوى لديك. ماذا تفعل؟\n1. تبني مأوى بسيط\n2. تصعد على شجرة\n3. تشعل نارًا للحماية\n4. تظل مستيقظًا",
        "سؤال 5:\nظهر شخص غريب على الجزيرة. ماذا تفعل؟\n1. تتحدث معه\n2. تختبئ\n3. تراقبه من بعيد\n4. تهاجمه أولًا"
    ],
    "لعبه3": [
        "سؤال 1:\nأنت في مدينة جديدة. أول شيء تفعله؟\n1. تستكشف\n2. تبحث عن مطعم\n3. تبحث عن فندق\n4. تسأل الناس",
        "سؤال 2:\nرأيت إعلانًا غريبًا في الشارع. هل تتابعه؟\n1. نعم بحماس\n2. لا أهتم\n3. ألتقط له صورة\n4. أتجاهله",
        "سؤال 3:\nشخص عرض عليك عملًا غريبًا. هل تقبله؟\n1. نعم\n2. لا\n3. أسأله التفاصيل\n4. أؤجل القرار",
        "سؤال 4:\nأضاع طفل طريقه أمامك. ماذا تفعل؟\n1. تساعده فورًا\n2. تبحث عن والديه\n3. تتصل بالشرطة\n4. تتجاهله",
        "سؤال 5:\nبدأت السماء تمطر. كيف تتصرف؟\n1. تفتح المظلة\n2. تجري لمكان مغلق\n3. تستمتع بالمطر\n4. تكمل طريقك"
    ],
    "لعبه4": [
        "سؤال 1:\nأمامك باب قصر قديم. تدخل؟\n1. أدخل مباشرة\n2. أراقب من الخارج\n3. أدعو شخصًا معي\n4. أعود لاحقًا",
        "سؤال 2:\nوجدت درجًا يؤدي للأسفل. تنزل؟\n1. نعم\n2. لا\n3. تتأكد من الضوء\n4. تبحث عن طريق آخر",
        "سؤال 3:\nرأيت غرفة مليئة بالكتب. ماذا تختار؟\n1. تفتح كتابًا قديمًا\n2. تأخذ واحدًا معك\n3. تتجاهلها\n4. تدعو أحدًا للمساعدة",
        "سؤال 4:\nصوت خطوات قربك، ماذا تفعل؟\n1. تراقب\n2. تختبئ\n3. تصرخ\n4. تتبع الصوت",
        "سؤال 5:\nوجدت صندوقًا مغلقًا. تفتحه؟\n1. نعم بحذر\n2. لا\n3. تبحث عن مفتاح\n4. تتركه"
    ],
    "لعبه5": [
        "سؤال 1:\nاستيقظت على كوكب جديد. أول ما تفعله؟\n1. تستكشف المشهد\n2. تبحث عن مأوى\n3. تجمع عينات\n4. تنتظر إشارات",
        "سؤال 2:\nوجدت نباتًا غريبًا، ماذا تفعل؟\n1. تلمسه\n2. تلتقط صورة\n3. تتجنبه\n4. تأخذ منه عينة",
        "سؤال 3:\nرأيت مخلوقًا صغيرًا. كيف تتصرف؟\n1. تقترب بحذر\n2. تبتعد\n3. تراقبه من بعيد\n4. تتواصل معه",
        "سؤال 4:\nتواجه فصل ليل غريب، ماذا تفعل؟\n1. تبني مأوى\n2. تشعل نارًا\n3. تواصل السير\n4. تستكشف المكان",
        "سؤال 5:\nوجدت جهازًا غريبًا، تضغط عليه؟\n1. نعم\n2. لا\n3. تدرسه أولًا\n4. تحطمه"
    ],
    "لعبه6": [
        "سؤال 1:\nأنت على شاطئ واسع. ماذا تفعل أولاً؟\n1. تسبح\n2. تمشي على الرمال\n3. تبحث عن صدفة\n4. تجلس تتأمل",
        "سؤال 2:\nوجدت قاربًا صغيرًا، تستخدمه؟\n1. نعم\n2. لا\n3. تفتشه أولًا\n4. تنتظر مساعدة",
        "سؤال 3:\nوجدت خريطة بحرية قديمة. ماذا تفعل؟\n1. تتبعها\n2. تتركها\n3. تحفظها\n4. تظهرها للآخرين",
        "سؤال 4:\nشخص في الماء يحتاج مساعدة، ماذا تفعل؟\n1. تنقذه فورًا\n2. تنادي لإنقاذه\n3. تستخدم قاربًا\n4. تبحث عن معدات",
        "سؤال 5:\nرأيت جزيرة صغيرة على الخريطة، تذهب؟\n1. نعم\n2. لا\n3. تجهز نفسك\n4. تنتظر"
    ],
    "لعبه7": [
        "سؤال 1:\nدخلت كهفًا مظلمًا، ماذا تفعل أولاً؟\n1. تشعل مصباحًا\n2. تمشي بحذر\n3. تعود للخارج\n4. تنادي للتأكد من الأمان",
        "سؤال 2:\nوجدت نقوشًا على الجدار، ماذا تفعل؟\n1. تدرسها\n2. تلمسها\n3. تصورها\n4. تتجاهلها",
        "سؤال 3:\nسمعت صدى غريب، ماذا تفعل؟\n1. تتبع الصوت\n2. تبتعد\n3. تصرخ\n4. تنصت بهدوء",
        "سؤال 4:\nرأيت غرفة مليئة بالبلورات، تأخذ قطعة؟\n1. نعم\n2. لا\n3. تلتقط صورة\n4. تسجل موقعها",
        "سؤال 5:\nوجدت مخبأ قديم، تدخل؟\n1. نعم بحذر\n2. لا\n3. تفتح من بعيد\n4. تنتظر"
    ],
    "لعبه8": [
        "سؤال 1:\nأنت في مدرسة قديمة، ماذا تفعل أولاً؟\n1. تدخل صفًا\n2. تسأل عن المكتبة\n3. تبحث عن المدرسين\n4. تتجول",
        "سؤال 2:\nوجدت دفتر ملاحظات غريب، ماذا تفعل؟\n1. تقرأه\n2. تغلقه\n3. تأخذ ملاحظة فقط\n4. تتركه",
        "سؤال 3:\nأستاذ يعرض مسابقة غريبة، تشارك؟\n1. نعم\n2. لا\n3. تسأل عن المكافأة\n4. تؤجل القرار",
        "سؤال 4:\nرأيت مجموعة تتناقش، تنضم؟\n1. نعم\n2. لا\n3. تراقب أولًا\n4. تسأل عن الموضوع",
        "سؤال 5:\nوجدت غرفة سرية، تدخل؟\n1. نعم\n2. لا\n3. تطرق الباب\n4. تبحث عن مفتاح"
    ],
    "لعبه9": [
        "سؤال 1:\nاستيقظت في مستقبل مختلف، ماذا تفعل أولاً؟\n1. تستكشف التكنولوجيا\n2. تبحث عن معلومات\n3. تحاول التواصل مع الآخرين\n4. تراقب بصمت",
        "سؤال 2:\nوجدت جهازًا يمكنه تغيير الذاكرة، تستخدمه؟\n1. نعم\n2. لا\n3. تجرب جزءًا صغيرًا\n4. تدرسه أولًا",
        "سؤال 3:\nرأيت آلة تستطيع السفر عبر الزمن، تذهب؟\n1. نعم\n2. لا\n3. تذهب لمحاولة قصيرة\n4. تتركها",
        "سؤال 4:\nالعالم يحتاج قرارًا مهمًا، تتدخل؟\n1. نعم بقوة\n2. لا تترك الخبراء\n3. تقدم اقتراحًا صغيرًا\n4. تراقب الانتقادات",
        "سؤال 5:\nوجدت فرصة للعودة للحاضر، تفعل؟\n1. أعود\n2. أبقى\n3. أرسل تقريرًا\n4. أنتظر فرصة أفضل"
    ],
    "لعبه10": [
        "سؤال 1:\nدخلت إلى حلم غريب، ماذا تفعل؟\n1. تستكشف المشاهد\n2. تحاول الاستيقاظ\n3. تتبع العناصر الغريبة\n4. تستمتع بالحلم",
        "سؤال 2:\nتحدث مع شخصية من أحلامك، ماذا تقول؟\n1. أسأل عن سبب وجودها\n2. أستمر بالحديث\n3. أتركها تمضي\n4. أطلب نصيحة",
        "سؤال 3:\nوجدت باب داخل الحلم، تفتحه؟\n1. نعم\n2. لا\n3. تراقبه\n4. تتركه",
        "سؤال 4:\nالحلم يتحول إلى كابوس، كيف تواجهه؟\n1. أقاوم بشجاعة\n2. أهرب\n3. أبحث عن مخرج\n4. أصحو من النوم",
        "سؤال 5:\nاستيقظت وعندك تذكّر غريب، تفعل؟\n1. تدون الأفكار\n2. تتجاهلها\n3. تشاركها مع أحد\n4. تبحث عن معنى"
    ]
}

# -----------------------------
# Default personality scoring
# -----------------------------
KEYWORDS = {
    "قيادية": [r"\bتدخل\b", r"\bتقترب\b", r"\bتسرع\b", r"\bتركض\b", r"\bأهاجم\b", r"\bأقبل\b"],
    "تعبيرية": [r"\bأتحدث\b", r"\bأتواصل\b", r"\bأشارك\b", r"\bألوّح\b", r"\bأضحك\b"],
    "تحليلية": [r"\bأبحث\b", r"\bأخطط\b", r"\bأفحص\b", r"\bأدرس\b", r"\bأقيس\b"],
    "داعمة": [r"\bأساعد\b", r"\bأساند\b", r"\bأنتظر\b", r"\bأعتني\b", r"\bأدعم\b"]
}

DESCRIPTIONS = {
    "قيادية": "الشخصية القيادية: استقلالية، عملية، تحب السيطرة.",
    "تعبيرية": "الشخصية التعبيرية: اجتماعية، ودودة، محبة للتواصل.",
    "تحليلية": "الشخصية التحليلية: عقلانية، دقيقة، تعتمد المنطق.",
    "داعمة": "الشخصية الداعمة: هادئة، مساندة، تفضل الاستقرار."
}

# -----------------------------
# Group sessions structure
# -----------------------------
group_sessions: typing.Dict[str, typing.Dict] = {}

# -----------------------------
# Helpers
# -----------------------------
def extract_option_text(game_key: str, q_index: int, chosen: int) -> str:
    try:
        q = games[game_key][q_index]
        opts = re.findall(r"\n\s*\d+\s*[\.\)\-:]\s*([^\n]+)", q)
        if opts and 1 <= chosen <= len(opts):
            return opts[chosen-1].strip()
    except Exception:
        pass
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
            if matched: break
        if not matched:
            if chosen_num == 1: scores["قيادية"] +=1
            elif chosen_num == 2: scores["تحليلية"] +=1
            elif chosen_num == 3: scores["تعبيرية"] +=1
            elif chosen_num == 4: scores["داعمة"] +=1
    sorted_by_score = sorted(scores.items(), key=lambda x: (-x[1], ["قيادية","تعبيرية","تحليلية","داعمة"].index(x[0])))
    top_trait, top_score = sorted_by_score[0]
    return top_trait if top_score>0 else "تعبيرية"

def build_final_analysis_text(name: str, trait_key: str) -> str:
    desc = DESCRIPTIONS.get(trait_key, "")
    return f"{name}\n{desc}"

def get_display_name(source) -> str:
    try:
        src_type = getattr(source, "type", None)
        if src_type == "group":
            return line_bot_api.get_group_member_profile(source.group_id, source.user_id).display_name
        else:
            return line_bot_api.get_profile(source.user_id).display_name
    except Exception:
        return "عضو"

# -----------------------------
# LINE webhook
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

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    source = event.source
    user_id = source.user_id
    group_id = getattr(source, "group_id", None)
    text = getattr(event.message, "text", "").strip()

    if text == "مساعدة":
        help_text = (
            "أوامر البوت:\n\n"
            "سؤال → يعطيك سؤال عشوائي.\n\n"
            "تحدي → يعطيك تحدي.\n\n"
            "اعتراف → يعطيك اعتراف.\n\n"
            "اسئلة شخصية → سؤال شخصي عشوائي.\n\n"
            "لعبهX → يبدأ لعبة جماعية (X من 1 إلى 10).\n"
            "كل عضو يرسل 'ابدأ' للانضمام ثم يجيب بالأرقام 1 إلى 4.\n"
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=help_text))
        return

    if group_id and text.startswith("لعبه"):
        if text not in games:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="اكتب لعبه1 حتى لعبه10 لبدء لعبة."))
            return
        group_sessions[group_id] = {"game": text, "players": {}, "state": "joining"}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"تم بدء الجلسة: {text}\nكل عضو يرسل 'ابدأ' للانضمام."))
        return

    if group_id and text == "ابدأ":
        gs = group_sessions.get(group_id)
        if not gs or gs.get("state") != "joining": return
        players = gs["players"]
        if user_id not in players:
            display_name = get_display_name(source)
            players[user_id] = {"name": display_name, "answers":[],"current_q":0}
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{display_name} انضم للعبة."))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="أنت بالفعل في اللعبة."))
        return

    if group_id and text in ["1","2","3","4"]:
        gs = group_sessions.get(group_id)
        if not gs or gs.get("state") != "joining": return
        players = gs["players"]
        if user_id not in players: return
        player = players[user_id]
        chosen_num = int(text)
        q_index = player["current_q"]
        chosen_text = extract_option_text(gs["game"], q_index, chosen_num)
        player["answers"].append((q_index, chosen_num, chosen_text))
        player["current_q"] += 1
        if player["current_q"] < len(games[gs["game"]]):
            next_q_text = games[gs["game"]][player["current_q"]]
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{player['name']}، {next_q_text}"))
        else:
            trait = score_answers_to_personality(player["answers"])
            final_text = build_final_analysis_text(player["name"], trait)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{player['name']} انتهى من اللعبة.\n{final_text}\nوداعاً"))
        return

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
