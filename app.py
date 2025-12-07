import json, os, logging, random, threading, time, requests
from flask import Flask, request, abort
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, FlexMessage,
    FlexBubble, FlexBox, FlexText, FlexSeparator,
    FlexButton, MessageAction, QuickReply, QuickReplyItem
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

C = {
    'bg': '#FEFCFF', 'glass': '#F5F0FA', 'card': '#FAF7FC',
    'pri': '#B794F6', 'sec': '#D4B5F8', 'acc': '#9061F9',
    'txt': '#4A4063', 'txt2': '#9B8AA8', 'bdr': '#E8DFF0', 'ok': '#9061F9'
}

class ContentManager:
    def __init__(self):
        self.files = {}
        self.mention = []
        self.riddles = []
        self.games = []
        self.quotes = []
        self.situations = []
        self.results = {}
        self.used = {}

    def load_lines(self, filename):
        if not os.path.exists(filename):
            logger.warning(f"الملف {filename} غير موجود")
            return []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logger.error(f"خطأ في قراءة {filename}: {e}")
            return []

    def load_json(self, filename):
        if not os.path.exists(filename):
            logger.warning(f"الملف {filename} غير موجود")
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
        self.riddles = self.load_json("riddles.json")
        self.quotes = self.load_json("quotes.json")
        self.results = self.load_json("detailed_results.json")
        
        games_data = self.load_json("personality_games.json")
        self.games = [games_data[k] for k in sorted(games_data.keys())] if isinstance(games_data, dict) else []
        
        self.used = {k: [] for k in list(self.files.keys()) + ["منشن", "لغز", "اقتباس", "موقف"]}
        logger.info("تم تحميل جميع البيانات بنجاح")

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

    def get_riddle(self):
        return self.riddles[self.get_random_index("لغز", len(self.riddles))] if self.riddles else None

    def get_quote(self):
        return self.quotes[self.get_random_index("اقتباس", len(self.quotes))] if self.quotes else None

cm = ContentManager()
cm.initialize()

riddle_state = {}
game_state = {}

def create_menu():
    items = [
        ("سؤال", "سؤال"), ("منشن", "منشن"), ("اعتراف", "اعتراف"),
        ("تحدي", "تحدي"), ("موقف", "موقف"), ("اقتباسات", "اقتباسات"),
        ("لغز", "لغز"), ("تحليل", "تحليل")
    ]
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label=label, text=text))
        for label, text in items
    ])

def create_header(title, icon=""):
    text = f"{icon} {title}" if icon else title
    return FlexBox(
        layout='vertical',
        background_color=C['glass'],
        corner_radius='16px',
        padding_all='16px',
        contents=[
            FlexText(text=text, weight='bold', size='xl', color=C['txt'], align='center')
        ]
    )

def create_help_flex():
    commands = ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]
    items = [
        FlexText(text=f"• {cmd}", size='md', color=C['txt'], margin='sm')
        for cmd in commands
    ]
    
    return FlexMessage(
        alt_text="مساعدة",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='20px',
                contents=[
                    create_header("بوت عناد المالكي"),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexText(text="أوامر البوت:", weight='bold', size='lg', color=C['acc'], margin='lg'),
                    FlexBox(layout='vertical', margin='md', spacing='xs', contents=items),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexBox(
                        layout='vertical',
                        margin='md',
                        padding_all='12px',
                        background_color=C['glass'],
                        corner_radius='8px',
                        contents=[
                            FlexText(
                                text="ملاحظة: تقدر تستخدم البوت بالخاص والقروبات",
                                size='sm',
                                color=C['txt2'],
                                wrap=True,
                                align='center'
                            )
                        ]
                    ),
                    FlexSeparator(margin='lg', color=C['bdr']),
                    FlexText(
                        text="عبير الدوسري - 2025",
                        size='xxs',
                        color=C['txt2'],
                        align='center',
                        margin='md'
                    )
                ]
            )
        )
    )

def create_puzzle_flex(puzzle):
    return FlexMessage(
        alt_text="لغز",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='24px',
                contents=[
                    create_header("لغز"),
                    FlexBox(
                        layout='vertical',
                        margin='xl',
                        padding_all='24px',
                        background_color=C['card'],
                        corner_radius='16px',
                        contents=[
                            FlexText(
                                text=puzzle['question'],
                                size='xl',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                weight='bold'
                            )
                        ]
                    ),
                    FlexBox(
                        layout='vertical',
                        margin='xl',
                        spacing='md',
                        contents=[
                            FlexButton(
                                action=MessageAction(label='لمح', text='لمح'),
                                style='secondary',
                                color=C['sec'],
                                height='md'
                            ),
                            FlexButton(
                                action=MessageAction(label='جاوب', text='جاوب'),
                                style='primary',
                                color=C['pri'],
                                height='md'
                            )
                        ]
                    )
                ]
            )
        )
    )

def create_answer_flex(answer, answer_type):
    label = "جاوب" if "جاوب" in answer_type else "لمح"
    color = C['ok'] if "جاوب" in answer_type else C['sec']
    
    return FlexMessage(
        alt_text=answer_type,
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='24px',
                contents=[
                    FlexBox(
                        layout='vertical',
                        padding_all='16px',
                        background_color=C['glass'],
                        corner_radius='16px',
                        contents=[
                            FlexText(text=label, weight='bold', size='xl', color=color, align='center')
                        ]
                    ),
                    FlexBox(
                        layout='vertical',
                        margin='xl',
                        padding_all='24px',
                        background_color=C['card'],
                        corner_radius='16px',
                        contents=[
                            FlexText(
                                text=answer,
                                size='xl',
                                color=C['txt'],
                                wrap=True,
                                align='center',
                                weight='bold'
                            )
                        ]
                    )
                ]
            )
        )
    )

def create_games_list_flex(games):
    buttons = [
        FlexButton(
            action=MessageAction(
                label=f"{i}. {game.get('title', f'تحليل {i}')}",
                text=str(i)
            ),
            style='secondary',
            color=C['pri'],
            height='sm'
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
                    create_header("تحليل الشخصية"),
                    FlexBox(layout='vertical', margin='xl', spacing='sm', contents=buttons)
                ]
            )
        )
    )

def create_game_question_flex(title, question, progress):
    buttons = [
        FlexButton(
            action=MessageAction(label=f"{key}. {value}", text=key),
            style='secondary',
            color=C['pri'],
            height='sm'
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
                padding_all='20px',
                contents=[
                    FlexBox(
                        layout='horizontal',
                        contents=[
                            FlexText(text=title, weight='bold', size='lg', color=C['acc'], flex=1),
                            FlexText(text=progress, size='xs', color=C['txt2'], flex=0, align='end')
                        ]
                    ),
                    FlexSeparator(margin='md', color=C['bdr']),
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        padding_all='16px',
                        background_color=C['glass'],
                        corner_radius='8px',
                        contents=[
                            FlexText(text=question['question'], size='md', color=C['txt'], wrap=True)
                        ]
                    ),
                    FlexBox(layout='vertical', margin='lg', spacing='sm', contents=buttons)
                ]
            )
        )
    )

def calculate_result(answers, game_index):
    counts = {"أ": 0, "ب": 0, "ج": 0}
    for answer in answers:
        if answer in counts:
            counts[answer] += 1
    
    most_common = max(counts, key=counts.get)
    return cm.results.get(f"لعبة{game_index + 1}", {}).get(most_common, "شخصيتك فريدة ومميزة")

def create_game_result_flex(result):
    return FlexMessage(
        alt_text="النتيجة",
        contents=FlexBubble(
            direction='rtl',
            body=FlexBox(
                layout='vertical',
                background_color=C['bg'],
                padding_all='20px',
                contents=[
                    FlexText(
                        text='نتيجة التحليل',
                        weight='bold',
                        size='xl',
                        color=C['acc'],
                        align='center'
                    ),
                    FlexSeparator(margin='md', color=C['bdr']),
                    FlexBox(
                        layout='vertical',
                        margin='lg',
                        padding_all='16px',
                        background_color=C['glass'],
                        corner_radius='8px',
                        contents=[
                            FlexText(
                                text=result,
                                size='md',
                                color=C['txt'],
                                wrap=True,
                                line_spacing='6px'
                            )
                        ]
                    ),
                    FlexBox(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            FlexButton(
                                action=MessageAction(label='تحليل جديد', text='تحليل'),
                                style='primary',
                                color=C['pri'],
                                height='sm'
                            )
                        ]
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
    "لغز": ["لغز"],
    "اقتباسات": ["اقتباسات", "اقتباس", "حكمة"]
}

def find_command(text):
    text = text.lower().strip()
    for command, variations in COMMANDS.items():
        if text in [v.lower() for v in variations]:
            return command
    return None

def send_reply(reply_token, messages):
    try:
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
        logger.info("تم إرسال الرد بنجاح")
    except Exception as e:
        logger.error(f"خطأ في إرسال الرد: {e}")

@app.route("/", methods=["GET"])
def home():
    return "LINE Bot is running", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "bot": "active"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    logger.info(f"استلام webhook: {body[:100]}...")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("توقيع غير صحيح")
        abort(400)
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        abort(500)
    
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()
    
    logger.info(f"رسالة من {user_id}: {text}")
    
    try:
        if text_lower == "مساعدة":
            send_reply(event.reply_token, [
                create_help_flex(),
                TextMessage(text="اختر من الأزرار:", quick_reply=create_menu())
            ])
            return
        
        command = find_command(text)
        if command:
            if command == "لغز":
                riddle = cm.get_riddle()
                if riddle:
                    riddle_state[user_id] = riddle
                    send_reply(event.reply_token, [create_puzzle_flex(riddle)])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد ألغاز متاحة حالياً")])
            
            elif command == "اقتباسات":
                quote = cm.get_quote()
                if quote:
                    text_msg = f"اقتباس\n\n\"{quote.get('text', '')}\"\n\n— {quote.get('author', 'مجهول')}"
                    send_reply(event.reply_token, [TextMessage(text=text_msg)])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد اقتباسات متاحة")])
            
            elif command == "منشن":
                question = cm.get_mention()
                if question:
                    send_reply(event.reply_token, [TextMessage(text=f"سؤال منشن\n\n{question}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد أسئلة متاحة")])
            
            elif command == "موقف":
                situation = cm.get_situation()
                if situation:
                    send_reply(event.reply_token, [TextMessage(text=f"موقف للنقاش\n\n{situation}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد مواقف متاحة")])
            
            else:
                content = cm.get_content(command)
                if content:
                    send_reply(event.reply_token, [TextMessage(text=f"{command}\n\n{content}")])
                else:
                    send_reply(event.reply_token, [TextMessage(text="لا توجد بيانات متاحة")])
            return
        
        if text_lower == "لمح":
            if user_id in riddle_state:
                hint = riddle_state[user_id].get('hint', 'لا يوجد تلميح')
                send_reply(event.reply_token, [create_answer_flex(hint, "لمح")])
            return
        
        if text_lower == "جاوب":
            if user_id in riddle_state:
                answer = riddle_state.pop(user_id)['answer']
                send_reply(event.reply_token, [create_answer_flex(answer, "جاوب")])
            return
        
        if text_lower in ["تحليل", "تحليل شخصية", "شخصية"]:
            if cm.games:
                send_reply(event.reply_token, [create_games_list_flex(cm.games)])
            else:
                send_reply(event.reply_token, [TextMessage(text="لا توجد تحليلات متاحة")])
            return
        
        if text.isdigit() and user_id not in game_state:
            game_num = int(text)
            if 1 <= game_num <= len(cm.games):
                game_index = game_num - 1
                game_state[user_id] = {
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
        
        if user_id in game_state:
            state = game_state[user_id]
            answer_map = {
                "1": "أ", "2": "ب", "3": "ج",
                "a": "أ", "b": "ب", "c": "ج",
                "أ": "أ", "ب": "ب", "ج": "ج"
            }
            
            answer = answer_map.get(text_lower)
            if answer:
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
                    del game_state[user_id]
            return
    
    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}")
        send_reply(event.reply_token, [TextMessage(text="حدث خطأ، يرجى المحاولة مرة أخرى")])

def keep_alive():
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG")
    if url and not url.startswith("http"):
        url = f"https://{url}.onrender.com"
    
    while True:
        try:
            if url:
                response = requests.get(f"{url}/health", timeout=10)
                logger.info(f"Keep-alive ping: {response.status_code}")
            time.sleep(840)
        except Exception as e:
            logger.error(f"خطأ في keep-alive: {e}")
            time.sleep(60)

if __name__ == "__main__":
    if os.getenv("RENDER_EXTERNAL_URL") or os.getenv("REPL_SLUG"):
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("تم تشغيل خاصية Keep-alive")
    
    port = int(os.getenv("PORT", 5000))
    logger.info(f"تشغيل البوت على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
