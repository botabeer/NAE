import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort

from linebot.v3.webhooks import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage,
    FlexMessage, FlexContainer,
    QuickReply, QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# ───────────────────────────── LOGGING ──────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── APP ──────────────────────────────────
app = Flask(__name__)
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ───────────────────────────── THEME ────────────────────────────────
C = {
    'bg':     '#FFFFFF',
    'glass':  '#F3F0FF',
    'pri':    '#7C3AED',
    'sec':    '#EDE9FE',
    'acc':    '#6D28D9',
    'txt':    '#111827',
    'txt2':   '#6B7280',
    'border': '#E5E7EB',
    'green':  '#059669',
    'blue':   '#1D4ED8',
    'teal':   '#0F766E',
    'red':    '#DC2626',
    'amber':  '#B45309',
}

# ══════════════════════════ CONTENT MANAGER ══════════════════════════
class ContentManager:
    def __init__(self):
        # original content
        self.files      = {}
        self.mention    = []
        self.games      = []
        self.quotes     = []
        self.situations = []
        self.riddles    = []
        self.results    = {}
        # new group content
        self.stories    = []   # ← قصة (replaces معلومة)
        self.scenarios  = []
        self.choices    = []
        self.never      = []
        self.motivation = []
        self.philosophy = []
        # anti-repeat tracker + per-user states
        self.used         = {}
        self.game_state   = {}
        self.riddle_state = {}

    def _lines(self, f):
        if not os.path.exists(f):
            logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                return [l.strip() for l in fh if l.strip()]
        except Exception as e:
            logger.error(f"Error {f}: {e}"); return []

    def _json(self, f, default=None):
        d = default if default is not None else {}
        if not os.path.exists(f):
            logger.warning(f"Missing: {f}"); return d
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                return json.load(fh)
        except Exception as e:
            logger.error(f"Error {f}: {e}"); return d

    def _stories(self, f):
        """Load stories separated by ─── delimiter."""
        if not os.path.exists(f):
            logger.warning(f"Missing: {f}"); return []
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                raw = fh.read()
            parts = [p.strip() for p in raw.split("───") if p.strip()]
            return parts
        except Exception as e:
            logger.error(f"Error {f}: {e}"); return []

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

        raw = self._json("personality_games.json")
        self.games = [raw[k] for k in sorted(raw.keys())] if isinstance(raw, dict) else []

        # new content
        self.stories    = self._stories("stories.txt")
        self.scenarios  = self._lines("scenarios.txt")
        self.choices    = self._lines("choices.txt")
        self.never      = self._lines("never.txt")
        self.motivation = self._lines("motivation.txt")

        phil = self._json("philosophical_questions.json", default=[])
        self.philosophy = [p["question"] for p in phil if "question" in p]

        all_keys = [
            "سؤال","تحدي","اعتراف","منشن","موقف","اقتباس","لغز",
            "قصة","فلسفة","لو كنت","أيهما أصعب","أنا لم","تحفيز",
        ]
        self.used = {k: [] for k in all_keys}

        logger.info(
            f"Loaded | q={len(self.files['سؤال'])} riddles={len(self.riddles)} "
            f"stories={len(self.stories)} phil={len(self.philosophy)} "
            f"never={len(self.never)} scenarios={len(self.scenarios)}"
        )

    def get_random(self, key, data):
        if not data: return None
        used = self.used.setdefault(key, [])
        if len(used) >= len(data): used.clear()
        available = [i for i in range(len(data)) if i not in used]
        idx = random.choice(available)
        used.append(idx)
        return data[idx]


cm = ContentManager()
cm.initialize()

# ══════════════════════════ QUICK REPLY ══════════════════════════════
MENU_A = [
    "سؤال","منشن","اعتراف","تحدي","موقف","اقتباس",
    "تحليل","لغز","قصة","فلسفة","لو كنت","أيهما أصعب","المزيد ⬇️"
]
MENU_B = [
    "أنا لم","تحفيز","سؤال","منشن","تحدي","موقف",
    "اقتباس","قصة","فلسفة","لو كنت","أيهما أصعب","لغز","تحليل"
]

def create_menu(secondary=False):
    labels = MENU_B if secondary else MENU_A
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=l, text=l))
        for l in labels
    ])

# ══════════════════════════ FLEX PRIMITIVES ═══════════════════════════
def _bubble(body):
    return FlexMessage(
        alt_text="Bot",
        contents=FlexContainer.from_dict({
            "type": "bubble", "direction": "rtl", "body": body
        })
    )

def _box(contents, **kw):
    return {"type": "box", "layout": "vertical", "contents": contents, **kw}

def _hbox(contents, **kw):
    return {"type": "box", "layout": "horizontal", "contents": contents, **kw}

def _text(t, **kw):
    return {"type": "text", "text": str(t), "wrap": True, **kw}

def _sep():
    return {"type": "separator", "margin": "md", "color": C['border']}

def _btn(label, text, style="secondary", color=None):
    return {
        "type": "button", "style": style,
        "color": color or C['sec'], "margin": "sm",
        "action": {"type": "message", "label": label, "text": text},
    }

# ══════════════════════════ FLEX BUILDERS ════════════════════════════

def games_list_flex():
    return _bubble(_box(
        [_text("تحليل الشخصية", weight="bold", size="md",
               color=C['acc'], align="center"), _sep()] +
        [_btn(f"{i+1}. {g.get('title','تحليل')}", str(i+1),
              style="primary", color=C['pri'])
         for i, g in enumerate(cm.games)],
        backgroundColor=C['bg'], paddingAll="20px"
    ))

def question_flex(title, q, progress):
    return _bubble(_box(
        [
            _text(f"{title}  •  {progress}", weight="bold", color=C['acc']),
            _box([_text(q['question'], color=C['txt'])],
                 margin="md", paddingAll="20px",
                 backgroundColor=C['glass'], cornerRadius="16px"),
        ] + [_btn(f"{k}. {v}", k) for k, v in q['options'].items()],
        backgroundColor=C['bg'], paddingAll="20px"
    ))

def result_flex(text):
    return _bubble(_box([
        _text("نتيجة التحليل", weight="bold", size="lg",
              color=C['acc'], align="center"),
        _box([_text(text, color=C['txt'])],
             margin="md", paddingAll="20px",
             backgroundColor=C['glass'], cornerRadius="16px"),
        _btn("تحليل جديد", "تحليل", style="primary", color=C['pri']),
    ], backgroundColor=C['bg'], paddingAll="20px"))

def riddle_flex(riddle, num, total):
    return _bubble(_box([
        _text(f"لغز  •  {num}/{total}", weight="bold", color=C['acc']),
        _box([_text(riddle['question'], color=C['txt'])],
             margin="md", paddingAll="20px",
             backgroundColor=C['glass'], cornerRadius="16px"),
        _hbox([
            _btn("تلميح", "تلميح"),
            _btn("إجابة", "إجابة"),
            _btn("لغز جديد", "لغز", style="primary", color=C['pri']),
        ], margin="md"),
    ], backgroundColor=C['bg'], paddingAll="20px"))

def hint_flex(hint, question):
    return _bubble(_box([
        _text("التلميح", weight="bold", color=C['acc']),
        _box([_text(hint, color=C['txt2'])],
             margin="md", paddingAll="16px",
             backgroundColor=C['glass'], cornerRadius="12px"),
        _box([_text(question, color=C['txt'], size="sm")],
             margin="sm", paddingAll="12px",
             backgroundColor=C['sec'], cornerRadius="12px"),
        _btn("إجابة", "إجابة"),
    ], backgroundColor=C['bg'], paddingAll="20px"))

def answer_flex(answer, question):
    return _bubble(_box([
        _text("الإجابة الصحيحة", weight="bold", color=C['green']),
        _box([_text(answer, color=C['txt'], weight="bold")],
             margin="md", paddingAll="20px",
             backgroundColor=C['glass'], cornerRadius="16px"),
        _box([_text(question, color=C['txt2'], size="sm")],
             margin="sm", paddingAll="12px",
             backgroundColor=C['sec'], cornerRadius="12px"),
        _btn("لغز جديد", "لغز", style="primary", color=C['pri']),
    ], backgroundColor=C['bg'], paddingAll="20px"))

def content_card(header, body_text, repeat_label, repeat_cmd, accent):
    return _bubble(_box([
        _text(header, weight="bold", color=accent),
        _box([_text(body_text, color=C['txt'], size="md")],
             margin="md", paddingAll="20px",
             backgroundColor=C['glass'], cornerRadius="16px"),
        _btn(repeat_label, repeat_cmd, style="primary", color=C['pri']),
    ], backgroundColor=C['bg'], paddingAll="20px"))

# per-type shortcuts
def story_flex(t):      return content_card("قصة ملهمة",           t, "قصة أخرى",     "قصة",          C['amber'])
def phil_flex(t):       return content_card("سؤال للنقاش",         t, "سؤال آخر",     "فلسفة",         C['acc'])
def scenario_flex(t):   return content_card("لو كنت...",           t, "سيناريو آخر",  "لو كنت",       "#7C3AED")
def choice_flex(t):     return content_card("أيهما أصعب؟",         t, "خيار آخر",     "أيهما أصعب",   C['red'])
def never_flex(t):      return content_card("أنا لم أفعل قط...",   t, "واحدة ثانية",  "أنا لم",        C['teal'])
def motivation_flex(t): return content_card("رسالة اليوم",         t, "رسالة أخرى",   "تحفيز",         C['green'])

# ══════════════════════════ RESULT CALCULATOR ════════════════════════
def calculate_result(answers, game_idx):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        if a in counts: counts[a] += 1
    max_val  = max(counts.values())
    top_keys = [k for k, v in counts.items() if v == max_val]
    key = top_keys[0] if len(top_keys) == 1 else \
          next((a for a in answers if a in top_keys), top_keys[0])
    return cm.results.get(f"لعبة{game_idx + 1}", {}).get(key, "شخصيتك مميزة ومختلفة")

# ══════════════════════════ REPLY HELPER ═════════════════════════════
def send_reply(token, msgs, secondary=False):
    if not msgs: return
    msgs[-1].quick_reply = create_menu(secondary)
    try:
        with ApiClient(configuration) as api:
            MessagingApi(api).reply_message(
                ReplyMessageRequest(reply_token=token, messages=msgs)
            )
    except Exception as e:
        logger.error(f"send_reply error: {e}")

# ══════════════════════════ ROUTES ═══════════════════════════════════
@app.route("/")
def home(): return "LINE BOT OK"

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

# ══════════════════════════ MAIN HANDLER ═════════════════════════════
@handler.add(MessageEvent, message=TextMessageContent)
def handle(event):
    uid  = event.source.user_id
    text = event.message.text.strip()

    # 1. Personality game in progress
    if uid in cm.game_state:
        ans = text if text in ["أ", "ب", "ج"] else None
        if not ans:
            send_reply(event.reply_token, [TextMessage(text="اختر: أ  /  ب  /  ج")])
            return
        state  = cm.game_state[uid]
        state["answers"].append(ans)
        game   = cm.games[state["game"]]
        q_next = state["q"] + 1
        if q_next < len(game["questions"]):
            state["q"] = q_next
            send_reply(event.reply_token, [
                question_flex(game["title"], game["questions"][q_next],
                              f"{q_next + 1}/{len(game['questions'])}")
            ])
        else:
            res = calculate_result(state["answers"], state["game"])
            del cm.game_state[uid]
            send_reply(event.reply_token, [result_flex(res)])
        return

    # 2. Riddle in progress
    if uid in cm.riddle_state:
        rs     = cm.riddle_state[uid]
        riddle = cm.riddles[rs["riddle_idx"]]
        if text == "تلميح":
            rs["hint_used"] = True
            send_reply(event.reply_token,
                       [hint_flex(riddle.get("hint", "لا يوجد تلميح"), riddle["question"])])
            return
        if text == "إجابة":
            del cm.riddle_state[uid]
            send_reply(event.reply_token,
                       [answer_flex(riddle["answer"], riddle["question"])])
            return
        if text != "لغز":
            send_reply(event.reply_token,
                       [TextMessage(text='اضغط "تلميح" أو "إجابة"')])
            return
        del cm.riddle_state[uid]

    # 3. Start game by number
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(cm.games):
            cm.game_state[uid] = {"game": idx, "q": 0, "answers": []}
            g = cm.games[idx]
            send_reply(event.reply_token, [
                question_flex(g["title"], g["questions"][0],
                              f"1/{len(g['questions'])}")
            ])
        return

    # 4. Second menu page
    if text == "المزيد ⬇️":
        send_reply(event.reply_token,
                   [TextMessage(text="اختر:")], secondary=True)
        return

    # 5. تحليل & لغز
    if text == "تحليل":
        send_reply(event.reply_token, [games_list_flex()]); return

    if text == "لغز":
        if not cm.riddles:
            send_reply(event.reply_token, [TextMessage(text="لا تتوفر ألغاز حالياً")]); return
        r   = cm.get_random("لغز", cm.riddles)
        idx = cm.riddles.index(r)
        cm.riddle_state[uid] = {"riddle_idx": idx, "hint_used": False}
        send_reply(event.reply_token, [riddle_flex(r, idx + 1, len(cm.riddles))]); return

    # 6. New group content
    new_commands = {
        "قصة":         (cm.stories,    story_flex),
        "فلسفة":       (cm.philosophy, phil_flex),
        "لو كنت":      (cm.scenarios,  scenario_flex),
        "أيهما أصعب": (cm.choices,    choice_flex),
        "أنا لم":      (cm.never,      never_flex),
        "تحفيز":       (cm.motivation, motivation_flex),
    }
    if text in new_commands:
        data, builder = new_commands[text]
        item = cm.get_random(text, data)
        if item:
            send_reply(event.reply_token, [builder(item)])
        else:
            send_reply(event.reply_token, [TextMessage(text="لا يتوفر محتوى حالياً")])
        return

    # 7. Original text dispatch
    dispatch = {
        "سؤال":   ("سؤال",   cm.files["سؤال"]),
        "تحدي":   ("تحدي",   cm.files["تحدي"]),
        "اعتراف": ("اعتراف", cm.files["اعتراف"]),
        "منشن":   ("منشن",   cm.mention),
        "موقف":   ("موقف",   cm.situations),
        "اقتباس": ("اقتباس", cm.quotes),
    }
    if text in dispatch:
        cat, data = dispatch[text]
        item = cm.get_random(cat, data)
        if text == "اقتباس" and isinstance(item, dict):
            author = item.get("author", "").strip()
            msg    = item.get("text", "—")
            if author: msg = f"{msg}\n\n— {author}"
        else:
            msg = item if isinstance(item, str) else "—"
        send_reply(event.reply_token, [TextMessage(text=msg or "—")])

# ══════════════════════════ KEEP ALIVE ═══════════════════════════════
def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL", "")
    if url and not url.startswith("http"):
        url = "https://" + url
    while True:
        try:
            if url: requests.get(url + "/health", timeout=5)
        except Exception:
            pass
        time.sleep(600)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL"):
        threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
