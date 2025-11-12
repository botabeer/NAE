#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة فحص الملفات المطلوبة للبوت
تستخدم قبل النشر للتأكد من وجود جميع الملفات
"""

import os
import json
from typing import List, Dict

# الألوان للطباعة
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text: str):
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")

def check_file(filename: str, file_type: str = "txt") -> Dict:
    """فحص ملف واحد"""
    result = {
        "exists": False,
        "size": 0,
        "lines": 0,
        "status": "❌"
    }
    
    if os.path.exists(filename):
        result["exists"] = True
        result["size"] = os.path.getsize(filename)
        
        try:
            if file_type == "txt":
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                    result["lines"] = len(lines)
            elif file_type == "json":
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        result["lines"] = len(data)
                    elif isinstance(data, dict):
                        result["lines"] = len(data.keys())
            
            result["status"] = "✅" if result["lines"] > 0 else "⚠️"
        except Exception as e:
            result["status"] = f"❌ خطأ: {str(e)[:30]}"
    
    return result

def main():
    print_header("فحص ملفات البوت")
    
    # الملفات المطلوبة
    required_files = {
        "ملفات نصية (TXT)": [
            "questions.txt",
            "challenges.txt",
            "confessions.txt",
            "more_questions.txt"
        ],
        "ملفات JSON": [
            "emojis.json",
            "riddles.json",
            "poems.json",
            "quotes.json",
            "personality_games.json",
            "detailed_results.json"
        ],
        "ملفات Python": [
            "app.py",
            "requirements.txt"
        ]
    }
    
    all_ok = True
    
    for category, files in required_files.items():
        print(f"{YELLOW}{category}:{RESET}")
        print("-" * 60)
        
        for filename in files:
            file_type = filename.split('.')[-1]
            result = check_file(filename, file_type)
            
            status = result["status"]
            size_kb = result["size"] / 1024
            
            if result["exists"]:
                if result["lines"] > 0:
                    print(f"{status} {filename:30} | {result['lines']:>4} عنصر | {size_kb:>6.1f} KB")
                else:
                    print(f"⚠️  {filename:30} | فارغ | {size_kb:>6.1f} KB")
                    all_ok = False
            else:
                print(f"❌ {filename:30} | غير موجود")
                all_ok = False
        
        print()
    
    # التحقق من المتغيرات البيئية
    print_header("المتغيرات البيئية")
    
    env_vars = {
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
        "PORT": os.getenv("PORT", "5000")
    }
    
    for var, value in env_vars.items():
        if value:
            masked = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {var:30} = {masked}")
        else:
            print(f"❌ {var:30} = غير محدد")
            if var != "PORT":
                all_ok = False
    
    # النتيجة النهائية
    print_header("النتيجة")
    
    if all_ok:
        print(f"{GREEN}✅ جميع الملفات جاهزة! يمكنك نشر البوت الآن{RESET}")
        return 0
    else:
        print(f"{RED}❌ يوجد ملفات مفقودة أو فارغة. يرجى إصلاحها قبل النشر{RESET}")
        print(f"\n{YELLOW}نصائح:{RESET}")
        print("  • تأكد من رفع جميع الملفات إلى Git")
        print("  • تحقق من ترميز الملفات (UTF-8)")
        print("  • تأكد من صحة ملفات JSON")
        return 1

if __name__ == "__main__":
    exit(main())
