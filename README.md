# 🤖 YouTube Automation Bot — Setup Guide

## الخطوة 1: تجهيز المفاتيح (30 دقيقة)

### OpenAI API Key
1. اذهب إلى: https://platform.openai.com/api-keys
2. Create new secret key → انسخه

### ElevenLabs API Key
1. اذهب إلى: https://elevenlabs.io → Sign up (مجاني)
2. Profile → API Key → انسخه

### YouTube Data API + OAuth
1. اذهب إلى: https://console.cloud.google.com
2. Create Project → اسمه "YTBot"
3. APIs & Services → Enable → YouTube Data API v3
4. Credentials → Create OAuth 2.0 Client ID → Desktop App
5. حمّل الملف JSON → سمّه `client_secrets.json` وضعه في المجلد
6. Credentials → Create API Key → انسخه (لـ YOUTUBE_API_KEY)

### Pexels API Key
1. اذهب إلى: https://www.pexels.com/api
2. Your API key → انسخه

---

## الخطوة 2: تشغيل لأول مرة (محلياً)

```bash
# نسخ المتغيرات
cp .env.example .env
# أضف مفاتيحك في .env

# تثبيت المكتبات
pip install -r requirements.txt

# أول تشغيل (سيفتح نافذة OAuth للربط بيوتيوب)
python main.py
```

عند ظهور نافذة الـ OAuth → اختر حسابك → اضغط Allow
يُحفظ التوكن في `token.pickle` وتشغيل مرة واحدة فقط.

---

## الخطوة 3: النشر على Railway

```bash
# سجّل دخول Railway
railway login

# إنشاء مشروع جديد
railway init

# رفع المتغيرات
railway variables set OPENAI_API_KEY=sk-...
railway variables set ELEVENLABS_API_KEY=...
railway variables set YOUTUBE_API_KEY=AIza...
railway variables set PEXELS_API_KEY=...

# رفع ملف token.pickle (مهم!)
railway up

# نشر
railway deploy
```

---

## الجدول الزمني

| الوقت (UTC) | الحدث | الوقت EST |
|------------|-------|-----------|
| 14:00 | YouTube Short | 9:00 AM |
| 20:00 | فيديو طويل (كل يومين) | 3:00 PM |

---

## التكاليف الشهرية المتوقعة

| الخدمة | التكلفة |
|--------|---------|
| OpenAI GPT-4o | ~$8 |
| ElevenLabs | مجاني (10k حرف) |
| Railway | $5 |
| Pexels | مجاني |
| **المجموع** | **~$13/شهر** |

---

## هيكل الملفات

```
youtube_bot/
├── main.py              # المشغل الرئيسي + الجدول الزمني
├── trend_finder.py      # البحث عن التريند الأمريكي
├── script_generator.py  # كتابة السكريبت + توليد الصوت
├── video_producer.py    # تجميع الفيديو + الصورة المصغرة
├── uploader.py          # الرفع على يوتيوب
├── requirements.txt
├── railway.toml
├── client_secrets.json  # ← تحمّله أنت من Google Console
└── token.pickle         # ← يُنشأ تلقائياً عند أول تشغيل
```
