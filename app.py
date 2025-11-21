import json
import os
import logging
import random
import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

# ═══════════════════════════════════════════════════════════
# إعدادات التطبيق
# ═══════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not TOKEN or not SECRET:
    raise RuntimeError("❌ Missing LINE credentials")

bot = LineBotApi(TOKEN)
handler = WebhookHandler(SECRET)

# ═══════════════════════════════════════════════════════════
# الألوان - وضع داكن أنيق
# ═══════════════════════════════════════════════════════════
COLORS = {
    'bg': '#0A0A0F',
    'card': '#1A1A2E',
    'card_light': '#252540',
    'primary': '#9D7EF2',
    'primary_light': '#B39DFF',
    'accent': '#8B5CF6',
    'blue': '#60A5FA',
    'cyan': '#22D3EE',
    'pink': '#F472B6',
    'orange': '#FB923C',
    'green': '#4ADE80',
    'yellow': '#FBBF24',
    'text': '#FFFFFF',
    'text_dim': '#C0C0D0',
    'text_muted': '#8888A0',
    'border': '#9D7EF2'
}

# ═══════════════════════════════════════════════════════════
# الأوامر المتاحة
# ═══════════════════════════════════════════════════════════
COMMANDS = {
    "سؤال": ["سؤال", "سوال"],
    "تحدي": ["تحدي"],
    "اعتراف": ["اعتراف"],
    "منشن": ["منشن"],
    "موقف": ["موقف"],
    "لغز": ["لغز", "الغاز"],
    "اقتباسات": ["اقتباسات", "اقتباس", "حكمة"],
    "تحليل": ["تحليل", "شخصية"],
    "مساعدة": ["مساعدة", "أوامر"]
}

# معلومات كل أمر
COMMAND_INFO = {
    'سؤال': ('💭', 'أسئلة للنقاش', COLORS['blue']),
    'منشن': ('💬', 'أسئلة منشن', COLORS['cyan']),
    'اعتراف': ('💗', 'اعترافات جريئة', COLORS['pink']),
    'تحدي': ('🎯', 'تحديات ممتعة', COLORS['orange']),
    'موقف': ('🤔', 'مواقف للنقاش', COLORS['yellow']),
    'اقتباسات': ('✨', 'حكم وأقوال', COLORS['green']),
    'لغز': ('💡', 'ألغاز ذهنية', COLORS['primary']),
    'تحليل': ('🎭', 'تحليل الشخصية', COLORS['primary_light'])
}

# جميع الكلمات المفتاحية
ALL_KEYWORDS = set()
for variants in COMMANDS.values():
    ALL_KEYWORDS.update(x.lower() for x in variants)
ALL_KEYWORDS.update({"لمح", "تلميح", "جاوب", "الجواب"})
ALL_KEYWORDS.update(str(i) for i in range(1, 11))
ALL_KEYWORDS.update({"أ", "ب", "ج", "a", "b", "c"})

ANSWER_MAP = {
    "1": "أ", "2": "ب", "3": "ج",
    "a": "أ", "b": "ب", "c": "ج",
    "أ": "أ", "ب": "ب", "ج": "ج"
}

# ═══════════════════════════════════════════════════════════
# مدير المحتوى
# ═══════════════════════════════════════════════════════════
class ContentManager:
    def __init__(self):
        self.data = {}
        self.used = {}
    
    def _load_text_file(self, path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return [line.strip() for line in f if line.strip()]
        except Exception as e:
            logging.error(f"Error loading {path}: {e}")
        return []
    
    def _load_json_file(self, path, default=None):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {path}: {e}")
        return default or []
    
    def initialize(self):
        self.data = {
            'سؤال': self._load_text_file("questions.txt"),
            'تحدي': self._load_text_file("challenges.txt"),
            'اعتراف': self._load_text_file("confessions.txt"),
            'منشن': self._load_text_file("more_questions.txt"),
            'موقف': self._load_text_file("situations.txt"),
            'لغز': self._load_json_file("riddles.json", []),
            'اقتباس': self._load_json_file("quotes.json", []),
            'تحليل': self._load_json_file("personality_games.json", {}),
            'نتائج': self._load_json_file("detailed_results.json", {})
        }
        
        if isinstance(self.data['تحليل'], dict):
            self.data['تحليل'] = [
                self.data['تحليل'][key] 
                for key in sorted(self.data['تحليل'].keys())
            ]
        
        self.used = {key: [] for key in self.data}
    
    def get_random(self, key):
        items = self.data.get(key, [])
        if not items:
            return None
        
        if len(self.used.get(key, [])) >= len(items):
            self.used[key] = []
        
        available = [i for i in range(len(items)) if i not in self.used.get(key, [])]
        index = random.choice(available) if available else 0
        
        self.used.setdefault(key, []).append(index)
        return items[index]

content_manager = ContentManager()
content_manager.initialize()

# ═══════════════════════════════════════════════════════════
# مدير الجلسات
# ═══════════════════════════════════════════════════════════
class SessionManager:
    def __init__(self):
        self.riddles = {}
        self.games = {}
    
    def set_riddle(self, user_id, riddle):
        self.riddles[user_id] = {'data': riddle, 'time': time.time()}
    
    def get_riddle(self, user_id):
        return self.riddles.get(user_id, {}).get('data')
    
    def clear_riddle(self, user_id):
        self.riddles.pop(user_id, None)
    
    def start_game(self, user_id, game_index):
        self.games[user_id] = {
            'game_index': game_index,
            'question_index': 0,
            'answers': [],
            'time': time.time()
        }
    
    def get_game(self, user_id):
        return self.games.get(user_id)
    
    def is_in_game(self, user_id):
        return user_id in self.games
    
    def add_answer(self, user_id, answer):
        if user_id in self.games:
            self.games[user_id]['answers'].append(answer)
            self.games[user_id]['question_index'] += 1
    
    def end_game(self, user_id):
        return self.games.pop(user_id, None)

session_manager = SessionManager()

# ═══════════════════════════════════════════════════════════
# القائمة السريعة
# ═══════════════════════════════════════════════════════════
QUICK_MENU = QuickReply(items=[
    QuickReplyButton(action=MessageAction(
        label=f"{COMMAND_INFO[cmd][0]} {cmd}",
        text=cmd
    ))
    for cmd in ["سؤال", "منشن", "اعتراف", "تحدي", "موقف", "اقتباسات", "لغز", "تحليل"]
])

# ═══════════════════════════════════════════════════════════
# Flex Messages - التصميم الداكن الأنيق
# ═══════════════════════════════════════════════════════════

def create_card_with_border(color, inner_contents):
    """إنشاء بطاقة بحدود ملونة"""
    return BoxComponent(
        layout='vertical',
        backgroundColor=COLORS['card'],
        cornerRadius='24px',
        paddingAll='3px',
        borderWidth='2px',
        borderColor=color,
        margin='md',
        contents=[
            BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                cornerRadius='22px',
                paddingAll='28px',
                contents=inner_contents
            )
        ]
    )

def create_button(label, color, is_primary=False):
    """إنشاء زر بتصميم أنيق"""
    return BoxComponent(
        layout='vertical',
        backgroundColor=color if is_primary else COLORS['card_light'],
        cornerRadius='16px',
        paddingAll='14px',
        action=MessageAction(label=label, text=label),
        contents=[
            TextComponent(
                text=label,
                size='md',
                color=COLORS['text'],
                weight='bold',
                align='center'
            )
        ]
    )

def flex_help():
    """رسالة المساعدة"""
    command_rows = []
    for cmd, (icon, desc, color) in COMMAND_INFO.items():
        command_rows.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=COLORS['card'],
                cornerRadius='16px',
                paddingAll='18px',
                margin='md',
                contents=[
                    TextComponent(
                        text=icon,
                        size='xl',
                        flex=0,
                        color=color
                    ),
                    BoxComponent(
                        layout='vertical',
                        paddingStart='16px',
                        flex=1,
                        contents=[
                            TextComponent(
                                text=cmd,
                                size='md',
                                color=color,
                                weight='bold'
                            ),
                            TextComponent(
                                text=desc,
                                size='sm',
                                color=COLORS['text_muted'],
                                margin='xs'
                            )
                        ]
                    )
                ]
            )
        )
    
    return FlexSendMessage(
        alt_text="📋 قائمة الأوامر",
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        alignItems='center',
                        contents=[
                            TextComponent(
                                text="بوت عناد المالكي",
                                size='xxl',
                                color=COLORS['primary_light'],
                                weight='bold',
                                margin='lg'
                            ),
                            TextComponent(
                                text="─────────",
                                size='sm',
                                color=COLORS['card_light'],
                                margin='md'
                            )
                        ]
                    ),
                    # قائمة الأوامر
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=command_rows
                    )
                ]
            )
        )
    )

def flex_simple(command_type, text):
    """رسالة بسيطة (سؤال، تحدي، إلخ)"""
    icon, title, color = COMMAND_INFO[command_type]
    
    # التأكد من أن النص ليس فارغًا
    if not text or not text.strip():
        text = "المحتوى غير متوفر حالياً"
    
    return FlexSendMessage(
        alt_text=f"{icon} {title}",
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(color, [
                        # العنوان
                        BoxComponent(
                            layout='horizontal',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text=icon,
                                    size='xl',
                                    flex=0
                                ),
                                TextComponent(
                                    text=title,
                                    size='lg',
                                    color=color,
                                    weight='bold',
                                    margin='md',
                                    flex=1
                                )
                            ]
                        ),
                        # الخط الفاصل
                        BoxComponent(
                            layout='vertical',
                            height='2px',
                            backgroundColor=color,
                            margin='lg'
                        ),
                        # المحتوى
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='20px',
                            margin='xl',
                            contents=[
                                TextComponent(
                                    text=str(text).strip(),
                                    size='lg',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center'
                                )
                            ]
                        ),
                        # زر التالي
                        BoxComponent(
                            layout='horizontal',
                            margin='xl',
                            contents=[
                                create_button(f"💫 التالي", color, True)
                            ]
                        )
                    ])
                ]
            )
        )
    )

def flex_quote(quote_data):
    """رسالة اقتباس"""
    quote_text = quote_data.get('quote', 'اقتباس ملهم')
    author = quote_data.get('author', 'مجهول')
    
    # التأكد من صحة البيانات
    if not quote_text or not quote_text.strip():
        quote_text = "الحياة قصيرة، اجعلها ذات معنى"
    if not author or not author.strip():
        author = "مجهول"
    
    return FlexSendMessage(
        alt_text="✨ اقتباس",
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(COLORS['green'], [
                        # الأيقونة
                        BoxComponent(
                            layout='vertical',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text="✨",
                                    size='xxl'
                                )
                            ]
                        ),
                        # النص
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='24px',
                            margin='xl',
                            contents=[
                                TextComponent(
                                    text=f"« {str(quote_text).strip()} »",
                                    size='lg',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center'
                                )
                            ]
                        ),
                        # المؤلف
                        BoxComponent(
                            layout='vertical',
                            alignItems='center',
                            margin='lg',
                            contents=[
                                TextComponent(
                                    text=f"— {str(author).strip()}",
                                    size='md',
                                    color=COLORS['green'],
                                    weight='bold'
                                )
                            ]
                        ),
                        # زر التالي
                        BoxComponent(
                            layout='horizontal',
                            margin='xl',
                            contents=[
                                create_button("✨ اقتباس آخر", COLORS['green'], True)
                            ]
                        )
                    ])
                ]
            )
        )
    )

def flex_riddle(riddle):
    """رسالة اللغز"""
    question = riddle.get('question', 'لغز مثير للتفكير')
    
    # التأكد من صحة السؤال
    if not question or not question.strip():
        question = "ما هو الشيء الذي يكتب ولا يقرأ؟"
    
    return FlexSendMessage(
        alt_text="💡 لغز",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(COLORS['primary'], [
                        # العنوان
                        BoxComponent(
                            layout='horizontal',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text="💡",
                                    size='xl',
                                    flex=0
                                ),
                                TextComponent(
                                    text="لغز ذهني",
                                    size='lg',
                                    color=COLORS['primary'],
                                    weight='bold',
                                    margin='md'
                                )
                            ]
                        ),
                        # الخط الفاصل
                        BoxComponent(
                            layout='vertical',
                            height='2px',
                            backgroundColor=COLORS['primary'],
                            margin='lg'
                        ),
                        # السؤال
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='24px',
                            margin='xl',
                            contents=[
                                TextComponent(
                                    text=str(question).strip(),
                                    size='lg',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center'
                                )
                            ]
                        ),
                        # الأزرار
                        BoxComponent(
                            layout='horizontal',
                            spacing='md',
                            margin='xl',
                            contents=[
                                create_button("💡 تلميح", COLORS['card_light'], False),
                                create_button("✅ الجواب", COLORS['primary'], True)
                            ]
                        )
                    ])
                ]
            )
        )
    )

def flex_answer(text, is_hint):
    """رسالة الإجابة أو التلميح"""
    title = "💡 تلميح" if is_hint else "✅ الجواب"
    color = COLORS['yellow'] if is_hint else COLORS['green']
    
    # التأكد من صحة النص
    if not text or not text.strip():
        text = "معلومة مفيدة!" if is_hint else "الإجابة الصحيحة!"
    
    return FlexSendMessage(
        alt_text=title,
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(color, [
                        # العنوان
                        BoxComponent(
                            layout='vertical',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text=title,
                                    size='xl',
                                    color=color,
                                    weight='bold'
                                )
                            ]
                        ),
                        # المحتوى
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='24px',
                            margin='xl',
                            contents=[
                                TextComponent(
                                    text=str(text).strip(),
                                    size='lg',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center'
                                )
                            ]
                        )
                    ])
                ]
            )
        )
    )

def flex_games():
    """قائمة الألعاب"""
    games = content_manager.data.get('تحليل', [])
    if not games:
        return None
    
    game_rows = []
    for i, game in enumerate(games[:10], 1):
        game_rows.append(
            BoxComponent(
                layout='horizontal',
                backgroundColor=COLORS['card'],
                cornerRadius='16px',
                paddingAll='16px',
                margin='md',
                action=MessageAction(label=str(i), text=str(i)),
                contents=[
                    TextComponent(
                        text=str(i),
                        size='xl',
                        color=COLORS['primary'],
                        weight='bold',
                        flex=0
                    ),
                    TextComponent(
                        text=game.get('title', 'لعبة'),
                        size='md',
                        color=COLORS['text'],
                        weight='bold',
                        margin='md',
                        flex=1
                    )
                ]
            )
        )
    
    return FlexSendMessage(
        alt_text="🎭 اختبارات الشخصية",
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='24px',
                contents=[
                    # العنوان
                    BoxComponent(
                        layout='vertical',
                        alignItems='center',
                        contents=[
                            TextComponent(
                                text="🎭",
                                size='xxl'
                            ),
                            TextComponent(
                                text="اختبارات الشخصية",
                                size='xl',
                                color=COLORS['primary_light'],
                                weight='bold',
                                margin='md'
                            )
                        ]
                    ),
                    # قائمة الألعاب
                    BoxComponent(
                        layout='vertical',
                        margin='xl',
                        contents=game_rows
                    )
                ]
            )
        )
    )

def flex_game_q(game, question_index):
    """سؤال اختبار الشخصية"""
    questions = game.get('questions', [])
    if question_index >= len(questions):
        return None
    
    q = questions[question_index]
    q_text = q.get('q', 'سؤال مثير')
    options = q.get('options', {})
    
    # التأكد من صحة البيانات
    if not q_text or not q_text.strip():
        q_text = "ما هو اختيارك المفضل؟"
    
    # التأكد من وجود خيارات صحيحة
    if not options or len(options) == 0:
        options = {'أ': 'الخيار الأول', 'ب': 'الخيار الثاني', 'ج': 'الخيار الثالث'}
    
    # بناء قائمة الخيارات
    option_boxes = []
    for key, value in options.items():
        if key and value and str(value).strip():  # التأكد من صحة البيانات
            option_boxes.append(
                BoxComponent(
                    layout='horizontal',
                    backgroundColor=COLORS['card'],
                    cornerRadius='12px',
                    paddingAll='14px',
                    action=MessageAction(label=str(key), text=str(key)),
                    contents=[
                        TextComponent(
                            text=str(key),
                            size='lg',
                            color=COLORS['primary'],
                            weight='bold',
                            flex=0
                        ),
                        TextComponent(
                            text=str(value).strip(),
                            size='md',
                            color=COLORS['text'],
                            margin='md',
                            flex=1
                        )
                    ]
                )
            )
    
    # إذا لم تكن هناك خيارات صحيحة، أضف خيارات افتراضية
    if len(option_boxes) == 0:
        option_boxes = [
            BoxComponent(
                layout='horizontal',
                backgroundColor=COLORS['card'],
                cornerRadius='12px',
                paddingAll='14px',
                action=MessageAction(label='أ', text='أ'),
                contents=[
                    TextComponent(text='أ', size='lg', color=COLORS['primary'], weight='bold', flex=0),
                    TextComponent(text='الخيار الأول', size='md', color=COLORS['text'], margin='md', flex=1)
                ]
            )
        ]
    
    return FlexSendMessage(
        alt_text=f"السؤال {question_index + 1}",
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(COLORS['primary'], [
                        # رقم السؤال
                        BoxComponent(
                            layout='vertical',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text=f"سؤال {question_index + 1} من {len(questions)}",
                                    size='sm',
                                    color=COLORS['text_dim']
                                )
                            ]
                        ),
                        # نص السؤال
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='24px',
                            margin='lg',
                            contents=[
                                TextComponent(
                                    text=str(q_text).strip(),
                                    size='lg',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center',
                                    weight='bold'
                                )
                            ]
                        ),
                        # الخيارات
                        BoxComponent(
                            layout='vertical',
                            spacing='md',
                            margin='xl',
                            contents=option_boxes
                        )
                    ])
                ]
            )
        )
    )

def calc_result(answers, game_index):
    """حساب النتيجة"""
    games = content_manager.data.get('تحليل', [])
    results_data = content_manager.data.get('نتائج', {})
    
    if game_index >= len(games):
        return {'type': 'unknown', 'text': 'نتيجة غير معروفة'}
    
    game = games[game_index]
    game_id = game.get('id', '')
    
    count = {'أ': 0, 'ب': 0, 'ج': 0}
    for ans in answers:
        count[ans] = count.get(ans, 0) + 1
    
    result_type = max(count, key=count.get)
    
    result_data = results_data.get(game_id, {}).get(result_type, {})
    if not result_data:
        result_data = game.get('results', {}).get(result_type, {})
    
    return {
        'type': result_type,
        'title': result_data.get('title', 'نتيجتك'),
        'text': result_data.get('text', 'نتيجة مميزة!'),
        'emoji': result_data.get('emoji', '✨')
    }

def flex_result(result):
    """عرض النتيجة"""
    emoji = result.get('emoji', '✨')
    title = result.get('title', 'نتيجتك')
    text = result.get('text', 'نتيجة مميزة!')
    
    # التأكد من صحة البيانات
    if not emoji or not emoji.strip():
        emoji = '✨'
    if not title or not title.strip():
        title = 'نتيجتك'
    if not text or not text.strip():
        text = 'نتيجة رائعة ومميزة!'
    
    return FlexSendMessage(
        alt_text="🎉 نتيجتك",
        quick_reply=QUICK_MENU,
        contents=BubbleContainer(
            direction='rtl',
            body=BoxComponent(
                layout='vertical',
                backgroundColor=COLORS['bg'],
                paddingAll='0px',
                contents=[
                    create_card_with_border(COLORS['primary_light'], [
                        # الأيقونة
                        BoxComponent(
                            layout='vertical',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text=str(emoji).strip(),
                                    size='xxl'
                                ),
                                TextComponent(
                                    text="🎉 نتيجتك 🎉",
                                    size='md',
                                    color=COLORS['text_dim'],
                                    margin='md'
                                )
                            ]
                        ),
                        # العنوان
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['primary'],
                            cornerRadius='16px',
                            paddingAll='16px',
                            margin='xl',
                            alignItems='center',
                            contents=[
                                TextComponent(
                                    text=str(title).strip(),
                                    size='xl',
                                    color=COLORS['text'],
                                    weight='bold',
                                    align='center'
                                )
                            ]
                        ),
                        # النص
                        BoxComponent(
                            layout='vertical',
                            backgroundColor=COLORS['card_light'],
                            cornerRadius='16px',
                            paddingAll='24px',
                            margin='lg',
                            contents=[
                                TextComponent(
                                    text=str(text).strip(),
                                    size='md',
                                    color=COLORS['text'],
                                    wrap=True,
                                    align='center'
                                )
                            ]
                        ),
                        # زر اختبار آخر
                        BoxComponent(
                            layout='horizontal',
                            margin='xl',
                            contents=[
                                create_button("🎭 اختبار آخر", COLORS['primary_light'], True)
                            ]
                        )
                    ])
                ]
            )
        )
    )

# ═══════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok", "message": "Bot is healthy"}, 200

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        logging.error(f"Callback error: {e}")
    
    return "OK"

# ═══════════════════════════════════════════════════════════
# Message Handler
# ═══════════════════════════════════════════════════════════

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    text_lower = text.lower().strip()
    
    # تجاهل الرسائل غير المتعلقة
    if text_lower not in ALL_KEYWORDS and not session_manager.is_in_game(user_id):
        return
    
    try:
        # البحث عن الأمر المناسب
        command = None
        for cmd, variants in COMMANDS.items():
            if text_lower in [v.lower() for v in variants]:
                command = cmd
                break
        
        # ═══════════════════════════════════════════════════════════
        # معالجة الأوامر
        # ═══════════════════════════════════════════════════════════
        
        # أمر المساعدة
        if command == "مساعدة":
            bot.reply_message(event.reply_token, flex_help())
        
        # أوامر المحتوى البسيط
        elif command in ["سؤال", "تحدي", "اعتراف", "منشن", "موقف"]:
            data = content_manager.get_random(command)
            if data:
                bot.reply_message(event.reply_token, flex_simple(command, data))
        
        # أمر الاقتباسات
        elif command == "اقتباسات":
            quote = content_manager.get_random('اقتباس')
            if quote:
                bot.reply_message(event.reply_token, flex_quote(quote))
        
        # أمر اللغز
        elif command == "لغز":
            riddle = content_manager.get_random('لغز')
            if riddle:
                session_manager.set_riddle(user_id, riddle)
                bot.reply_message(event.reply_token, flex_riddle(riddle))
        
        # طلب تلميح
        elif text_lower in ["لمح", "تلميح"]:
            riddle = session_manager.get_riddle(user_id)
            if riddle:
                hint = riddle.get('hint', 'فكر أكثر... 🤔')
                bot.reply_message(event.reply_token, flex_answer(hint, True))
        
        # طلب الجواب
        elif text_lower in ["جاوب", "الجواب"]:
            riddle = session_manager.get_riddle(user_id)
            if riddle:
                answer = riddle.get('answer', '')
                session_manager.clear_riddle(user_id)
                bot.reply_message(event.reply_token, flex_answer(answer, False))
        
        # أمر التحليل (عرض قائمة الألعاب)
        elif command == "تحليل":
            message = flex_games()
            if message:
                bot.reply_message(event.reply_token, message)
        
        # اختيار لعبة برقم
        elif text.isdigit() and not session_manager.is_in_game(user_id):
            game_index = int(text) - 1
            games = content_manager.data.get('تحليل', [])
            
            if 0 <= game_index < len(games):
                session_manager.start_game(user_id, game_index)
                message = flex_game_q(games[game_index], 0)
                if message:
                    bot.reply_message(event.reply_token, message)
        
        # الإجابة على أسئلة اختبار الشخصية
        elif session_manager.is_in_game(user_id):
            answer = ANSWER_MAP.get(text_lower)
            
            if answer:
                game_data = session_manager.get_game(user_id)
                game_index = game_data['game_index']
                games = content_manager.data.get('تحليل', [])
                
                if game_index < len(games):
                    game = games[game_index]
                    session_manager.add_answer(user_id, answer)
                    
                    next_question_index = game_data['question_index'] + 1
                    total_questions = len(game.get('questions', []))
                    
                    # إذا كان هناك أسئلة متبقية
                    if next_question_index < total_questions:
                        message = flex_game_q(game, next_question_index)
                        if message:
                            bot.reply_message(event.reply_token, message)
                    
                    # إذا انتهت الأسئلة، احسب النتيجة
                    else:
                        all_answers = game_data['answers'] + [answer]
                        result = calc_result(all_answers, game_index)
                        session_manager.end_game(user_id)
                        bot.reply_message(event.reply_token, flex_result(result))
    
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        # يمكن إرسال رسالة خطأ للمستخدم هنا إذا أردت

# ═══════════════════════════════════════════════════════════
# تشغيل التطبيق
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
