import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage,
    FlexMessage, FlexBubble, FlexBox, FlexText, FlexButton, FlexSeparator,
    MessageAction, QuickReply, QuickReplyItem
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
configuration = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

C = {'bg': '#1a1a1a', 'card': '#2d2d2d', 'glass': '#252525', 'pri': '#9b59b6',
     'sec': '#8e44ad', 'acc': '#b388ff', 'txt': '#e0e0e0', 'txt2': '#a0a0a0', 'border': '#3d3d3d'}

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
        if not os.path.exists(f): return []
        try:
            with open(f, 'r', encoding='utf-8') as file:
                return [l.strip() for l in file if l.strip()]
        except: return []

    def load_json(self, f):
        if not os.path.exists(f): return [] if f.endswith('s.json') else {}
        try:
            with open(f, 'r', encoding='utf-8') as file:
                return json.load(file)
        except: return [] if f.endswith('s.json') else {}

    def initialize(self):
        self.files = {"سؤال": self.load_lines("questions.txt"), "تحدي": self.load_lines("challenges.txt"),
                      "اعتراف": self.load_lines("confessions.txt")}
        self.mention = self.load_lines("more_questions.txt")
        self.situations = self.load_lines("situations.txt")
        self.quotes = self.load_json("quotes.json")
        self.results = self.load_json("detailed_results.json")
        g = self.load_json("personality_games.json")
        self.games = [g[k] for k in sorted(g.keys())] if isinstance(g, dict) else []
        self.used = {k: [] for k in list(self.files.keys()) + ["منشن", "اقتباس", "موقف"]}

    def get_random_index(self, key, max_count):
        if max_count == 0: return 0
        if len(self.used.get(key, [])) >= max_count: self.used[key] = []
        available = [i for i in range(max_count) if i not in self.used.get(key, [])]
        idx = random.choice(available) if available else random.randint(0, max_count - 1)
        if key not in self.used: self.used[key] = []
        self.used[key].append(idx)
        return idx

    def get_content(self, cat):
        items = self.files.get(cat, [])
        return items[self.get_random_index(cat, len(items))] if items else None

    def get_mention(self):
        return self.mention[self.get_random_index("منشن", len(self.mention))] if self.mention else None

    def get_situation(self):
        return self.situations[self.get_random_index("موقف", len(self.situations))] if self.situations else None

    def get_quote(self):
        return self.quotes[self.get_random_index("اقتباس", len(self.quotes))] if self.quotes else None

cm = ContentManager()
cm.initialize()

def create_menu():
    return QuickReply(items=[QuickReplyItem(action=MessageAction(label=l, text=t)) 
        for l, t in [("سؤال", "سؤال"), ("منشن", "منشن"), ("اعتراف", "اعتراف"),
                     ("تحدي", "تحدي"), ("موقف", "موقف"), ("اقتباس", "اقتباس"), ("تحليل", "تحليل")]])

def create_games_list_flex(games):
    return FlexMessage(alt_text="تحليل الشخصية", contents=FlexBubble(direction='rtl',
        body=FlexBox(layout='vertical', background_color=C['bg'], padding_all='24px', contents=[
            FlexBox(layout='vertical', background_color=C['glass'], corner_radius='12px', 
                padding_all='16px', margin='none', contents=[
                FlexText(text='بوت عناد المالكي', weight='bold', size='lg', color=C['acc'], align='center'),
                FlexText(text='اختر تحليل الشخصية', size='sm', color=C['txt2'], align='center', margin='sm')]),
            FlexSeparator(margin='lg', color=C['border']),
            FlexBox(layout='vertical', margin='lg', spacing='sm', contents=[
                FlexButton(action=MessageAction(label=f"{i}. {g.get('title', f'تحليل {i}')}", text=str(i)),
                    style='primary', color=C['pri'], height='md', margin='sm') 
                for i, g in enumerate(games[:10], 1)]),
            FlexSeparator(margin='lg', color=C['border']),
            FlexText(text='عبير الدوسري © 2025', size='xxs', color=C['txt2'], align='center', margin='md')])))

def create_game_question_flex(title, q, progress):
    return FlexMessage(alt_text=title, contents=FlexBubble(direction='rtl',
        body=FlexBox(layout='vertical', background_color=C['bg'], padding_all='24px', contents=[
            FlexBox(layout='horizontal', margin='none', contents=[
                FlexText(text=title, weight='bold', size='lg', color=C['acc'], flex=1),
                FlexText(text=progress, size='sm', color=C['txt2'], flex=0, align='end')]),
            FlexSeparator(margin='md', color=C['border']),
            FlexBox(layout='vertical', margin='lg', padding_all='16px', background_color=C['card'],
                corner_radius='12px', contents=[FlexText(text=q['question'], size='md', 
                color=C['txt'], wrap=True, weight='bold')]),
            FlexBox(layout='vertical', margin='lg', spacing='sm', contents=[
                FlexButton(action=MessageAction(label=f"{k}. {v}", text=k), style='primary',
                    color=C['pri'], height='md', margin='sm') 
                for k, v in q['options'].items()])])))

def create_game_result_flex(result):
    return FlexMessage(alt_text="النتيجة", contents=FlexBubble(direction='rtl',
        body=FlexBox(layout='vertical', background_color=C['bg'], padding_all='24px', contents=[
            FlexBox(layout='vertical', background_color=C['glass'], corner_radius='12px',
                padding_all='16px', margin='none', contents=[
                FlexText(text='بوت عناد المالكي', weight='bold', size='md', color=C['acc'], align='center'),
                FlexText(text='نتيجة التحليل', size='xl', color=C['txt'], align='center', 
                    weight='bold', margin='sm')]),
            FlexSeparator(margin='lg', color=C['border']),
            FlexBox(layout='vertical', margin='lg', padding_all='20px', background_color=C['card'],
                corner_radius='12px', contents=[FlexText(text=result, size='md', color=C['txt'], 
                wrap=True, line_spacing='8px')]),
            FlexBox(layout='vertical', margin='xl', contents=[
                FlexButton(action=MessageAction(label='تحليل جديد', text='تحليل'), 
                    style='primary', color=C['pri'], height='md')]),
            FlexSeparator(margin='lg', color=C['border']),
            FlexText(text='عبير الدوسري © 2025', size='xxs', color=C['txt2'], align='center', margin='md')])))

COMMANDS = {"سؤال": ["سؤال", "سوال"], "تحدي": ["تحدي"], "اعتراف": ["اعتراف"],
            "منشن": ["منشن"], "موقف": ["موقف"], "اقتباس": ["اقتباس", "اقتباسات", "حكمة"],
            "تحليل": ["تحليل", "شخصية"]}

def find_command(text):
    text = text.lower().strip()
    for cmd, vars in COMMANDS.items():
        if text in [v.lower() for v in vars]: return cmd
    return None

def send_reply(token, msgs):
    try:
        if isinstance(msgs[-1], TextMessage): msgs[-1].quick_reply = create_menu()
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=token, messages=msgs))
    except Exception as e: logger.error(f"خطأ: {e}")

def calculate_result(answers, idx):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for a in answers:
        if a in counts: counts[a] += 1
    return cm.results.get(f"لعبة{idx + 1}", {}).get(max(counts, key=counts.get), "شخصيتك فريدة")

@app.route("/", methods=["GET"])
def home(): return "LINE Bot is running", 200

@app.route("/health", methods=["GET"])
def health(): return {"status": "ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    try: handler.handle(request.get_data(as_text=True), request.headers.get("X-Line-Signature", ""))
    except InvalidSignatureError: abort(400)
    except: abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()
    
    try:
        if user_id in cm.game_state:
            answer_map = {"1": "أ", "2": "ب", "3": "ج", "a": "أ", "b": "ب", "c": "ج",
                         "أ": "أ", "ب": "ب", "ج": "ج"}
            answer = answer_map.get(text_lower)
            if answer:
                state = cm.game_state[user_id]
                state["answers"].append(answer)
                game = cm.games[state["game_index"]]
                state["question_index"] += 1
                if state["question_index"] < len(game["questions"]):
                    send_reply(event.reply_token, [create_game_question_flex(
                        game.get('title', 'تحليل'),
                        game["questions"][state["question_index"]],
                        f"{state['question_index'] + 1}/{len(game['questions'])}")])
                else:
                    send_reply(event.reply_token, [create_game_result_flex(
                        calculate_result(state["answers"], state["game_index"]))])
                    del cm.game_state[user_id]
            return
        
        if text.isdigit():
            num = int(text)
            if 1 <= num <= len(cm.games):
                cm.game_state[user_id] = {"game_index": num - 1, "question_index": 0, "answers": []}
                game = cm.games[num - 1]
                send_reply(event.reply_token, [create_game_question_flex(
                    game.get('title', f'تحليل {num}'), game["questions"][0],
                    f"1/{len(game['questions'])}")])
            return
        
        cmd = find_command(text)
        if cmd:
            if cmd == "اقتباس":
                q = cm.get_quote()
                send_reply(event.reply_token, [TextMessage(text=f"{q.get('text', '')}\n\n{q.get('author', 'مجهول')}" if q else "لا توجد اقتباسات")])
            elif cmd == "منشن":
                q = cm.get_mention()
                send_reply(event.reply_token, [TextMessage(text=q if q else "لا توجد أسئلة")])
            elif cmd == "موقف":
                s = cm.get_situation()
                send_reply(event.reply_token, [TextMessage(text=s if s else "لا توجد مواقف")])
            elif cmd == "تحليل":
                send_reply(event.reply_token, [create_games_list_flex(cm.games)] if cm.games else [TextMessage(text="لا توجد تحليلات")])
            else:
                c = cm.get_content(cmd)
                send_reply(event.reply_token, [TextMessage(text=c if c else "لا توجد بيانات")])
    except Exception as e: logger.error(f"خطأ: {e}")

def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG")
    if url and not url.startswith("http"): url = f"https://{url}.onrender.com"
    while True:
        try:
            if url: requests.get(f"{url}/health", timeout=10)
            time.sleep(840)
        except: time.sleep(60)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG"):
        threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), threaded=True)
