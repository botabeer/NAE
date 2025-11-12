import json
import os
import logging
import random
from typing import List, Optional, Dict, Union
from threading import Lock
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FlexSendMessage,
    QuickReply, QuickReplyButton, MessageAction, BubbleContainer,
    BoxComponent, TextComponent, ButtonComponent, MessageAction as FlexMessageAction,
    SeparatorComponent
)

# === إعداد Logging ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# === إعداد متغيرات البيئة ===
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise RuntimeError("يجب تعيين LINE_CHANNEL_ACCESS_TOKEN و LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# === Locks للتزامن ===
content_lock = Lock()

# === مدير المحتوى ===
class ContentManager:
    def __init__(self):
        self.content_files: Dict[str, List[str]] = {}
        self.more_questions: List[str] = []
        self.proverbs_list: List[dict] = []
        self.riddles_list: List[dict] = []
        self.games_list: List[dict] = []
        self.poems_list: List[dict] = []
        self.quotes_list: List[dict] = []
        self.detailed_results: Dict = {}
        self.used_indices: Dict[str, List[int]] = {}

    def load_file_lines(self, filename: str) -> List[str]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return []
        try:
            with open(filename, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                logger.info(f"تم تحميل {len(lines)} سطر من {filename}")
                return lines
        except Exception as e:
            logger.error(f"خطأ في قراءة الملف {filename}: {e}")
            return []

    def load_json_file(self, filename: str) -> Union[dict, list]:
        if not os.path.exists(filename):
            logger.warning(f"الملف غير موجود: {filename}")
            return [] if filename.endswith("s.json") else {}
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                logger.info(f"تم تحميل {filename}")
                return data
        except Exception as e:
            logger.error(f"خطأ في قراءة أو تحليل JSON {filename}: {e}")
            return [] if filename.endswith("s.json") else {}

    def initialize(self):
        self.content_files = {
            "سؤال": self.load_file_lines("questions.txt"),
            "تحدي": self.load_file_lines("challenges.txt"),
            "اعتراف": self.load_file_lines("confessions.txt"),
        }

        self.used_indices = {key: [] for key in self.content_files.keys()}
        for key in ["أكثر","أمثال","لغز","شعر","اقتباسات"]:
            self.used_indices[key] = []

        self.more_questions = self.load_file_lines("more_file.txt")
        self.proverbs_list = self.load_json_file("proverbs.json")
        self.riddles_list = self.load_json_file("riddles.json")
        self.detailed_results = self.load_json_file("detailed_results.json")
        self.poems_list = self.load_json_file("poems.json")
        self.quotes_list = self.load_json_file("quotes.json")

        data = self.load_json_file("personality_games.json")
        if isinstance(data, dict):
            self.games_list = [data[key] for key in sorted(data.keys())]
        else:
            self.games_list = []

        logger.info("تم تهيئة جميع الملفات بنجاح")

    def get_random_index(self, command: str, max_length: int) -> int:
        with content_lock:
            if len(self.used_indices[command]) >= max_length:
                self.used_indices[command] = []
            available_indices = [i for i in range(max_length) if i not in self.used_indices[command]]
            index = random.choice(available_indices) if available_indices else random.randint(0,max_length-1)
            self.used_indices[command].append(index)
            return index

    def get_content(self, command: str) -> Optional[str]:
        file_list = self.content_files.get(command, [])
        if not file_list: return None
        index = self.get_random_index(command, len(file_list))
        return file_list[index]

    def get_more_question(self) -> Optional[str]:
        if not self.more_questions: return None
        index = self.get_random_index("أكثر", len(self.more_questions))
        return self.more_questions[index]

    def get_proverb(self) -> Optional[dict]:
        if not self.proverbs_list: return None
        index = self.get_random_index("أمثال", len(self.proverbs_list))
        return self.proverbs_list[index]

    def get_riddle(self) -> Optional[dict]:
        if not self.riddles_list: return None
        index = self.get_random_index("لغز", len(self.riddles_list))
        return self.riddles_list[index]

    def get_poem(self) -> Optional[str]:
        if not self.poems_list: return None
        index = self.get_random_index("شعر", len(self.poems_list))
        poem_entry = self.poems_list[index]
        return f"📝 شعر - {poem_entry.get('poet','')}:\n\n{poem_entry.get('text','')}"

    def get_quote(self) -> Optional[str]:
        if not self.quotes_list: return None
        index = self.get_random_index("اقتباسات", len(self.quotes_list))
        quote_entry = self.quotes_list[index]
        return f"💭 اقتباس - {quote_entry.get('author','')}:\n\n{quote_entry.get('text','')}"

# === تهيئة مدير المحتوى ===
content_manager = ContentManager()
content_manager.initialize()

# === الأزرار الرئيسية Quick Reply ===
def create_main_menu() -> QuickReply:
    return QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="❓ سؤال", text="سؤال")),
        QuickReplyButton(action=MessageAction(label="🎯 تحدي", text="تحدي")),
        QuickReplyButton(action=MessageAction(label="💬 اعتراف", text="اعتراف")),
        QuickReplyButton(action=MessageAction(label="✨ أكثر", text="أكثر")),
        QuickReplyButton(action=MessageAction(label="📝 شعر", text="شعر")),
        QuickReplyButton(action=MessageAction(label="💭 اقتباسات", text="اقتباسات")),
        QuickReplyButton(action=MessageAction(label="🧩 لغز", text="لغز")),
        QuickReplyButton(action=MessageAction(label="📜 أمثال", text="أمثال")),
        QuickReplyButton(action=MessageAction(label="🎮 لعبة", text="لعبه")),
    ])

# === Flex Messages للألعاب ===
def create_games_list_flex(games: list) -> FlexSendMessage:
    """قائمة الألعاب بتصميم Flex احترافي"""
    game_buttons = []
    for i, game in enumerate(games[:10], 1):
        game_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(
                    label=f"{i}. {game.get('title', f'اللعبة {i}')}",
                    text=str(i)
                ),
                style='secondary',
                color='#333333',
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text="🎮 قائمة الألعاب",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text='🎮',
                        size='xxl',
                        align='center',
                        margin='none'
                    ),
                    TextComponent(
                        text='الألعاب المتاحة',
                        weight='bold',
                        size='xl',
                        color='#1a1a1a',
                        align='center',
                        margin='md'
                    ),
                    SeparatorComponent(margin='lg', color='#f5f5f5'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='sm',
                        contents=game_buttons
                    )
                ],
                paddingAll='24px',
                backgroundColor='#ffffff'
            )
        )
    )

def create_game_question_flex(game_title: str, question: dict, progress: str) -> FlexSendMessage:
    """سؤال اللعبة بتصميم Flex ناعم"""
    option_buttons = []
    for key, value in question['options'].items():
        option_buttons.append(
            ButtonComponent(
                action=FlexMessageAction(label=f"{key}. {value}", text=key),
                style='secondary',
                color='#2c2c2c',
                height='sm'
            )
        )
    
    return FlexSendMessage(
        alt_text=f"🎮 {game_title}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    BoxComponent(
                        layout='horizontal',
                        contents=[
                            TextComponent(
                                text='🎮',
                                size='lg',
                                flex=0,
                                color='#4a4a4a'
                            ),
                            TextComponent(
                                text=game_title,
                                weight='bold',
                                size='lg',
                                color='#1a1a1a',
                                margin='md',
                                flex=1
                            ),
                            TextComponent(
                                text=progress,
                                size='sm',
                                color='#999999',
                                flex=0,
                                align='end'
                            )
                        ]
                    ),
                    SeparatorComponent(margin='lg', color='#f5f5f5'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=question['question'],
                                size='md',
                                color='#2c2c2c',
                                wrap=True,
                                lineSpacing='6px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor='#fafafa',
                        cornerRadius='12px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        spacing='sm',
                        contents=option_buttons
                    )
                ],
                paddingAll='24px',
                backgroundColor='#ffffff'
            )
        )
    )

def create_game_result_flex(result_text: str, stats: str) -> FlexSendMessage:
    """نتيجة اللعبة بتصميم Flex مريح"""
    return FlexSendMessage(
        alt_text="🏆 النتيجة",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                contents=[
                    TextComponent(
                        text='🏆',
                        size='xxl',
                        align='center',
                        margin='none'
                    ),
                    TextComponent(
                        text='نتيجتك',
                        weight='bold',
                        size='xl',
                        color='#1a1a1a',
                        align='center',
                        margin='md'
                    ),
                    SeparatorComponent(margin='lg', color='#f5f5f5'),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            TextComponent(
                                text=result_text,
                                size='md',
                                color='#2c2c2c',
                                wrap=True,
                                lineSpacing='6px'
                            )
                        ],
                        paddingAll='16px',
                        backgroundColor='#fafafa',
                        cornerRadius='12px'
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='lg',
                        contents=[
                            TextComponent(
                                text=stats,
                                size='sm',
                                color='#888888',
                                wrap=True,
                                align='center'
                            )
                        ]
                    ),
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=[
                            ButtonComponent(
                                action=FlexMessageAction(label='🎮 لعبة جديدة', text='لعبه'),
                                style='primary',
                                color='#333333',
                                height='sm'
                            )
                        ]
                    )
                ],
                paddingAll='24px',
                backgroundColor='#ffffff'
            )
        )
    )

# === حالات المستخدمين ===
user_game_state: Dict[str, dict] = {}
user_proverb_state: Dict[str, dict] = {}
user_riddle_state: Dict[str, dict] = {}

# === خريطة الأوامر ===
COMMANDS_MAP = {
    "سؤال":["سؤال","سوال","اسأله","اسئلة","اسأل"],
    "تحدي":["تحدي","تحديات","تحد"],
    "اعتراف":["اعتراف","اعترافات"],
    "أكثر":["أكثر","اكثر","زيادة"],
    "أمثال":["أمثال","امثال","مثل"],
    "لغز":["لغز","الغاز","ألغاز"],
    "شعر":["شعر"],
    "اقتباسات":["اقتباسات","اقتباس","قول"]
}

def find_command(text:str) -> Optional[str]:
    text_lower = text.lower().strip()
    for key, variants in COMMANDS_MAP.items():
        if text_lower in [v.lower() for v in variants]:
            return key
    return None

# === دوال الألعاب ===
def calculate_result(answers: List[str], game_index: int) -> tuple:
    count = {"أ":0,"ب":0,"ج":0}
    for ans in answers:
        if ans in count: count[ans] +=1
    most_common = max(count, key=count.get)
    game_key = f"لعبة{game_index+1}"
    result_text = content_manager.detailed_results.get(game_key,{}).get(
        most_common,f"✅ إجابتك الأكثر: {most_common}\n\nنتيجتك تعكس شخصية فريدة!"
    )
    stats = f"📊 إحصائياتك: أ: {count['أ']} | ب: {count['ب']} | ج: {count['ج']}"
    return result_text, stats

def handle_game_selection(event, user_id: str, num: int):
    if 1 <= num <= len(content_manager.games_list):
        game_index = num - 1
        user_game_state[user_id] = {"game_index": game_index, "question_index": 0, "answers": []}
        game = content_manager.games_list[game_index]
        first_q = game["questions"][0]
        progress = f"1/{len(game['questions'])}"
        
        flex_msg = create_game_question_flex(
            game.get('title', f'اللعبة {num}'),
            first_q,
            progress
        )
        line_bot_api.reply_message(event.reply_token, flex_msg)

def handle_game_answer(event, user_id: str, text: str):
    state = user_game_state.get(user_id)
    if not state: return
    
    answer_map = {"1":"أ","2":"ب","3":"ج","a":"أ","b":"ب","c":"ج"}
    answer = answer_map.get(text.lower(), text)
    
    if answer in ["أ","ب","ج"]:
        state["answers"].append(answer)
        game = content_manager.games_list[state["game_index"]]
        state["question_index"] += 1
        
        if state["question_index"] < len(game["questions"]):
            q = game["questions"][state["question_index"]]
            progress = f"{state['question_index']+1}/{len(game['questions'])}"
            
            flex_msg = create_game_question_flex(
                game.get('title', 'اللعبة'),
                q,
                progress
            )
            line_bot_api.reply_message(event.reply_token, flex_msg)
        else:
            result_text, stats = calculate_result(state["answers"], state["game_index"])
            flex_msg = create_game_result_flex(result_text, stats)
            line_bot_api.reply_message(event.reply_token, flex_msg)
            del user_game_state[user_id]

# === دوال المحتوى ===
def handle_content_command(event, command: str):
    if command == "أمثال":
        proverb = content_manager.get_proverb()
        if not proverb:
            content = "⚠️ لا توجد أمثال متاحة حالياً."
        else:
            user_proverb_state[event.source.user_id] = proverb
            content = f"📜 المثل:\n\n{proverb['question']}\n\n━━━━━━━━━━━━━━━\n💡 اكتب (جاوب) لمعرفة المعنى"
    elif command == "لغز":
        riddle = content_manager.get_riddle()
        if not riddle:
            content = "⚠️ لا توجد ألغاز متاحة حالياً."
        else:
            user_riddle_state[event.source.user_id] = riddle
            content = f"🧩 اللغز:\n\n{riddle['question']}\n\n━━━━━━━━━━━━━━━\n💡 اكتب (لمح) للتلميح\n✅ اكتب (جاوب) للإجابة"
    elif command == "أكثر":
        question = content_manager.get_more_question()
        content = f"✨ سؤال محير:\n\n{question}\n\n━━━━━━━━━━━━━━━" if question else "⚠️ لا توجد أسئلة متاحة."
    elif command == "شعر":
        poem = content_manager.get_poem()
        content = f"{poem}\n\n━━━━━━━━━━━━━━━" if poem else "⚠️ لا يوجد شعر متاح."
    elif command == "اقتباسات":
        quote = content_manager.get_quote()
        content = f"{quote}\n\n━━━━━━━━━━━━━━━" if quote else "⚠️ لا توجد اقتباسات متاحة."
    else:
        emoji_map = {"سؤال": "❓", "تحدي": "🎯", "اعتراف": "💬"}
        emoji = emoji_map.get(command, "📌")
        text_content = content_manager.get_content(command)
        content = f"{emoji} {command}:\n\n{text_content}\n\n━━━━━━━━━━━━━━━" if text_content else f"⚠️ لا توجد بيانات متاحة."
    
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=content, quick_reply=create_main_menu()))

def handle_answer_command(event, user_id: str):
    if user_id in user_proverb_state:
        proverb = user_proverb_state.pop(user_id)
        msg = f"✅ معنى المثل:\n\n{proverb['answer']}\n\n━━━━━━━━━━━━━━━"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))
    elif user_id in user_riddle_state:
        riddle = user_riddle_state.pop(user_id)
        msg = f"✅ الإجابة الصحيحة:\n\n{riddle['answer']}\n\n━━━━━━━━━━━━━━━"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

def handle_hint_command(event, user_id: str):
    if user_id in user_riddle_state:
        riddle = user_riddle_state[user_id]
        hint = riddle.get('hint','لا يوجد تلميح')
        msg = f"💡 التلميح:\n\n{hint}\n\n━━━━━━━━━━━━━━━"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg, quick_reply=create_main_menu()))

# === Routes ===
@app.route("/", methods=["GET"])
def home():
    return "✅ البوت يعمل بنجاح!", 200

@app.route("/health", methods=["GET"])
def health_check():
    return {"status":"healthy","service":"line-bot"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature","")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("توقيع غير صالح")
        abort(400)
    except Exception as e:
        logger.error(f"خطأ في معالجة الطلب: {e}")
        abort(500)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower()

    try:
        if text_lower in ["مساعدة","help","بداية","start"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="👋 مرحباً بك!\n\nاختر من القائمة أدناه:",
                    quick_reply=create_main_menu()
                )
            )
            return

        command = find_command(text)
        if command:
            handle_content_command(event, command)
            return

        if text_lower in ["جاوب","الجواب","الاجابة","اجابة"]:
            handle_answer_command(event, user_id)
            return

        if text_lower in ["لمح","تلميح","hint"]:
            handle_hint_command(event, user_id)
            return

        if text_lower in ["لعبه","لعبة","العاب","ألعاب","game"]:
            if content_manager.games_list:
                flex_msg = create_games_list_flex(content_manager.games_list)
                line_bot_api.reply_message(event.reply_token, flex_msg)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="⚠️ لا توجد ألعاب متاحة حالياً.",
                        quick_reply=create_main_menu()
                    )
                )
            return

        if text.isdigit():
            handle_game_selection(event, user_id, int(text))
            return

        if user_id in user_game_state:
            handle_game_answer(event, user_id, text)
            return

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="👋 مرحباً! اختر من الأزرار أدناه",
                quick_reply=create_main_menu()
            )
        )

    except Exception as e:
        logger.error(f"خطأ في معالجة الرسالة: {e}", exc_info=True)
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="⚠️ حدث خطأ، يرجى المحاولة مرة أخرى",
                    quick_reply=create_main_menu()
                )
            )
        except:
            pass

# === تشغيل التطبيق ===
if __name__=="__main__":
    port = int(os.getenv("PORT",5000))
    logger.info(f"البوت يعمل على المنفذ {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
