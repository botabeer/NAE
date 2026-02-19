import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    FlexMessage, FlexContainer,
    QuickReply, QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler       = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ═══════════════════════════ THEME ═══════════════════════════════════
# Monochrome — elegant, clean, easy on the eyes
C = {
    'white':   '#FFFFFF',
    'off':     '#F8F8F8',
    'light':   '#EFEFEF',
    'mid':     '#C8C8C8',
    'soft':    '#888888',
    'dark':    '#444444',
    'black':   '#111111',
    'border':  '#E0E0E0',
}

# ═══════════════════════════ CONTENT MANAGER ═════════════════════════
class ContentManager:
    def __init__(self):
        self.files      = {}
        self.mention    = []
        self.games      = []
        self.quotes     = []
        self.situations = []
        self.riddles    = []
        self.results    = {}
        self.religion   = []
        self.stories    = []
        self.scenarios  = []
        self.choices    = []
        self.never      = []
        self.motivation = []
        self.philosophy = []
        self.used        = {}
        self.game_state  = {}   # uid -> {game, q, answers}
        self.riddle_state= {}   # uid -> {idx}
        self.deen_state  = {}   # uid -> {idx}

    def _lines(self, f):
        if not os.path.exists(f): logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, encoding='utf-8') as fh:
                return [l.strip() for l in fh if l.strip()]
        except Exception as e:
            logger.error(f"{f}: {e}"); return []

    def _json(self, f, default=None):
        d = default if default is not None else {}
        if not os.path.exists(f): logger.warning(f"Missing: {f}"); return d
        try:
            with open(f, encoding='utf-8') as fh:
                return json.load(fh)
        except Exception as e:
            logger.error(f"{f}: {e}"); return d

    def _stories(self, f):
        if not os.path.exists(f): logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, encoding='utf-8') as fh:
                raw = fh.read()
            return [p.strip() for p in raw.split("───") if p.strip()]
        except Exception as e:
            logger.error(f"{f}: {e}"); return []

    def initialize(self):
        self.files = {
            "سؤال":   self._lines("questions.txt"),
            "تحدي":   self._lines("challenges.txt"),
            "اعتراف": self._lines("confessions.txt"),
        }
        self.mention    = self._lines("more_questions.txt")
        self.situations = self._lines("situations.txt")
        self.quotes     = self._json("quotes.json", default=[])
        self.riddles    = self._json("riddles.json", default=[])
        self.results    = self._json("detailed_results.json")
        self.religion   = self._json("religion.json", default=[])
        self.stories    = self._stories("stories.txt")
        self.scenarios  = self._lines("scenarios.txt")
        self.choices    = self._lines("choices.txt")
        self.never      = self._lines("never.txt")
        self.motivation = self._lines("motivation.txt")

        raw = self._json("personality_games.json")
        self.games = [raw[k] for k in sorted(raw.keys())] if isinstance(raw, dict) else []

        phil = self._json("philosophical_questions.json", default=[])
        self.philosophy = [p["question"] for p in phil if "question" in p]

        keys = ["سؤال","تحدي","اعتراف","منشن","موقف","اقتباس","لغز","دين",
                "قصة","فلسفة","لو كنت","أيهما أصعب","أنا لم","تحفيز"]
        self.used = {k: [] for k in keys}

        logger.info(f"games={len(self.games)} riddles={len(self.riddles)} "
                    f"religion={len(self.religion)} stories={len(self.stories)}")

    def get_random(self, key, data):
        if not data: return None
        used = self.used.setdefault(key, [])
        if len(used) >= len(data): used.clear()
        avail = [i for i in range(len(data)) if i not in used]
        idx = random.choice(avail)
        used.append(idx)
        return data[idx]

cm = ContentManager()
cm.initialize()

# ═══════════════════════════ MENUS ═══════════════════════════════════
MENU_A = ["سؤال","منشن","اعتراف","تحدي","موقف","اقتباس",
          "تحليل","لغز","دين","قصة","فلسفة","لو كنت","المزيد"]
MENU_B = ["أيهما أصعب","أنا لم","تحفيز",
          "سؤال","منشن","تحدي","موقف","لغز","دين","تحليل","مساعدة","بداية","رجوع"]

def make_menu(secondary=False):
    labels = MENU_B if secondary else MENU_A
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=l, text=l))
        for l in labels
    ])

# ═══════════════════════════ FLEX HELPERS ════════════════════════════
def bubble(body_contents, footer=None):
    d = {
        "type": "bubble",
        "direction": "rtl",
        "body": {
            "type": "box", "layout": "vertical",
            "backgroundColor": C['white'],
            "paddingAll": "20px",
            "contents": body_contents
        }
    }
    if footer:
        d["footer"] = {
            "type": "box", "layout": "vertical",
            "backgroundColor": C['off'],
            "paddingAll": "12px",
            "contents": footer
        }
    return FlexMessage(
        alt_text="بوت عناد المالكي",
        contents=FlexContainer.from_dict(d)
    )

def box_v(contents, **kw):
    return {"type": "box", "layout": "vertical", "contents": contents, **kw}

def box_h(contents, **kw):
    return {"type": "box", "layout": "horizontal", "contents": contents, **kw}

def txt(t, size="md", weight="regular", color=None, align="start", wrap=True, **kw):
    d = {"type": "text", "text": str(t), "size": size,
         "weight": weight, "wrap": wrap, "align": align}
    if color: d["color"] = color
    return {**d, **kw}

def sep(color=None):
    return {"type": "separator", "margin": "md", "color": color or C['border']}

def btn(label, msg, style="secondary"):
    # style: primary=black fill, secondary=outline
    if style == "primary":
        return {
            "type": "button", "style": "primary",
            "color": C['black'], "margin": "sm",
            "action": {"type": "message", "label": label, "text": msg}
        }
    return {
        "type": "button", "style": "secondary",
        "color": C['light'], "margin": "sm",
        "action": {"type": "message", "label": label, "text": msg}
    }

def card(contents):
    return box_v(contents,
        backgroundColor=C['off'], cornerRadius="12px",
        paddingAll="16px", margin="md")

# ═══════════════════════════ WELCOME FLEX ════════════════════════════
def welcome_flex():
    return bubble([
        txt("بوت عناد المالكي", size="xl", weight="bold",
            color=C['black'], align="center"),
        sep(),
        box_v([
            txt("مرحباً بك", size="sm", color=C['soft'], align="center"),
        ], margin="md"),
        sep(),
        txt("الاوامر المتاحة", size="sm", weight="bold",
            color=C['dark'], margin="lg"),
        box_h([
            btn("سؤال",    "سؤال"),
            btn("تحدي",    "تحدي"),
            btn("اعتراف",  "اعتراف"),
        ], margin="sm", spacing="sm"),
        box_h([
            btn("منشن",    "منشن"),
            btn("موقف",    "موقف"),
            btn("اقتباس",  "اقتباس"),
        ], margin="sm", spacing="sm"),
        box_h([
            btn("قصة",     "قصة"),
            btn("فلسفة",   "فلسفة"),
            btn("تحفيز",   "تحفيز"),
        ], margin="sm", spacing="sm"),
        box_h([
            btn("لو كنت",  "لو كنت"),
            btn("أيهما أصعب", "أيهما أصعب"),
        ], margin="sm", spacing="sm"),
        box_h([
            btn("أنا لم",  "أنا لم"),
            btn("لغز",     "لغز"),
            btn("دين",     "دين"),
        ], margin="sm", spacing="sm"),
        box_v([btn("تحليل الشخصية", "تحليل", style="primary")],
              margin="sm"),
        sep(),
        box_h([
            btn("مساعدة", "مساعدة"),
        ], margin="sm"),
    ],
    footer=[
        txt("تم إنشاء هذا البوت بواسطة عبير الدوسري",
            size="xs", color=C['soft'], align="center")
    ])

# ═══════════════════════════ HELP FLEX ═══════════════════════════════
def help_flex():
    commands = [
        ("سؤال",         "سؤال للنقاش في القروب"),
        ("منشن",         "سؤال تذكر فيه شخص"),
        ("اعتراف",       "اعتراف للمجموعة"),
        ("تحدي",         "تحدي لأحد الأعضاء"),
        ("موقف",         "موقف محرج أو مضحك"),
        ("اقتباس",       "اقتباس ملهم"),
        ("قصة",          "قصة قصيرة ملهمة"),
        ("فلسفة",        "سؤال فلسفي للنقاش"),
        ("لو كنت",       "سيناريو افتراضي"),
        ("أيهما أصعب",   "خيار صعب بين اثنين"),
        ("أنا لم",       "اعتراف شخصي صادق"),
        ("تحفيز",        "رسالة تحفيزية"),
        ("لغز",          "لغز مع تلميح وجواب"),
        ("دين",          "سؤال ديني مع تلميح وجواب"),
        ("تحليل",        "تحليل شخصيتك"),
    ]
    rows = []
    for cmd, desc in commands:
        rows.append(box_h([
            txt(cmd,  size="sm", weight="bold", color=C['black'], flex=2),
            txt(desc, size="sm", color=C['soft'], flex=5),
        ], margin="sm"))
        rows.append(sep())

    return bubble(
        [txt("دليل الأوامر", size="lg", weight="bold",
             color=C['black'], align="center"),
         sep()] + rows[:-1],
        footer=[
            txt("تم إنشاء هذا البوت بواسطة عبير الدوسري",
                size="xs", color=C['soft'], align="center")
        ]
    )

# ═══════════════════════════ GAME FLEX ═══════════════════════════════
def games_list_flex():
    btns = [btn(f"{i+1}. {g.get('title','تحليل')}", str(i+1), style="primary")
            for i, g in enumerate(cm.games)]
    return bubble(
        [txt("تحليل الشخصية", size="lg", weight="bold",
             color=C['black'], align="center"),
         sep(),
         txt("اختر التحليل المناسب لك", size="sm",
             color=C['soft'], align="center", margin="sm"),
         box_v(btns, margin="md")]
    )

def question_flex(title, q, progress):
    options = [btn(f"{k}. {v}", f"game_ans_{k}")
               for k, v in q['options'].items()]
    return bubble([
        box_h([
            txt(title,    size="sm", weight="bold", color=C['black'], flex=4),
            txt(progress, size="sm", color=C['soft'],  flex=1, align="end"),
        ]),
        card([txt(q['question'], color=C['dark'], size="md")]),
        box_v(options, margin="md"),
    ])

def result_flex(t):
    return bubble([
        txt("نتيجة التحليل", size="lg", weight="bold",
            color=C['black'], align="center"),
        sep(),
        card([txt(t, color=C['dark'])]),
        box_v([btn("تحليل جديد", "تحليل", style="primary")], margin="md"),
    ],
    footer=[txt("تم إنشاء هذا البوت بواسطة عبير الدوسري",
                size="xs", color=C['soft'], align="center")])

# ═══════════════════════════ RIDDLE FLEX ═════════════════════════════
def riddle_flex(r, num, total):
    return bubble([
        box_h([
            txt("لغز", size="sm", weight="bold", color=C['black'], flex=4),
            txt(f"{num}/{total}", size="sm", color=C['soft'], flex=1, align="end"),
        ]),
        card([txt(r['question'], color=C['dark'])]),
        box_h([
            btn("تلميح",   "تلميح_لغز"),
            btn("الجواب",  "جواب_لغز"),
            btn("التالي","لغز", style="primary"),
        ], margin="md", spacing="sm"),
    ])

def riddle_hint_flex(hint, question):
    return bubble([
        txt("تلميح", size="sm", weight="bold", color=C['black']),
        card([txt(hint, color=C['soft'], size="sm")]),
        box_v([txt(question, size="xs", color=C['mid'])], margin="sm"),
        box_h([
            btn("الجواب",   "جواب_لغز"),
            btn("التالي", "لغز", style="primary"),
        ], margin="md", spacing="sm"),
    ])

def riddle_answer_flex(answer, question):
    return bubble([
        txt("الجواب", size="sm", weight="bold", color=C['black']),
        card([txt(answer, color=C['dark'], weight="bold")]),
        box_v([txt(question, size="xs", color=C['mid'])], margin="sm"),
        box_v([btn("التالي", "لغز", style="primary")], margin="md"),
    ])

# ═══════════════════════════ DEEN FLEX ═══════════════════════════════
def deen_flex(item, num, total):
    return bubble([
        box_h([
            txt("سؤال ديني", size="sm", weight="bold", color=C['black'], flex=4),
            txt(f"{num}/{total}", size="sm", color=C['soft'], flex=1, align="end"),
        ]),
        card([txt(item['question'], color=C['dark'])]),
        box_h([
            btn("تلميح",     "تلميح_دين"),
            btn("الجواب",    "جواب_دين"),
            btn("سؤال جديد", "دين", style="primary"),
        ], margin="md", spacing="sm"),
    ])

def deen_hint_flex(hint, question):
    return bubble([
        txt("تلميح", size="sm", weight="bold", color=C['black']),
        card([txt(hint, color=C['soft'], size="sm")]),
        box_v([txt(question, size="xs", color=C['mid'])], margin="sm"),
        box_h([
            btn("الجواب",    "جواب_دين"),
            btn("سؤال جديد", "دين", style="primary"),
        ], margin="md", spacing="sm"),
    ])

def deen_answer_flex(answer, question):
    return bubble([
        txt("الجواب", size="sm", weight="bold", color=C['black']),
        card([txt(answer, color=C['dark'], weight="bold")]),
        box_v([txt(question, size="xs", color=C['mid'])], margin="sm"),
        box_v([btn("سؤال جديد", "دين", style="primary")], margin="md"),
    ])

# ═══════════════════════════ HELPERS ═════════════════════════════════
def _txt(t):
    return TextMessage(text=str(t))

def calculate_result(answers, game_idx):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        # answers are stored as "أ"/"ب"/"ج" directly
        if a in counts:
            counts[a] += 1
    if not any(counts.values()):
        return "شخصيتك مميزة ومختلفة"
    max_val  = max(counts.values())
    top_keys = [k for k, v in counts.items() if v == max_val]
    key = top_keys[0] if len(top_keys) == 1 else \
          next((a for a in answers if a in top_keys), top_keys[0])
    return cm.results.get(f"لعبة{game_idx + 1}", {}).get(key, "شخصيتك مميزة ومختلفة")

def reply(token, msgs, secondary=False):
    if not msgs: return
    msgs[-1].quick_reply = make_menu(secondary)
    try:
        with ApiClient(configuration) as api:
            MessagingApi(api).reply_message(
                ReplyMessageRequest(reply_token=token, messages=msgs)
            )
    except Exception as e:
        logger.error(f"reply error: {e}")

# ═══════════════════════════ ROUTES ══════════════════════════════════
@app.route("/")
def home(): return "OK"

@app.route("/health")
def health(): return {"ok": True}

@app.route("/callback", methods=["POST"])
def callback():
    sig  = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, sig)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ═══════════════════════════ HANDLER ═════════════════════════════════
@handler.add(MessageEvent, message=TextMessageContent)
def handle(event):
    uid  = event.source.user_id
    text = event.message.text.strip()

    # ─── تحليل: answer in progress ───────────────────────────────────
    if uid in cm.game_state:
        # buttons send "game_ans_أ" etc.
        if text.startswith("game_ans_"):
            ans = text.replace("game_ans_", "").strip()
        elif text in ["أ", "ب", "ج"]:
            ans = text
        else:
            ans = None

        if ans not in ["أ", "ب", "ج"]:
            reply(event.reply_token, [_txt("اختر إجابة من الأزرار")]); return

        state  = cm.game_state[uid]
        state["answers"].append(ans)
        game   = cm.games[state["game"]]
        q_next = state["q"] + 1

        if q_next < len(game["questions"]):
            state["q"] = q_next
            reply(event.reply_token, [
                question_flex(game["title"], game["questions"][q_next],
                              f"{q_next+1}/{len(game['questions'])}")
            ])
        else:
            res = calculate_result(state["answers"], state["game"])
            del cm.game_state[uid]
            reply(event.reply_token, [result_flex(res)])
        return

    # ─── لغز: in progress ────────────────────────────────────────────
    if uid in cm.riddle_state:
        rs     = cm.riddle_state[uid]
        riddle = cm.riddles[rs["idx"]]
        if text == "تلميح_لغز":
            reply(event.reply_token,
                  [riddle_hint_flex(riddle.get("hint","لا يوجد تلميح"), riddle["question"])]); return
        if text == "جواب_لغز":
            del cm.riddle_state[uid]
            reply(event.reply_token,
                  [riddle_answer_flex(riddle["answer"], riddle["question"])]); return
        if text != "لغز":
            reply(event.reply_token, [_txt('اضغط "تلميح" أو "الجواب"')]); return
        del cm.riddle_state[uid]

    # ─── دين: in progress ────────────────────────────────────────────
    if uid in cm.deen_state:
        ds   = cm.deen_state[uid]
        item = cm.religion[ds["idx"]]
        if text == "تلميح_دين":
            reply(event.reply_token,
                  [deen_hint_flex(item.get("hint","لا يوجد تلميح"), item["question"])]); return
        if text == "جواب_دين":
            del cm.deen_state[uid]
            reply(event.reply_token,
                  [deen_answer_flex(item["answer"], item["question"])]); return
        if text != "دين":
            reply(event.reply_token, [_txt('اضغط "تلميح" أو "الجواب"')]); return
        del cm.deen_state[uid]

    # ─── تحليل: choose game by number ────────────────────────────────
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(cm.games):
            cm.game_state[uid] = {"game": idx, "q": 0, "answers": []}
            g = cm.games[idx]
            reply(event.reply_token, [
                question_flex(g["title"], g["questions"][0],
                              f"1/{len(g['questions'])}")
            ])
        return

    # ─── بداية / مساعدة ──────────────────────────────────────────────
    if text in ["بداية", "ابدأ", "start"]:
        reply(event.reply_token, [welcome_flex()]); return

    if text == "مساعدة":
        reply(event.reply_token, [help_flex()]); return

    if text == "المزيد":
        reply(event.reply_token, [_txt("اختر:")], secondary=True); return

    if text == "رجوع":
        reply(event.reply_token, [_txt("تفضل:")], secondary=False); return

    # ─── تحليل ───────────────────────────────────────────────────────
    if text == "تحليل":
        reply(event.reply_token, [games_list_flex()]); return

    # ─── لغز ─────────────────────────────────────────────────────────
    if text == "لغز":
        if not cm.riddles:
            reply(event.reply_token, [_txt("لا تتوفر ألغاز")]); return
        r   = cm.get_random("لغز", cm.riddles)
        idx = cm.riddles.index(r)
        cm.riddle_state[uid] = {"idx": idx}
        reply(event.reply_token, [riddle_flex(r, idx+1, len(cm.riddles))]); return

    # ─── دين ─────────────────────────────────────────────────────────
    if text == "دين":
        if not cm.religion:
            reply(event.reply_token, [_txt("لا تتوفر أسئلة")]); return
        r   = cm.get_random("دين", cm.religion)
        idx = cm.religion.index(r)
        cm.deen_state[uid] = {"idx": idx}
        reply(event.reply_token, [deen_flex(r, idx+1, len(cm.religion))]); return

    # ─── نص عادي ─────────────────────────────────────────────────────
    plain = {
        "قصة":         cm.stories,
        "فلسفة":       cm.philosophy,
        "لو كنت":      cm.scenarios,
        "أيهما أصعب": cm.choices,
        "أنا لم":      cm.never,
        "تحفيز":       cm.motivation,
    }
    if text in plain:
        item = cm.get_random(text, plain[text])
        reply(event.reply_token, [_txt(item or "—")]); return

    # ─── محتوى أصلي ──────────────────────────────────────────────────
    original = {
        "سؤال":   ("سؤال",   cm.files["سؤال"]),
        "تحدي":   ("تحدي",   cm.files["تحدي"]),
        "اعتراف": ("اعتراف", cm.files["اعتراف"]),
        "منشن":   ("منشن",   cm.mention),
        "موقف":   ("موقف",   cm.situations),
        "اقتباس": ("اقتباس", cm.quotes),
    }
    if text in original:
        cat, data = original[text]
        item = cm.get_random(cat, data)
        if text == "اقتباس" and isinstance(item, dict):
            author = item.get("author","").strip()
            msg    = item.get("text","—")
            if author: msg = f"{msg}\n\n— {author}"
        else:
            msg = item if isinstance(item, str) else "—"
        reply(event.reply_token, [_txt(msg or "—")])

# ═══════════════════════════ KEEP ALIVE ══════════════════════════════
def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL","")
    if url and not url.startswith("http"): url = "https://" + url
    while True:
        try:
            if url: requests.get(url+"/health", timeout=5)
        except Exception: pass
        time.sleep(600)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL"):
        threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",5000)))
