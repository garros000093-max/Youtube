# 🔴 إصلاح خطأ youtubeSignupRequired — دليل خطوة بخطوة

## ما هو السبب الحقيقي؟

خطأ `youtubeSignupRequired` لا يتعلق بالكود — التوكن يتجدد بنجاح لكن YouTube يرفض الرفع.
**السبب:** OAuth app في Google Cloud لا يزال في وضع **Testing**.
في هذا الوضع، كل refresh token **ينتهي تلقائياً بعد 7 أيام** حتى لو جددته.

---

## الحل الدائم (10 دقائق)

### الخطوة 1: Publish OAuth App

1. اذهب إلى: https://console.cloud.google.com/
2. اختر مشروعك (نفس المشروع الذي فيه YouTube Data API)
3. من القائمة الجانبية: **APIs & Services → OAuth consent screen**
4. ستجد زر أزرق: **"PUBLISH APP"** أو **"Push to Production"**
5. اضغطه → ستظهر رسالة تأكيد → اضغط **Confirm**

> ⚠️ إذا طلب منك Google "verification"، اضغط **"Submit for verification"** لكن
> الاستخدام الشخصي يعمل مباشرة بدون انتظار verification.

---

### الخطوة 2: احصل على Refresh Token جديد

بعد نشر الـ app، **لا بد** من توليد refresh token جديد:

1. على Railway، شغّل **auth_setup.py** كـ service منفصل مؤقت:
   - اذهب إلى Railway → مشروعك → **New Service → GitHub Repo**
   - أو في نفس الـ service: غيّر `CMD` في Dockerfile مؤقتاً إلى:
     ```
     CMD ["python", "auth_setup.py"]
     ```
2. افتح URL الـ service (من Railway → Settings → Domains)
3. اضغط **"Connect YouTube Channel"**
4. سجّل دخول بنفس حساب Google الذي فيه الـ YouTube channel
5. انسخ الـ **refresh token** الذي يظهر

---

### الخطوة 3: حدّث Railway Variables

في Railway → مشروعك → **Variables**:

```
YOUTUBE_REFRESH_TOKEN = [الـ token الجديد من الخطوة 2]
```

---

### الخطوة 4: أعد Deploy البوت

1. غيّر Dockerfile مرة أخرى إلى: `CMD ["python", "main.py"]`
2. أو اضغط **Redeploy** في Railway

---

## ✅ علامات النجاح في اللوق

```
✅ YouTube authenticated via refresh token
✅ Video uploaded: VIDEO_ID
✅ Thumbnail set
```

---

## إذا استمرت المشكلة بعد هذه الخطوات

**تحقق من هذه الأشياء:**

1. **هل الحساب الذي فعلت auth_setup.py به لديه YouTube Channel؟**
   - اذهب إلى youtube.com → تأكد من وجود channel
   - إذا لم يكن موجوداً، أنشئه أولاً ثم أعد الخطوة 2

2. **هل YOUTUBE_CHANNEL_ID صحيح؟**
   - شغّل `diagnose_auth.py` على Railway
   - سيعطيك الـ Channel ID الصحيح

3. **هل YouTube Data API v3 مفعّل؟**
   - Google Cloud Console → APIs & Services → Enabled APIs
   - ابحث عن **YouTube Data API v3** → تأكد أنه Enabled

---

## ملاحظة مهمة عن الـ Quota

YouTube Data API لديه **quota يومي = 10,000 units**.
- رفع فيديو واحد = ~1,600 units
- هذا يسمح بـ ~6 فيديوهات يومياً كحد أقصى
- البوت حالياً يرفع 1 شورتس + 1 فيديو طويل = ~3,200 units ✅
