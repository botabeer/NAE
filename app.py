# -*- coding: utf-8 -*-
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

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= APP =================
app = Flask(__name__)
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ================= RENDER THEME =================
C = {
    'bg': '#FFFFFF',
    'card': '#F9FAFB',
    'glass': '#F3F0FF',

    'pri': '#7C3AED',
    'sec': '#EDE9FE',
    'acc': '#6D28D9',

    'txt': '#111827',
    'txt2': '#6B7280',

    'border': '#E5E7EB'
}

# ================= CONTENT MANAGER =================
class ContentManager:
    def __init__(self):
        self.files = {}
        self.mention = []
        self.games = []
        self.quotes = []
        self.situations = []
        self.results = {}
        self.used = {}
        self.game_state = {}

    def load_lines(self, f):
        if not os.path.exists(f):
            return []
        try:
            with open(f, 'r', encoding='utf-8') as file:
                return [l.strip() for l in file if l.strip()]
        except Exception as e:
            logger.error(e)
            return []

    def load_json(self, f):
        if not os.path.exists(f):
            return {}
        try:
            with open(f, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception as e:
            logger.error(e)
            return {}

    def initialize(self):
        self.files = {
            "سؤال": self.load_lines("questions.txt"),
            "تحدي": self.load_lines("challenges.txt"),
            "اعتراف": self.load_lines("confessions.txt")
        }
        self.mention = self.load_lines("more_questions.txt")
        self.situations = self.load_lines("situations.txt")
        self.quotes = self.load_json("quotes.json")
        self.results = self.load_json("detailed_results.json")

        games = self.load_json("personality_games.json")
        self.games = [games[k] for k in sorted(games.keys())] if isinstance(games, dict) else []

        self.used = {k: [] for k in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف", "اقتباس"]}
        logger.info("Content initialized")

    def get_random(self, key, data):
        if not data:
            return None
        used = self.used.get(key, [])
        if len(used) >= len(data):
            used.clear()
        idx = random.choice([i for i in range(len(data)) if i not in used])
        used.append(idx)
        self.used[key] = used
        return data[idx]

cm = ContentManager()
cm.initialize()

# ================= QUICK MENU =================
def create_menu():
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=l, text=l))
        for l in ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباس", "تحليل"]
    ])

# ================= FLEX BUILDERS =================
def flex_container(body):
    return FlexMessage(
        alt_text="Bot",
        contents=FlexContainer.from_dict({
            "type": "bubble",
            "direction": "rtl",
            "body": body
        })
    )

def games_list_flex():
    return flex_container({
        "type": "box",
        "layout": "vertical",
        "backgroundColor": C['bg'],
        "paddingAll": "20px",
        "contents": [
            {
                "type": "text",
                "text": "تحليل الشخصية",
                "weight": "bold",
                "size": "md",
                "color": C['acc'],
                "align": "center"
            },
            {
                "type": "separator",
                "margin": "md",
                "color": C['border']
            }
        ] + [
            {
                "type": "button",
                "style": "primary",
                "color": C['pri'],
                "margin": "sm",
                "action": {
                    "type": "message",
                    "label": f"{i+1}. {g.get('title','تحليل')}",
                    "text": str(i+1)
                }
            } for i, g in enumerate(cm.games)
        ]
    })

def question_flex(title, q, progress):
    return flex_container({
        "type": "box",
        "layout": "vertical",
        "backgroundColor": C['bg'],
        "paddingAll": "20px",
        "contents": [
            {
                "type": "text",
                "text": f"{title} • {progress}",
                "weight": "bold",
                "color": C['acc']
            },
            {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "paddingAll": "20px",
                "backgroundColor": C['glass'],
                "cornerRadius": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": q['question'],
                        "wrap": True,
                        "color": C['txt']
                    }
                ]
            }
        ] + [
            {
                "type": "button",
                "style": "secondary",
                "color": C['sec'],
                "margin": "sm",
                "action": {
                    "type": "message",
                    "label": f"{k}. {v}",
                    "text": k
                }
            } for k, v in q['options'].items()
        ]
    })

def result_flex(text):
    return flex_container({
        "type": "box",
        "layout": "vertical",
        "backgroundColor": C['bg'],
        "paddingAll": "20px",
        "contents": [
            {
                "type": "text",
                "text": "نتيجة التحليل",
                "weight": "bold",
                "size": "lg",
                "color": C['acc'],
                "align": "center"
            },
            {
                "type": "box",
                "layout": "vertical",
                "margin": "md",
                "paddingAll": "20px",
                "backgroundColor": C['glass'],
                "cornerRadius": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": text,
                        "wrap": True,
                        "color": C['txt']
                    }
                ]
            },
            {
                "type": "button",
                "style": "primary",
                "color": C['pri'],
                "margin": "lg",
                "action": {
                    "type": "message",
                    "label": "تحليل جديد",
                    "text": "تحليل"
                }
            }
        ]
    })

# ================= HELPERS =================
def send_reply(token, msgs):
    msgs[-1].quick_reply = create_menu()
    with ApiClient(configuration) as api:
        MessagingApi(api).reply_message(
            ReplyMessageRequest(reply_token=token, messages=msgs)
        )

def calculate_result(answers, idx):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        counts[a] += 1
    key = max(counts, key=counts.get)
    return cm.results.get(f"لعبة{idx+1}", {}).get(key, "شخصيتك مميزة ")

# ================= ROUTES =================
@app.route("/")
def home():
    return "LINE BOT OK"

@app.route("/health")
def health():
    return {"ok": True}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ================= HANDLER =================
@handler.add(MessageEvent, message=TextMessageContent)
def handle(event):
    uid = event.source.user_id
    text = event.message.text.strip()

    if uid in cm.game_state:
        ans = text if text in ["أ", "ب", "ج"] else None
        if not ans:
            return
        state = cm.game_state[uid]
        state["answers"].append(ans)
        game = cm.games[state["game"]]
        state["q"] += 1
        if state["q"] < len(game["questions"]):
            send_reply(event.reply_token, [
                question_flex(game["title"], game["questions"][state["q"]],
                              f"{state['q']+1}/{len(game['questions'])}")
            ])
        else:
            res = calculate_result(state["answers"], state["game"])
            send_reply(event.reply_token, [result_flex(res)])
            del cm.game_state[uid]
        return

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

    if text == "تحليل":
        send_reply(event.reply_token, [games_list_flex()])
        return

    mapping = {
        "سؤال": "سؤال",
        "تحدي": "تحدي",
        "اعتراف": "اعتراف",
        "منشن": "منشن",
        "موقف": "موقف",
        "اقتباس": "اقتباس"
    }

    if text in mapping:
        if text == "اقتباس":
            q = cm.get_random("اقتباس", cm.quotes)
            msg = f"{q.get('text','')}\n\n{q.get('author','')}" if q else "—"
        elif text == "منشن":
            msg = cm.get_random("منشن", cm.mention)
        elif text == "موقف":
            msg = cm.get_random("موقف", cm.situations)
        else:
            msg = cm.get_random(text, cm.files.get(text))
        send_reply(event.reply_token, [TextMessage(text=msg or "—")])

# ================= KEEP ALIVE =================
def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if url and not url.startswith("http"):
        url = "https://" + url
    while True:
        try:
            if url:
                requests.get(url + "/health", timeout=5)
        except:
            pass
        time.sleep(600)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL"):
        threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
