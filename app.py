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

app  = Flask(__name__)
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler       = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ═══════════════════════════ THEME ═══════════════════════════════════
# Black / White / Grey — elegant, unified, easy on the eyes
C = {
    'bg':       '#FFFFFF',   # pure white background
    'card':     '#F5F5F5',   # light grey card
    'stroke':   '#E0E0E0',   # border grey
    'muted':    '#BDBDBD',   # muted grey
    'subtle':   '#9E9E9E',   # subtle text
    'body':     '#424242',   # body text
    'strong':   '#212121',   # strong text / near black
    'btn_light':'#EEEEEE',   # light grey button
    'btn_mid':  '#757575',   # mid grey button
    'btn_dark': '#212121',   # dark / black button
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
        self.game_state  = {}
        self.riddle_state= {}
        self.deen_state  = {}

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
            with open(f, encoding='utf-8') as fh: return json.load(fh)
        except Exception as e:
            logger.error(f"{f}: {e}"); return d

    def _stories(self, f):
        if not os.path.exists(f): logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, encoding='utf-8') as fh: raw = fh.read()
            return [p.strip() for p in raw.split("───") if p.strip()]
        except Exception as e:
            logger.error(f"{f}: {e}"); return []

    def _quotes(self, f):
        """Load quotes — supports both JSON array and plain text (one per line)."""
        if not os.path.exists(f):
            logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, encoding='utf-8') as fh:
                raw = fh.read().strip()
            # Try JSON first
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    result = []
                    for item in data:
                        if isinstance(item, dict):
                            result.append(item)
                        elif isinstance(item, str) and item.strip():
                            result.append({"text": item.strip(), "author": ""})
                    return result
            except json.JSONDecodeError:
                pass
            # Plain text fallback: each line is a quote
            # Format: "quote text (author)" or just "quote text"
            result = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                # Extract author if in parentheses at the end
                if line.endswith(')') and '(' in line:
                    idx = line.rfind('(')
                    author = line[idx+1:-1].strip()
                    text   = line[:idx].strip()
                    result.append({"text": text, "author": author})
                else:
                    result.append({"text": line, "author": ""})
            return result
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
        self.quotes     = self._quotes("quotes.txt")
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
                    f"religion={len(self.religion)} stories={len(self.stories)} "
                    f"quotes={len(self.quotes)}")

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
          "سؤال","منشن","تحدي","لغز","دين","تحليل","مساعدة","بداية","موقف","رجوع"]

def make_menu(secondary=False):
    labels = MENU_B if secondary else MENU_A
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=l, text=l)) for l in labels
    ])

# ═══════════════════════════ FLEX CORE ═══════════════════════════════
def flex_msg(body_contents, footer_contents=None):
    body = {
        "type": "box", "layout": "vertical",
        "backgroundColor": C['bg'],
        "paddingAll": "24px",
        "contents": body_contents
    }
    d = {"type": "bubble", "direction": "rtl", "body": body}
    if footer_contents:
        d["footer"] = {
            "type": "box", "layout": "vertical",
            "backgroundColor": C['card'],
            "paddingAll": "14px",
            "contents": footer_contents
        }
    return FlexMessage(
        alt_text="بوت عناد المالكي",
        contents=FlexContainer.from_dict(d)
    )

def vbox(contents, **kw):
    return {"type": "box", "layout": "vertical", "contents": contents, **kw}

def hbox(contents, **kw):
    return {"type": "box", "layout": "horizontal", "contents": contents, **kw}

def t(text, size="md", weight="regular", color=None, align="start", **kw):
    d = {"type": "text", "text": str(text), "size": size,
         "weight": weight, "wrap": True, "align": align}
    if color: d["color"] = color
    return {**d, **kw}

def sep():
    return {"type": "separator", "margin": "lg", "color": C['stroke']}

def spacer(size="md"):
    return {"type": "box", "layout": "vertical", "contents": [],
            "height": "1px" if size == "sm" else "8px" if size == "md" else "16px",
            "margin": "none"}

def card_box(contents, **kw):
    return vbox(contents,
        backgroundColor=C['card'],
        cornerRadius="10px",
        paddingAll="16px",
        margin="lg",
        **kw)

# ── Button helpers — unified B&W palette ─────────────────────────────
def btn_light(label, msg):
    """Light grey button — unified for all actions"""
    return {
        "type": "button", "style": "secondary",
        "color": C['btn_light'], "margin": "sm", "height": "sm",
        "action": {"type": "message", "label": label, "text": msg}
    }

# All buttons use the same light grey style
btn_dark  = btn_light
btn_mid   = btn_light
btn_soft  = btn_light
btn_solid = btn_light
btn_ghost = btn_light

def footer_credit():
    return [t("تم انشاء هذا البوت بواسطة عبير الدوسري",
              size="xs", color=C['subtle'], align="center")]

# ═══════════════════════════ WELCOME FLEX ════════════════════════════
def welcome_flex():
    return flex_msg([
        t("بوت عناد المالكي", size="xl", weight="bold",
          color=C['strong'], align="center"),
        vbox([], height="4px"),
        t("يمكن استخدام البوت بالخاص و القروبات", size="sm", color=C['subtle'], align="center"),
        sep(),

        t("اسئلة وتفاعل", size="xs", color=C['subtle'], margin="lg"),
        hbox([
            btn_light("سؤال",    "سؤال"),
            btn_light("منشن",    "منشن"),
            btn_light("اعتراف",  "اعتراف"),
        ], margin="sm", spacing="sm"),
        hbox([
            btn_light("تحدي",    "تحدي"),
            btn_light("موقف",    "موقف"),
            btn_light("اقتباس",  "اقتباس"),
        ], margin="sm", spacing="sm"),

        t("نقاش وتفكير", size="xs", color=C['subtle'], margin="lg"),
        hbox([
            btn_light("فلسفة",        "فلسفة"),
            btn_light("لو كنت",       "لو كنت"),
            btn_light("ايهما اصعب",   "أيهما أصعب"),
        ], margin="sm", spacing="sm"),
        hbox([
            btn_light("انا لم",   "أنا لم"),
            btn_light("قصة",      "قصة"),
            btn_light("تحفيز",    "تحفيز"),
        ], margin="sm", spacing="sm"),

        t("العاب ومعرفة", size="xs", color=C['subtle'], margin="lg"),
        hbox([
            btn_light("لغز",  "لغز"),
            btn_light("دين",  "دين"),
        ], margin="sm", spacing="sm"),
        vbox([btn_dark("تحليل الشخصية", "تحليل")], margin="sm"),

        sep(),
        hbox([
            btn_light("مساعدة", "مساعدة"),
        ], margin="sm"),
    ],
    footer_contents=footer_credit())

# ═══════════════════════════ HELP FLEX ═══════════════════════════════
def help_flex():
    cmds = [
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
        ("تحليل",        "تحليل الشخصية"),
    ]
    rows = []
    for cmd, desc in cmds:
        rows.append(
            hbox([
                t(cmd,  size="sm", weight="bold", color=C['strong'], flex=3),
                t(desc, size="sm", color=C['subtle'], flex=7),
            ], margin="sm")
        )
        rows.append({"type": "separator", "margin": "sm", "color": C['stroke']})

    return flex_msg(
        [t("دليل الأوامر", size="lg", weight="bold",
           color=C['strong'], align="center"), sep()] + rows[:-1],
        footer_contents=footer_credit()
    )

# ═══════════════════════════ GAME FLEX ═══════════════════════════════
def games_list_flex():
    btns = [btn_dark(f"{i+1}. {g.get('title','تحليل')}", str(i+1))
            for i, g in enumerate(cm.games)]
    return flex_msg([
        t("تحليل الشخصية", size="lg", weight="bold",
          color=C['strong'], align="center"),
        sep(),
        t("اختر التحليل المناسب لك", size="sm",
          color=C['subtle'], align="center", margin="sm"),
        vbox(btns, margin="lg"),
    ])

def question_flex(title, q, progress):
    opts = [btn_light(f"{k}. {v}", k) for k, v in q['options'].items()]
    return flex_msg([
        hbox([
            t(title,    size="sm", weight="bold", color=C['body'], flex=5),
            t(progress, size="sm", color=C['subtle'], flex=1, align="end"),
        ]),
        card_box([t(q['question'], color=C['body'])]),
        vbox(opts, margin="lg"),
    ])

def result_flex(result_text):
    return flex_msg([
        t("نتيجة التحليل", size="lg", weight="bold",
          color=C['strong'], align="center"),
        sep(),
        card_box([t(result_text, color=C['body'])]),
        vbox([btn_dark("تحليل جديد", "تحليل")], margin="lg"),
    ],
    footer_contents=footer_credit())

# ═══════════════════════════ RIDDLE FLEX ═════════════════════════════
def riddle_flex(r, num, total):
    return flex_msg([
        hbox([
            t("لغز", size="sm", weight="bold", color=C['body'], flex=4),
            t(f"{num}/{total}", size="sm", color=C['subtle'], flex=1, align="end"),
        ]),
        card_box([t(r['question'], color=C['body'])]),
        hbox([
            btn_light("تلميح",  "تلميح"),
            btn_light("جواب",   "جواب"),
            btn_dark("التالي",  "لغز"),
        ], margin="lg", spacing="sm"),
    ])

def riddle_hint_flex(hint, question):
    return flex_msg([
        t("تلميح", size="sm", weight="bold", color=C['body']),
        card_box([t(hint, color=C['subtle'])]),
        vbox([t(question, size="xs", color=C['muted'])], margin="sm"),
        hbox([
            btn_light("جواب",  "جواب"),
            btn_dark("التالي", "لغز"),
        ], margin="lg", spacing="sm"),
    ])

def riddle_answer_flex(answer, question):
    return flex_msg([
        t("الجواب", size="sm", weight="bold", color=C['body']),
        card_box([t(answer, color=C['strong'], weight="bold")]),
        vbox([t(question, size="xs", color=C['muted'])], margin="sm"),
        vbox([btn_dark("التالي", "لغز")], margin="lg"),
    ])

# ═══════════════════════════ DEEN FLEX ═══════════════════════════════
def deen_flex(item, num, total):
    return flex_msg([
        hbox([
            t("سؤال ديني", size="sm", weight="bold", color=C['body'], flex=5),
            t(f"{num}/{total}", size="sm", color=C['subtle'], flex=1, align="end"),
        ]),
        card_box([t(item['question'], color=C['body'])]),
        hbox([
            btn_light("تلميح",  "تلميح"),
            btn_light("جواب",   "جواب"),
            btn_dark("التالي",  "دين"),
        ], margin="lg", spacing="sm"),
    ])

def deen_hint_flex(hint, question):
    return flex_msg([
        t("تلميح", size="sm", weight="bold", color=C['body']),
        card_box([t(hint, color=C['subtle'])]),
        vbox([t(question, size="xs", color=C['muted'])], margin="sm"),
        hbox([
            btn_light("جواب",  "جواب"),
            btn_dark("التالي", "دين"),
        ], margin="lg", spacing="sm"),
    ])

def deen_answer_flex(answer, question):
    return flex_msg([
        t("الجواب", size="sm", weight="bold", color=C['body']),
        card_box([t(answer, color=C['strong'], weight="bold")]),
        vbox([t(question, size="xs", color=C['muted'])], margin="sm"),
        vbox([btn_dark("التالي", "دين")], margin="lg"),
    ])

# ═══════════════════════════ HELPERS ═════════════════════════════════
def _txt(text):
    return TextMessage(text=str(text))

def calculate_result(answers, game_idx):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        if a in counts: counts[a] += 1
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

# ═══════════════════════════ MAIN HANDLER ════════════════════════════
@handler.add(MessageEvent, message=TextMessageContent)
def handle(event):
    uid  = event.source.user_id
    text = event.message.text.strip()

    # ── PRIORITY 1: Game in progress ─────────────────────────────────
    if uid in cm.game_state:
        state = cm.game_state[uid]
        if text in ["أ", "ب", "ج"]:
            state["answers"].append(text)
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
        else:
            game = cm.games[state["game"]]
            q    = state["q"]
            reply(event.reply_token, [
                question_flex(game["title"], game["questions"][q],
                              f"{q+1}/{len(game['questions'])}")
            ])
        return

    # ── PRIORITY 2: Riddle in progress ───────────────────────────────
    if uid in cm.riddle_state:
        rs     = cm.riddle_state[uid]
        riddle = cm.riddles[rs["idx"]]
        if text == "تلميح":
            reply(event.reply_token,
                  [riddle_hint_flex(riddle.get("hint","لا يوجد تلميح"), riddle["question"])]); return
        if text == "جواب":
            del cm.riddle_state[uid]
            reply(event.reply_token,
                  [riddle_answer_flex(riddle["answer"], riddle["question"])]); return
        if text == "لغز":
            del cm.riddle_state[uid]
            # fall through to start new riddle
        else:
            reply(event.reply_token, [_txt('اضغط "تلميح" او "جواب"')]); return

    # ── PRIORITY 3: Deen in progress ─────────────────────────────────
    if uid in cm.deen_state:
        ds   = cm.deen_state[uid]
        item = cm.religion[ds["idx"]]
        if text == "تلميح":
            reply(event.reply_token,
                  [deen_hint_flex(item.get("hint","لا يوجد تلميح"), item["question"])]); return
        if text == "جواب":
            del cm.deen_state[uid]
            reply(event.reply_token,
                  [deen_answer_flex(item["answer"], item["question"])]); return
        if text == "دين":
            del cm.deen_state[uid]
            # fall through to start new question
        else:
            reply(event.reply_token, [_txt('اضغط "تلميح" او "جواب"')]); return

    # ── Game selection by number ──────────────────────────────────────
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

    # ── Navigation ────────────────────────────────────────────────────
    if text in ["بداية","ابدأ","start"]:
        reply(event.reply_token, [welcome_flex()]); return

    if text == "مساعدة":
        reply(event.reply_token, [help_flex()]); return

    if text == "المزيد":
        reply(event.reply_token, [_txt("تفضل:")], secondary=True); return

    if text == "رجوع":
        reply(event.reply_token, [_txt("تفضل:")], secondary=False); return

    # ── تحليل ─────────────────────────────────────────────────────────
    if text == "تحليل":
        reply(event.reply_token, [games_list_flex()]); return

    # ── لغز ───────────────────────────────────────────────────────────
    if text == "لغز":
        if not cm.riddles:
            reply(event.reply_token, [_txt("لا تتوفر الغاز")]); return
        r   = cm.get_random("لغز", cm.riddles)
        idx = cm.riddles.index(r)
        cm.riddle_state[uid] = {"idx": idx}
        reply(event.reply_token, [riddle_flex(r, idx+1, len(cm.riddles))]); return

    # ── دين ───────────────────────────────────────────────────────────
    if text == "دين":
        if not cm.religion:
            reply(event.reply_token, [_txt("لا تتوفر اسئلة")]); return
        r   = cm.get_random("دين", cm.religion)
        idx = cm.religion.index(r)
        cm.deen_state[uid] = {"idx": idx}
        reply(event.reply_token, [deen_flex(r, idx+1, len(cm.religion))]); return

    # ── Plain text commands ────────────────────────────────────────────
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

    # ── Original content ──────────────────────────────────────────────
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
            if author and author != "غير معروف": msg = f"{msg}\n\n— {author}"
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
