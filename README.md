<p align="center">
  <img src="vesta_payment/static/description/banner.png" alt="Vesta Gateway · درگاه وستا برای اودو ۲۰" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Odoo-20.0-714B67?style=for-the-badge" alt="Odoo 20.0">
  <img src="https://img.shields.io/badge/license-LGPL--3-5b3cc4?style=for-the-badge" alt="LGPL-3">
  <img src="https://img.shields.io/badge/tests-63%20passing-2ea44f?style=for-the-badge" alt="63 tests passing">
  <img src="https://img.shields.io/badge/Shaparak-Mellat%20·%20Saman%20·%20Melli%20·%20Pasargad%20·%20Parsian-e8392e?style=for-the-badge" alt="Banks">
</p>

<p align="center">
  <a href="#fa">فارسی</a> · <a href="#en">English</a> ·
  <a href="docs/ACTIVATION.md">راهنمای فعال‌سازی</a> ·
  <a href="docs/SECURITY.md">امنیت</a> ·
  <a href="docs/INTEGRATION.md">نحوه‌ی اتصال</a>
</p>

---

<div dir="rtl" id="fa">

## درگاه وستا؛ پرداخت بانک‌های ایرانی در اودو ۲۰

**درگاه وستا** کامل‌ترین ماژول بومی‌سازی پرداخت اینترنتی برای اودو ۲۰ است: درگاه بانک‌های **ملت، سامان، ملی (سداد)، پاسارگاد و پارسیان** با یک هسته‌ی مشترک امن، یک داشبورد برای نصب، آزمایش، روشن و خاموش کردن و پایش همه‌ی بانک‌ها، و حالت آزمایشی آماده روی سندباکس banktest.ir.

مشتری در فروشگاه اینترنتی، پورتال، لینک پرداخت فاکتور یا سفارش فروش، بانک دلخواهش را انتخاب می‌کند، در صفحه‌ی امن بانک پرداخت می‌کند و برمی‌گردد. درگاه وستا پرداخت را **سرور به سرور با بانک تأیید می‌کند**، مبلغ را با سفارش تطبیق می‌دهد، رسید بانک را فقط به یک سفارش وصل می‌کند و اگر چیزی درست نبود، **پول را خودکار به کارت مشتری برمی‌گرداند**.

> ⭐ اگر به کارتان آمد، به این مخزن ستاره بدهید تا بقیه هم پیدایش کنند.

### ⇄ مسیریابی هوشمند تراکنش؛ چند بانک، یک صندوق

بیشتر فروشگاه‌ها چند ترمینال بانکی دارند ولی همه‌ی پرداخت‌ها را به یکی می‌فرستند؛ تا سقف روزانه‌اش پر شود، بانک قطع شود یا پول در یک حساب انباشته شود. **درگاه وستا تصمیم را خودکار می‌گیرد**: برای هر پرداخت، طبق قانونی که شما در **مرکز کنترل** تعیین می‌کنید، بانک مناسب را انتخاب می‌کند.

| حالت | چه می‌کند | مناسب برای |
|---|---|---|
| 👤 **انتخاب مشتری** | همه‌ی بانک‌های فعال به ترتیب دلخواه شما نمایش داده می‌شوند | فروشگاه با مشتری‌هایی که بانک خاصی دارند |
| ⚖️ **توزیع وزنی** | سهم هر بانک را می‌دهید (مثلاً ملت ۴۰، سامان ۳۰، ملی ۱۵، پاسارگاد ۱۰، پارسیان ۵)؛ هر پرداخت به بانکی می‌رود که بیشترین فاصله را با سهمش دارد، پس توزیع **در هر لحظه از روز** با وزن‌ها هماهنگ است | پخش گردش مالی بین حساب‌ها، توافق کارمزد با چند بانک |
| 🔄 **چرخشی** | بانک‌ها به نوبت پرداخت می‌گیرند و هر بانک **چند پرداخت پیاپی** (نوبت) دارد: مثلاً ۳ ملت، ۲ سامان، ۱ ملی… | تقسیم مساوی و قابل پیش‌بینی |
| 🥇 **اولویت با جایگزین** | همه‌ی پرداخت‌ها به بانک اول می‌روند؛ وقتی متوقف شد یا به سقف رسید، بانک بعدی | یک بانک اصلی و چند بانک پشتیبان |

- 🛑 **سقف روزانه برای هر ترمینال** (تعداد یا مبلغ ریالی)؛ وقتی پر شد، پرداخت‌ها خودکار به بانک‌های دیگر می‌روند.
- 🩺 **سلامت بانک**: بانکی که ۳ بار پیاپی توکن صادر نکند، ۱۰ دقیقه از مسیریابی کنار گذاشته می‌شود و بعد خودکار برمی‌گردد. خطاهای ناشی از مبلغ سفارش حساب نمی‌شوند، پس کسی نمی‌تواند با سفارش‌های کوچک بانکی را از کار بیندازد.
- 🔮 **پیش‌نمایش ۲۴ پرداخت بعدی**: در مرکز کنترل می‌بینید پرداخت‌های بعدی به کدام بانک‌ها می‌روند.
- 🧭 **بانک انتخاب‌شده اول** در صفحه‌ی پرداخت نمایش داده می‌شود؛ می‌توانید بانک‌های دیگر را هم زیر آن نشان دهید یا فقط همان یکی را.
- 📊 **توزیع واقعی در برابر هدف**: سهم امروز هر بانک کنار سهم هدفش، نمودار دایره‌ای توزیع و نمودار ساعتی/روزانه.

<p align="center"><img src="vesta_payment/static/description/screenshots/control_center.jpg" alt="مرکز کنترل درگاه وستا" width="100%"></p>
<p align="center"><img src="vesta_payment/static/description/screenshots/control_center_banks.jpg" alt="تنظیم وزن، نوبت و سقف هر بانک" width="100%"></p>

### این مخزن و نسخه‌ی حرفه‌ای

| ماژول | بانک | سرویس | این مخزن (متن‌باز) | درگاه وستا حرفه‌ای (زیپ) |
|---|---|---|:---:|:---:|
| `vesta_payment` | اپ «درگاه وستا» و هسته‌ی مشترک | — | ✅ | ✅ |
| `vesta_payment_mellat` | **بانک ملت** (به‌پرداخت) | REST + SOAP | ✅ | ✅ |
| `vesta_payment_saman` | **بانک سامان** (سپ) | REST · OnlinePG 3.3 | | ✅ |
| `vesta_payment_sadad` | **بانک ملی** (سداد) | REST · VPG v0 | | ✅ |
| `vesta_payment_pasargad` | **بانک پاسارگاد** (پپ، سوییچ پرسا) | REST · نسخه ۱۳ | | ✅ |
| `vesta_payment_parsian` | **بانک پارسیان** (پک) | SOAP · NewIPG | | ✅ |

### امکانات

**پرداخت**
- 🏦 پنج بانک اصلی شاپرک، هر کدام با جدیدترین سرویس رسمی‌اش؛ ملت با **REST یا SOAP** به انتخاب شما
- 🔁 جریان کامل هر بانک: درخواست توکن ← پرداخت ← بازگشت ← تأیید ← تسویه/تأیید نهایی ← برگشت
- 💸 **استرداد از داخل اودو** برای سامان، پاسارگاد و پارسیان (دکمه‌ی Refund)
- 📱 ارسال موبایل مشتری به بانک برای نمایش کارت‌های ذخیره‌شده
- 💱 ریال (`IRR`) و تومان (`IRT`) با تبدیل خودکار به ریال
- 🛒 کار در فروشگاه اینترنتی، پورتال مشتری، لینک پرداخت فاکتور و سفارش فروش؛ وابستگی فقط به `payment`

**امنیت** ([جزئیات](docs/SECURITY.md))
- ✅ تأیید **سرور به سرور** هر پرداخت؛ فرم بازگشت هیچ‌وقت به‌تنهایی پذیرفته نمی‌شود
- 🔐 آدرس بازگشت امضاشده با **HMAC**، تطبیق زمان‌ثابت توکن بانک
- 🧾 جلوگیری از **دوبار مصرف رسید** با ایندکس یکتای پایگاه‌داده
- ⚖️ تطبیق مبلغ و **برگشت خودکار وجه** در مغایرت؛ برگشت خودکار وقتی تسویه/تأیید نهایی ناموفق است
- 🔒 قفل تراکنش در برابر بازگشت هم‌زمان و دوبار کلیک
- ♻️ **تلاش دوباره‌ی خودکار** تأیید در قطعی بانک، تا پایان مهلت هر بانک
- 🛡️ پارسر SOAP ایمن در برابر XXE، پنهان شدن رمزها در لاگ، پاک شدن رمزها در کپی تستی پایگاه‌داده

**مدیریت**
- 🛰️ **مرکز کنترل**: شاخص‌های امروز / ۷ روز / ۳۰ روز (تعداد، نرخ موفقیت، مبلغ دریافتی، در انتظار بانک)، حالت مسیریابی، پیش‌نمایش جریان پرداخت، نمودار توزیع، و کنترل کامل هر بانک در یک صفحه
- ↕️ **ترتیب بانک‌ها** با دکمه‌های بالا/پایین؛ همان ترتیب صفحه‌ی پرداخت و اولویت مسیریابی
- 🎛️ **کارت بانک‌ها**: وضعیت (عملیاتی، آزمایشی، غیرفعال)، آمار ۳۰ روز، هشدار تنظیمات ناقص
- 🔌 دکمه‌ی **آزمایش اتصال** بدون جابه‌جایی پول: رمز، IP سرور و دسترسی بانک را بررسی می‌کند
- 🟢 **فعال‌سازی عملیاتی / حالت آزمایشی / غیرفعال** با یک کلیک، با سرور آزمایشی قابل تغییر
- 📋 گزارش **پرداخت‌های بانکی** با رسید دیجیتال، RRN، شماره پیگیری، کارت پوشیده و وضعیت تأیید بانک
- 🇮🇷 ترجمه‌ی کامل فارسی، پیام خطای فارسی هر کد بانک

### تصویرها

<p align="center"><img src="vesta_payment/static/description/screenshots/dashboard.jpg" alt="داشبورد درگاه وستا" width="100%"></p>

| انتخاب بانک در صفحه‌ی پرداخت | پرداخت‌های بانکی |
|---|---|
| <img src="vesta_payment/static/description/screenshots/checkout_fa.jpg" alt="صفحه‌ی پرداخت"> | <img src="vesta_payment/static/description/screenshots/payments.jpg" alt="پرداخت‌های بانکی"> |
| **صفحه‌ی پرداخت آزمایشی ملت** | **پیکربندی بانک** |
| <img src="vesta_payment/static/description/screenshots/sandbox_mellat.jpg" alt="سندباکس ملت"> | <img src="vesta_payment/static/description/screenshots/provider_form.jpg" alt="پیکربندی بانک"> |

### چطور کار می‌کند

```mermaid
flowchart LR
    R["مسیریابی هوشمند<br/>وزنی · چرخشی · اولویت"] --> A["بانک انتخاب‌شده<br/>اول نمایش داده می‌شود"]
    A --> B["اودو از بانک توکن می‌گیرد<br/>(سرور به سرور)"]
    B --> C["پرداخت روی<br/>سایت امن بانک"]
    C --> D["بازگشت به آدرس<br/>امضاشده‌ی اودو"]
    D --> E{"تأیید سرور به سرور<br/>+ تطبیق مبلغ و رسید"}
    E -- درست --> F["سفارش تأیید شد<br/>رسید ثبت شد"]
    E -- مغایرت --> G["برگشت خودکار<br/>وجه به کارت"]
    E -- قطعی بانک --> H["تلاش دوباره<br/>هر ۵ دقیقه"]
```

### شروع سریع

```bash
cd /opt/odoo/custom-addons
git clone -b 20.0 https://github.com/vestaai-ir/vesta-payment-iran.git
```

1. مسیر `vesta-payment-iran` را به `addons_path` اضافه کنید و اودو را راه‌اندازی مجدد کنید.
2. **برنامه‌ها ← به‌روزرسانی فهرست** و نصب **Vesta Gateway**.
3. **درگاه وستا ← بانک‌ها ← نصب** روی بانک ملت.
4. **پیکربندی**: شناسه ترمینال، نام کاربری و رمز را وارد کنید ← **حالت آزمایشی** ← **آزمایش اتصال**.
5. بعد از خرید آزمایشی موفق، اطلاعات اصلی را وارد کنید و **فعال‌سازی عملیاتی** را بزنید.

راهنمای کامل همه‌ی بانک‌ها، روی سرور اصلی و آزمایشی، با جدول رفع اشکال: **[docs/ACTIVATION.md](docs/ACTIVATION.md)**

### مستندات

| سند | محتوا |
|---|---|
| [ACTIVATION.md](docs/ACTIVATION.md) | نصب، حالت آزمایشی، فعال‌سازی عملیاتی، روشن/خاموش کردن، کار روزانه، رفع اشکال |
| [SECURITY.md](docs/SECURITY.md) | مدل تهدید با ۲۲ مورد، کنترل‌ها و محل آن‌ها در کد، نکته‌های هر بانک، چک‌لیست راه‌اندازی امن |
| [INTEGRATION.md](docs/INTEGRATION.md) | آدرس سرویس‌ها، پارامترها، ترتیب فراخوانی و کدهای پاسخ هر بانک، نکته‌های کشف‌شده در سندباکس |

### آزمایش‌شده

- **۶۳ تست خودکار** (بدون نیاز به اینترنت): مسیریابی وزنی، چرخشی و اولویت، سقف روزانه، توقف خودکار بانک، تأیید، تسویه، برگشت، دوبار مصرف رسید، مغایرت مبلغ، توکن جعلی، امضای آدرس، تلاش دوباره، XXE، تبدیل تومان
  ```bash
  odoo -d test_db -i vesta_payment_mellat --test-tags=/vesta_payment,/vesta_payment_mellat --stop-after-init
  ```
- **آزمون سرتاسری روی سندباکس banktest.ir** برای هر پنج بانک: پرداخت موفق، انصراف مشتری، خطای تأیید، خطای تسویه با برگشت خودکار، تایم‌اوت ۶۵ ثانیه‌ای و تلاش دوباره، دوبار مصرف رسید، مغایرت مبلغ و استرداد.

### سازگاری

اودو ۲۰ (Community و Enterprise)، پایتون ۳.۱۲ به بالا. بدون وابستگی خارجی: `requests`، `lxml` و `cryptography` همراه اودو نصب می‌شوند.

### مجوز

هسته و بانک ملت: [LGPL-3](LICENSE). درگاه وستا حرفه‌ای (سامان، ملی، پاسارگاد، پارسیان) جداگانه به صورت فایل زیپ ارائه می‌شود.
ساخته‌ی [هوش مصنوعی وستا](https://vestaai.ir). نشان‌های بانک‌ها متعلق به خود بانک‌هاست و فقط برای معرفی درگاه آن‌ها استفاده شده است.

</div>

---

<div id="en">

<p align="center"><img src="vesta_payment/static/description/banner_en.png" alt="Vesta Gateway" width="100%"></p>

## Vesta Gateway: Iranian bank payments for Odoo 20

**Vesta Gateway** brings the payment gateways of **Bank Mellat, Bank Saman, Bank Melli (Sadad), Bank Pasargad and Bank Parsian** to Odoo 20, on one secure core, with one dashboard to install, test, enable, disable and monitor every bank, and a ready-made test mode on the banktest.ir sandbox.

Customers pick their bank on the website, customer portal, invoice payment link or sales order, pay on the bank's secure page and come back. Vesta Gateway **confirms each payment server-to-server**, checks the amount against the order, binds each bank receipt to a single order and **reverses the money automatically** when anything is off.

### This repository and Pro

This repository holds the core app (`vesta_payment`) and **Bank Mellat** (`vesta_payment_mellat`, REST and SOAP). Saman, Melli (Sadad), Pasargad and Parsian are part of **Vesta Gateway Pro**, shipped as a zip; the dashboard lists them with a "Get Pro" button until their modules are in the addons path.

### Highlights

- **Smart routing between banks**: customer choice, weighted distribution (the bank furthest below its share takes the next payment, so shares match the weights at any time of day), rotation in batches, or priority with failover; daily count and amount caps per terminal; automatic pause of a failing bank; a preview of the next 24 routing decisions
- **Control center**: today / 7 / 30-day KPIs, routing mode, distribution donut and hourly/daily chart, and per-bank weight, batch, caps, order, live/test/off and connection test on one page

- Server-to-server verification of every payment; the browser's return form is never trusted alone
- HMAC-signed return URLs, constant-time token checks, transaction locking against double processing
- Double-spending protection: a database unique index binds each bank receipt to one transaction
- Amount check with automatic reversal; reversal when settlement/confirmation fails (Mellat, Pasargad)
- Automatic retries of the bank confirmation by cron until each bank's window closes
- Refunds from Odoo for Saman, Pasargad and Parsian
- Rial (IRR) and Toman (IRT); bank-time (Asia/Tehran) handling; TripleDES signing for Sadad; JWT caching for Pasargad
- XXE-safe SOAP, credentials masked in logs, restricted to Settings users, wiped on database neutralization
- Dashboard with live/test/disabled toggles, connection test, 30-day statistics; full Persian translation
- 63 automated tests and end-to-end runs of every bank on the sandbox

### Documentation

[Activation guide](docs/ACTIVATION.md) · [Security](docs/SECURITY.md) · [Integration details](docs/INTEGRATION.md) (Persian).

### License

Core and Bank Mellat: [LGPL-3](LICENSE). Made by [Vesta AI](https://vestaai.ir). Bank logos belong to their banks and are only used to identify their gateways.

</div>
