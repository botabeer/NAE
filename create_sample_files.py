#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
إنشاء ملفات تجريبية للاختبار
استخدم هذا السكريبت إذا كانت الملفات مفقودة
"""

import json
import os

def create_sample_files():
    """إنشاء جميع الملفات التجريبية"""
    
    print("=" * 60)
    print("إنشاء ملفات تجريبية للبوت")
    print("=" * 60)
    
    # 1. questions.txt
    with open("questions.txt", "w", encoding="utf-8") as f:
        questions = [
            "ما هو أكثر شيء تندم عليه في حياتك؟",
            "إذا كان لديك قوة خارقة واحدة، ماذا ستكون؟",
            "ما هي أسعد لحظة في حياتك؟",
            "من هو الشخص الذي تحترمه أكثر؟",
            "ما هو حلمك الأكبر في الحياة؟"
        ]
        f.write("\n".join(questions))
    print("✅ تم إنشاء questions.txt")
    
    # 2. challenges.txt
    with open("challenges.txt", "w", encoding="utf-8") as f:
        challenges = [
            "اتصل بآخر شخص في قائمة جهات الاتصال",
            "أرسل رسالة لأقدم محادثة في الواتساب",
            "غير صورة بروفايلك لمدة 24 ساعة",
            "انشر ستوري عن أفضل صديق لك",
            "اكتب منشور عن شيء تخجل منه"
        ]
        f.write("\n".join(challenges))
    print("✅ تم إنشاء challenges.txt")
    
    # 3. confessions.txt
    with open("confessions.txt", "w", encoding="utf-8") as f:
        confessions = [
            "اعترف بشيء لم تخبر به أحداً من قبل",
            "ما هو أكبر سر احتفظت به عن والديك؟",
            "هل كذبت على صديقك المقرب؟ لماذا؟",
            "ما هو أكثر شيء تخجل من الاعتراف به؟",
            "اعترف بشيء فعلته وتندم عليه"
        ]
        f.write("\n".join(confessions))
    print("✅ تم إنشاء confessions.txt")
    
    # 4. more_questions.txt
    with open("more_questions.txt", "w", encoding="utf-8") as f:
        more = [
            "أكثر شخص تثق به؟",
            "أكثر مكان تحب زيارته؟",
            "أكثر شيء يسعدك؟",
            "أكثر شيء يزعجك؟",
            "أكثر شخص تفتقده؟"
        ]
        f.write("\n".join(more))
    print("✅ تم إنشاء more_questions.txt")
    
    # 5. emojis.json
    emojis = [
        {
            "question": "🍕🍔🍟",
            "answer": "طعام سريع",
            "hint": "نوع من الأكل",
            "image": ""
        },
        {
            "question": "☀️🌙⭐",
            "answer": "السماء",
            "hint": "أشياء في السماء",
            "image": ""
        }
    ]
    with open("emojis.json", "w", encoding="utf-8") as f:
        json.dump(emojis, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء emojis.json")
    
    # 6. riddles.json
    riddles = [
        {
            "question": "ما هو الشيء الذي له رأس وليس له عينان؟",
            "answer": "الدبوس",
            "hint": "شيء صغير وحاد",
            "image": ""
        },
        {
            "question": "يسير بلا رجلين ويبكي بلا عينين؟",
            "answer": "السحاب",
            "hint": "في السماء",
            "image": ""
        }
    ]
    with open("riddles.json", "w", encoding="utf-8") as f:
        json.dump(riddles, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء riddles.json")
    
    # 7. poems.json
    poems = [
        {
            "poet": "أحمد شوقي",
            "text": "قم للمعلم وفه التبجيلا\nكاد المعلم أن يكون رسولا"
        },
        {
            "poet": "نزار قباني",
            "text": "أحبك جداً\nوأعرف أني سأبقى أحبك"
        }
    ]
    with open("poems.json", "w", encoding="utf-8") as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء poems.json")
    
    # 8. quotes.json
    quotes = [
        {
            "author": "علي بن أبي طالب",
            "text": "الصبر مفتاح الفرج"
        },
        {
            "author": "أينشتاين",
            "text": "الخيال أهم من المعرفة"
        }
    ]
    with open("quotes.json", "w", encoding="utf-8") as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء quotes.json")
    
    # 9. personality_games.json
    games = {
        "لعبة1": {
            "title": "اكتشف شخصيتك",
            "questions": [
                {
                    "question": "كيف تقضي وقت فراغك؟",
                    "options": {
                        "أ": "القراءة",
                        "ب": "الرياضة",
                        "ج": "التسوق"
                    }
                },
                {
                    "question": "ما هو لونك المفضل؟",
                    "options": {
                        "أ": "الأزرق",
                        "ب": "الأحمر",
                        "ج": "الأخضر"
                    }
                }
            ]
        }
    }
    with open("personality_games.json", "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء personality_games.json")
    
    # 10. detailed_results.json
    results = {
        "لعبة1": {
            "أ": "أنت شخص هادئ ومفكر",
            "ب": "أنت شخص نشيط ومغامر",
            "ج": "أنت شخص اجتماعي ومرح"
        }
    }
    with open("detailed_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("✅ تم إنشاء detailed_results.json")
    
    print("\n" + "=" * 60)
    print("✅ تم إنشاء جميع الملفات التجريبية بنجاح!")
    print("=" * 60)
    print("\nالملفات التي تم إنشاؤها:")
    for filename in os.listdir('.'):
        if filename.endswith(('.txt', '.json')) and filename not in ['requirements.txt', 'package.json']:
            size = os.path.getsize(filename)
            print(f"  • {filename:30} ({size} bytes)")
    print("\n⚠️  تذكير: هذه ملفات تجريبية للاختبار فقط")
    print("   استبدلها بالمحتوى الحقيقي قبل النشر النهائي\n")

if __name__ == "__main__":
    create_sample_files()
