import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage,
    FlexBubble, FlexBox, FlexText, FlexButton, FlexSeparator,
    MessageAction, QuickReply, QuickReplyItem
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=TOKEN)
handler = WebhookHandler(SECRET)

# ثيم أسود وبنفسجي أنيق
C = {
    'bg': '#1a1a1a',           # خلفية سوداء
    'card': '#2d2d2d',         # كارد رمادي غامق
    'glass': '#252525',        # زجاجي
    'pri': '#9b59b6',          # بنفسجي أساسي
    'sec': '#8e44ad',          # بنفسجي غامق
    'acc': '#b388ff',          # بنفسجي فاتح للتمييز
    'txt': '#e0e0e0',          # نص فاتح
    'txt2': '#a0a0a0',         # نص ثانوي
    'border': '#3d3d3d'        # حدود
}

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

    def load_lines(self, filename):
        if not os.path.exists(filename):
            return []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"خطأ في قراءة {filename}: {e}")
            return []

    def load_json(self, filename):
        if not os.path.exists(filename):
            return [] if filename.endswith('s.json') else {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"خطأ في قراءة {filename}: {e}")
            return [] if filename.endswith('s.json') else {}

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
        
        games_data = self.load_json("personality_games.json")
        self.games = [games_data[k] for k in sorted(games_data.keys())] if isinstance(games_data, dict) else []
        
        self.used = {k: [] for k in list(self.files.keys()) + ["منشن", "اقتباس", "موقف"]}

    def get_random_index(self, key, max_count):
        if max_count == 0:
            return 0
        if len(self.used.get(key, [])) >= max_count:
            self.used[key] = []
        
        available = [i for i in range(max_count) if i not in self.used.get(key, [])]
        index = random.choice(available) if available else random.randint(0, max_count - 1)
        
        if key not in self.used:
            self.used[key] = []
        self.used[key].append(index)
        return index

    def get_content(self, category):
        items = self.files.get(category, [])
        return items[self.get_random_index(category, len(items))] if items else None

    def get_mention(self):
        return self.mention[self.get_random_index("منشن", len(self.mention))] if self.mention else None

    def get_situation(self):
        return self.situations[self.get_random_index("موقف", len(self.situations))] if self.situations else None

    def get_quote(self):
        return self.quotes[self.get_random_index("اقتباس", len(self.quotes))] if self.quotes else None

cm = ContentManager()
cm.initialize()

def create_menu():
    """قائمة الأزرار الثابتة"""
    items = [
        ("سؤال", "سؤال"), ("منشن", "منشن"), ("اعتراف", "اعتراف"),
        ("تحدي", "تحدي"), ("موقف", "موقف"), ("اقتباس", "اقتباس"),
        ("تحليل", "تحليل")
    ]
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=label, text=text))
        for label, text in items
    ])

def create_games_list_flex(games):
    """قائمة التحليلات بتصميم أنيق"""
    buttons = [
        FlexButton(
            action=MessageAction(
                label=f"{i}. {game.get('title', f'تحليل {i}')}",
                text=str(i)
            ),
            style='primary',
            color=C['pri'],
            height='md',
            margin='sm'
        )
        for i, game in enumerate(games[:10], 1)
    ]
    
    return FlexMessage(
        alt_text="تحليل الشخصية",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='24px',
                contents=[
                    # Header
                    FlexBox(
                        layout='vertical',
                        background_color=C['glass'],
                        corner_radius='12px',
                        padding_all='16px',
                        margin='none',
                        contents=[
                            FlexText(
                                text='بوت عناد المالكي',
                                weight='bold',
                                size='lg',
                                color=C['acc'],
                                align='center'
                            ),
                            FlexText(
                                text='اختر تحليل الشخصية',
                                size='sm',
                                color=C['txt2'],
                                align='center',
                                margin='sm'
                            )
                        ]
                    ),
                    FlexSeparator(margin='lg', color=C['border']),
                    # Buttons
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        spacing='sm',
                        contents=buttons
                    ),
                    FlexSeparator(margin='lg', color=C['border']),
                    # Footer
                    FlexText(
                        text='عبير الدوسري © 2025',
                        size='xxs',
                        color=C['txt2'],
                        align='center',
                        margin='md'
                    )
                ]
            )
        )
    )

def create_game_question_flex(title, question, progress):
    """سؤال التحليل بتصميم أنيق"""
    buttons = [
        FlexButton(
            action=MessageAction(label=f"{key}. {value}", text=key),
            style='primary',
            color=C['pri'],
            height='md',
            margin='sm'
        )
        for key, value in question['options'].items()
    ]
    
    return FlexMessage(
        alt_text=title,
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='24px',
                contents=[
                    # Header
                    FlexBox(
                        layout='horizontal',
                        margin='none',
                        contents=[
                            FlexText(
                                text=title,
                                weight='bold',
                                size='lg',
                                color=C['acc'],
                                flex=1
                            ),
                            FlexText(
                                text=progress,
                                size='sm',
                                color=C['txt2'],
                                flex=0,
                                align='end'
                            )
                        ]
                    ),
                    FlexSeparator(margin='md', color=C['border']),
                    # Question
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        padding_all='16px',
                        background_color=C['card'],
                        corner_radius='12px',
                        contents=[
                            FlexText(
                                text=question['question'],
                                size='md',
                                color=C['txt'],
                                wrap=True,
                                weight='bold'
                            )
                        ]
                    ),
                    # Options
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        spacing='sm',
                        contents=buttons
                    )
                ]
            )
        )
    )

def create_game_result_flex(result):
    """نتيجة التحليل بتصميم أنيق"""
    return FlexMessage(
        alt_text="النتيجة",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='24px',
                contents=[
                    # Header
                    FlexBox(
                        layout='vertical',
                        background_color=C['glass'],
                        corner_radius='12px',
                        padding_all='16px',
                        margin='none',
                        contents=[
                            FlexText(
                                text='بوت عناد المالكي',
                                weight='bold',
                                size='md',
                                color=C['acc'],
                                align='center'
                            ),
                            FlexText(
                                text='نتيجة التحليل',
                                size='xl',
                                color=C['txt'],
                                align='center',
                                weight='bold',
                                margin='sm'
                            )
                        ]
                    ),
                    FlexSeparator(margin='lg', color=C['border']),
                    # Result
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        padding_all='20px',
                        background_color=C['card'],
                        corner_radius='12px',
                        contents=[
                            FlexText(
                                text=result,
                                size='md',
                                color=C['txt'],
                                wrap=True,
                                line_spacing='8px'
                            )
                        ]
                    ),
                    # New Analysis Button
                    FlexBox(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            FlexButton(
                                action=MessageAction(label='تحليل جديد', text='تحليل'),
                                style='primary',
                                color=C['pri'],
                                height='md'
                            )
                        ]
                    ),
                    FlexSeparator(margin='lg', color=C['border']),
                    # Footer
                    FlexText(
                        text='عبير الدوسري © 2025',
                        size='xxs',
                        color=C['txt2'],
                        align='center',
                        margin='md'
                    )
                ]
            )
        )
    )

COMMANDS = {
    "سؤال": ["سؤال", "سوال"],
    "تحدي": ["تحدي"],
    "اعتراف": ["اعتراف"],
    "منشن": ["منشن"],
    "موقف": ["موقف"],
    "اقتباس": ["اقتباس", "اقتباسات", "حكمة"],
    "تحليل": ["تحليل", "شخصية"]
}

def find_command(text):
    text = text.lower().strip()
    for command, variations in COMMANDS.items():
        if text in [v.lower() for v in variations]:
            return command
    return None

def send_reply(reply_token, messages):
    """إرسال رد مع القائمة الثابتة"""
    try:
        # إضافة القائمة للرسالة الأخيرة
        if isinstance(messages[-1], TextMessage):
            messages[-1].quick_reply = create_menu()
        
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
    except Exception as e:
        logger.error(f"خطأ في إرسال الرد: {e}")

def calculate_result(answers, game_index):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for answer in answers:
        if answer in counts:
            counts[answer] += 1
    
    most_common = max(counts, key=counts.get)
    return cm.results.get(f"لعبة{game_index + 1}", {}).get(most_common, "شخصيتك فريدة")

@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        logger.error(f"خطأ: {e}")
        abort(500)
    
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()
    
    try:
        # التعامل مع التحليل - اختيار رقم
        if text.isdigit() and user_id not in cm.game_state:
            game_num = int(text)
            if 1 <= game_num <= len(cm.games):
                game_index = game_num - 1
                cm.game_state[user_id] = {
                    "game_index": game_index,
                    "question_index": 0,
                    "answers": []
                }
                game = cm.games[game_index]
                title = game.get('title', f'تحليل {game_num}')
                progress = f"1/{len(game['questions'])}"
                send_reply(event.reply_token, [
                    create_game_question_flex(title, game["questions"][0], progress)
                ])
            return
        
        # التعامل مع إجابات التحليل
        if user_id in cm.game_state:
            answer_map = {
                "1": "أ", "2": "ب", "3": "ج",
                "a": "أ", "b": "ب", "c": "ج",
                "أ": "أ", "ب": "ب", "ج": "ج"
            }
            
            answer = answer_map.get(text_lower)
            if answer:
                state = cm.game_state[user_id]
                state["answers"].append(answer)
                game = cm.games[state["game_index"]]
                state["question_index"] += 1
                
                if state["question_index"] < len(game["questions"]):
                    title = game.get('title', 'تحليل')
                    progress = f"{state['question_index'] + 1}/{len(game['questions'])}"
                    send_reply(event.reply_token, [
                        create_game_question_flex(
                            title,
                            game["questions"][state["question_index"]],
                            progress
                        )
                    ])
                else:
                    result = calculate_result(state["answers"], state["game_index"])
                    send_reply(event.reply_token, [create_game_result_flex(result)])
                    del cm.game_state[user_id]
            return
        
        # الأوامر الأساسية
        command = find_command(text)
        if command:
            if command == "اقتباس":
                quote = cm.get_quote()
                if quote:
                    msg = f"💭 {quote.get('text', '')}\n\n— {quote.get('author', 'مجهول')}"
                    send_reply(event.reply_token, [TextMessage(text=msg)])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد اقتباسات")])
            
            elif command == "منشن":
                question = cm.get_mention()
                if question:
                    send_reply(event.reply_token, [TextMessage(text=f"❓ {question}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد أسئلة")])
            
            elif command == "موقف":
                situation = cm.get_situation()
                if situation:
                    send_reply(event.reply_token, [TextMessage(text=f"💭 {situation}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد مواقف")])
            
            elif command == "تحليل":
                if cm.games:
                    send_reply(event.reply_token, [create_games_list_flex(cm.games)])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد تحليلات")])
            
            else:
                content = cm.get_content(command)
                if content:
                    send_reply(event.reply_token, [TextMessage(text=f"• {content}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد بيانات")])
    
    except Exception as e:
        logger.error(f"خطأ: {e}")
        send_reply(event.reply_token, [TextMessage(text="حدث خطأ")])

def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG")
    if url and not url.startswith("http"):
        url = f"https://{url}.onrender.com"
    
    while True:
        try:
            if url:
                requests.get(f"{url}/health", timeout=10)
            time.sleep(840)
        except:
            time.sleep(60)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG"):
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
    
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
