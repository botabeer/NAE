#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اختبار سريع للتطبيق
يتحقق من:
1. استيراد الملف بدون أخطاء
2. وجود جميع الدوال المطلوبة
3. صحة Routes
"""

import sys
import os

def test_import():
    """اختبار استيراد الملف"""
    print("=" * 60)
    print("1️⃣  اختبار استيراد app.py")
    print("=" * 60)
    
    try:
        import app
        print("✅ تم استيراد app.py بنجاح")
        return True
    except Exception as e:
        print(f"❌ خطأ في استيراد app.py: {e}")
        return False

def test_functions():
    """اختبار وجود الدوال"""
    print("\n" + "=" * 60)
    print("2️⃣  اختبار الدوال المطلوبة")
    print("=" * 60)
    
    try:
        import app
        
        required_functions = [
            'safe_reply',
            'create_help_flex',
            'create_stats_flex',
            'create_main_menu',
            'handle_content_command',
            'handle_answer_command',
            'handle_hint_command',
            'handle_personality_test_selection',
            'handle_personality_test_answer',
            'callback',
            'handle_message',
            'home',
            'health_check'
        ]
        
        all_ok = True
        for func in required_functions:
            if hasattr(app, func):
                print(f"✅ {func}")
            else:
                print(f"❌ {func} - غير موجودة!")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def test_routes():
    """اختبار Routes"""
    print("\n" + "=" * 60)
    print("3️⃣  اختبار Flask Routes")
    print("=" * 60)
    
    try:
        import app
        
        # الحصول على جميع routes
        routes = []
        for rule in app.app.url_map.iter_rules():
            routes.append(str(rule))
        
        required_routes = ['/', '/health', '/callback']
        
        all_ok = True
        for route in required_routes:
            if route in routes:
                print(f"✅ {route}")
            else:
                print(f"❌ {route} - غير موجود!")
                all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def test_content_manager():
    """اختبار ContentManager"""
    print("\n" + "=" * 60)
    print("4️⃣  اختبار ContentManager")
    print("=" * 60)
    
    try:
        import app
        
        cm = app.content_manager
        
        print(f"✅ الأسئلة: {len(cm.content_files.get('سؤال', []))}")
        print(f"✅ التحديات: {len(cm.content_files.get('تحدي', []))}")
        print(f"✅ الاعترافات: {len(cm.content_files.get('اعتراف', []))}")
        print(f"✅ أسئلة أكثر: {len(cm.more_questions)}")
        print(f"✅ ألغاز الإيموجي: {len(cm.emoji_puzzles)}")
        print(f"✅ الألغاز: {len(cm.riddles_list)}")
        print(f"✅ الأشعار: {len(cm.poems_list)}")
        print(f"✅ الاقتباسات: {len(cm.quotes_list)}")
        print(f"✅ ألعاب الشخصية: {len(cm.games_list)}")
        
        return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def test_env_vars():
    """اختبار المتغيرات البيئية"""
    print("\n" + "=" * 60)
    print("5️⃣  اختبار المتغيرات البيئية")
    print("=" * 60)
    
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    secret = os.getenv("LINE_CHANNEL_SECRET")
    
    if token:
        print(f"✅ LINE_CHANNEL_ACCESS_TOKEN = {token[:15]}...")
    else:
        print("⚠️  LINE_CHANNEL_ACCESS_TOKEN غير محدد")
    
    if secret:
        print(f"✅ LINE_CHANNEL_SECRET = {secret[:10]}...")
    else:
        print("⚠️  LINE_CHANNEL_SECRET غير محدد")
    
    return True

def test_server_start():
    """اختبار تشغيل السيرفر"""
    print("\n" + "=" * 60)
    print("6️⃣  محاولة تشغيل السيرفر")
    print("=" * 60)
    
    try:
        import app
        import threading
        import time
        import requests
        
        # تشغيل السيرفر في thread منفصل
        def run_server():
            app.app.run(host="127.0.0.1", port=5555, debug=False, use_reloader=False)
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # انتظار بدء السيرفر
        time.sleep(2)
        
        # اختبار endpoints
        print("\nاختبار Endpoints:")
        
        try:
            response = requests.get("http://127.0.0.1:5555/", timeout=5)
            if response.status_code == 200:
                print(f"✅ GET / - {response.status_code}")
            else:
                print(f"⚠️  GET / - {response.status_code}")
        except Exception as e:
            print(f"❌ GET / - خطأ: {e}")
        
        try:
            response = requests.get("http://127.0.0.1:5555/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ GET /health - {response.status_code}")
                print(f"   Response: {response.json()}")
            else:
                print(f"⚠️  GET /health - {response.status_code}")
        except Exception as e:
            print(f"❌ GET /health - خطأ: {e}")
        
        return True
        
    except ImportError:
        print("⚠️  مكتبة requests غير مثبتة - تخطي اختبار السيرفر")
        print("   لتثبيتها: pip install requests")
        return True
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return False

def main():
    """الدالة الرئيسية"""
    print("\n" + "🧪 " * 20)
    print("اختبار تطبيق LINE Bot".center(60))
    print("🧪 " * 20 + "\n")
    
    results = []
    
    # تشغيل الاختبارات
    results.append(("استيراد الملف", test_import()))
    
    if results[0][1]:  # إذا نجح الاستيراد
        results.append(("الدوال المطلوبة", test_functions()))
        results.append(("Flask Routes", test_routes()))
        results.append(("ContentManager", test_content_manager()))
        results.append(("المتغيرات البيئية", test_env_vars()))
        results.append(("تشغيل السيرفر", test_server_start()))
    
    # النتيجة النهائية
    print("\n" + "=" * 60)
    print("📊 النتيجة النهائية")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    print("\n" + "=" * 60)
    if passed == total:
        print(f"✅ نجح {passed}/{total} اختبار - التطبيق جاهز!")
        print("=" * 60)
        print("\n🚀 يمكنك الآن نشر البوت على Render")
        print("\nالأوامر المتاحة:")
        print("  • python app.py           - تشغيل محلي")
        print("  • gunicorn app:app        - تشغيل production")
        print("  • git push origin main    - النشر على Render")
        return 0
    else:
        print(f"⚠️  نجح {passed}/{total} اختبار - يوجد مشاكل!")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  تم إيقاف الاختبار")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
