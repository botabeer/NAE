#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
أداة فحص وإصلاح الاستيرادات
تتحقق من أن الكود لا يحتوي على SpacerComponent أو مكونات غير متوافقة
"""

import re
import sys

def check_imports():
    """فحص استيرادات app.py"""
    print("=" * 60)
    print("🔍 فحص استيرادات app.py")
    print("=" * 60)
    
    try:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # البحث عن SpacerComponent
        spacer_imports = re.findall(r'from linebot\.models import.*SpacerComponent', content, re.DOTALL)
        spacer_usage = re.findall(r'SpacerComponent\s*\(', content)
        
        issues = []
        
        if spacer_imports:
            issues.append("❌ SpacerComponent موجود في الاستيراد")
            print("❌ وُجد SpacerComponent في سطر الاستيراد")
            for match in spacer_imports[:3]:
                print(f"   {match[:80]}...")
        else:
            print("✅ لا يوجد SpacerComponent في الاستيراد")
        
        if spacer_usage:
            issues.append(f"❌ SpacerComponent مستخدم في الكود ({len(spacer_usage)} مرة)")
            print(f"❌ وُجد SpacerComponent في الكود ({len(spacer_usage)} مرة)")
            for i, match in enumerate(spacer_usage[:5], 1):
                print(f"   {i}. {match}")
        else:
            print("✅ لا يوجد استخدام لـ SpacerComponent في الكود")
        
        # البحث عن create_spacer (البديل)
        spacer_func = re.search(r'def create_spacer\(', content)
        spacer_func_usage = re.findall(r'create_spacer\s*\(', content)
        
        if spacer_func:
            print(f"✅ دالة create_spacer موجودة")
        else:
            issues.append("⚠️  دالة create_spacer غير موجودة")
            print("⚠️  دالة create_spacer غير موجودة")
        
        if spacer_func_usage:
            print(f"✅ create_spacer مستخدمة في الكود ({len(spacer_func_usage)} مرة)")
        else:
            print("⚠️  create_spacer غير مستخدمة")
        
        # فحص المكونات الأخرى
        print("\n" + "=" * 60)
        print("🔍 فحص المكونات الأخرى")
        print("=" * 60)
        
        components_check = {
            'FlexSendMessage': True,
            'BubbleContainer': True,
            'BoxComponent': True,
            'TextComponent': True,
            'SeparatorComponent': True,
            'FillerComponent': False,  # غير مستخدم
            'SpacerComponent': False,  # غير متوافق
        }
        
        for component, should_exist in components_check.items():
            pattern = f'from linebot\\.models import.*{component}'
            found = re.search(pattern, content, re.DOTALL)
            
            if should_exist:
                if found:
                    print(f"✅ {component} - موجود")
                else:
                    print(f"❌ {component} - مفقود (مطلوب)")
                    issues.append(f"❌ {component} مفقود")
            else:
                if found:
                    print(f"⚠️  {component} - موجود (غير ضروري)")
                    issues.append(f"⚠️  {component} موجود بدون داعي")
                else:
                    print(f"✅ {component} - غير موجود (صحيح)")
        
        # النتيجة
        print("\n" + "=" * 60)
        print("📊 النتيجة")
        print("=" * 60)
        
        if not issues:
            print("✅ جميع الاستيرادات صحيحة!")
            print("\n💡 يمكنك الآن تشغيل البوت:")
            print("   python app.py")
            return 0
        else:
            print(f"⚠️  وُجد {len(issues)} مشكلة:")
            for issue in issues:
                print(f"   • {issue}")
            print("\n💡 راجع الكود وأصلح المشاكل")
            return 1
        
    except FileNotFoundError:
        print("❌ ملف app.py غير موجود!")
        return 1
    except Exception as e:
        print(f"❌ خطأ: {e}")
        return 1

def test_import():
    """اختبار استيراد المكتبة"""
    print("\n" + "=" * 60)
    print("🧪 اختبار استيراد line-bot-sdk")
    print("=" * 60)
    
    try:
        from linebot import LineBotApi, WebhookHandler
        print("✅ تم استيراد LineBotApi و WebhookHandler")
    except Exception as e:
        print(f"❌ خطأ في استيراد line-bot-sdk: {e}")
        return False
    
    try:
        from linebot.models import (
            MessageEvent, TextMessage, TextSendMessage,
            FlexSendMessage, BubbleContainer, BoxComponent, TextComponent
        )
        print("✅ تم استيراد جميع المكونات الأساسية")
    except Exception as e:
        print(f"❌ خطأ في استيراد المكونات: {e}")
        return False
    
    # محاولة استيراد SpacerComponent
    try:
        from linebot.models import SpacerComponent
        print("⚠️  SpacerComponent متاح في هذا الإصدار")
        print("   لكن من الأفضل عدم استخدامه للتوافق")
    except ImportError:
        print("✅ SpacerComponent غير متاح (صحيح)")
    
    return True

def check_line_sdk_version():
    """فحص إصدار line-bot-sdk"""
    print("\n" + "=" * 60)
    print("📦 فحص إصدار line-bot-sdk")
    print("=" * 60)
    
    try:
        import linebot
        version = getattr(linebot, '__version__', 'غير معروف')
        print(f"✅ الإصدار المثبت: {version}")
        
        # قراءة requirements.txt
        try:
            with open('requirements.txt', 'r') as f:
                for line in f:
                    if 'line-bot-sdk' in line.lower():
                        print(f"📄 في requirements.txt: {line.strip()}")
        except:
            pass
        
        print("\n💡 الإصدارات الموصى بها:")
        print("   • line-bot-sdk>=3.0.0  (أحدث، بدون SpacerComponent)")
        print("   • line-bot-sdk==2.4.2  (قديم، مع SpacerComponent)")
        
    except ImportError:
        print("❌ line-bot-sdk غير مثبت!")
        print("\n💡 لتثبيته:")
        print("   pip install line-bot-sdk>=3.0.0")

def main():
    """الدالة الرئيسية"""
    print("\n" + "🔧 " * 20)
    print("أداة فحص وإصلاح الاستيرادات".center(60))
    print("🔧 " * 20 + "\n")
    
    # 1. فحص الاستيرادات في الكود
    result = check_imports()
    
    # 2. اختبار الاستيراد الفعلي
    test_import()
    
    # 3. فحص الإصدار
    check_line_sdk_version()
    
    # النتيجة النهائية
    print("\n" + "=" * 60)
    if result == 0:
        print("✅ الكود جاهز للتشغيل!")
        print("=" * 60)
        print("\n🚀 الخطوات التالية:")
        print("   1. python app.py              - تشغيل محلي")
        print("   2. gunicorn app:app           - تشغيل production")
        print("   3. git push origin main       - النشر على Render")
    else:
        print("⚠️  يوجد مشاكل تحتاج إلى إصلاح")
        print("=" * 60)
        print("\n🔧 خطوات الإصلاح:")
        print("   1. راجع الأخطاء أعلاه")
        print("   2. أصلح app.py")
        print("   3. أعد تشغيل هذا السكريبت")
    
    return result

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  تم إيقاف الفحص")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ خطأ غير متوقع: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
