<div dir="rtl">

# نحوه‌ی اتصال به درگاه بانک‌ها

این سند جزئیات فنی اتصال درگاه وستا به هر بانک را نگه می‌دارد: آدرس سرویس‌ها روی سرور اصلی و آزمایشی، احراز هویت، پارامترها، ترتیب فراخوانی‌ها، کدهای پاسخ و نکته‌هایی که فقط با آزمایش روی سندباکس پیدا شدند.
همه‌ی جریان‌ها روی سندباکس [banktest.ir](https://banktest.ir) آزمایش شده‌اند (پرداخت موفق، انصراف مشتری، خطای تأیید، خطای تسویه، قطع ارتباط، دوبار مصرف رسید، مغایرت مبلغ و استرداد).

> **امنیت:** چرایی تصمیم‌ها در [SECURITY.md](SECURITY.md) آمده است. **راه‌اندازی:** [ACTIVATION.md](ACTIVATION.md).

---

## ۱. معماری

```
vesta_payment               ← هسته و اپ «درگاه وستا» (متن‌باز)
├── داشبورد بانک‌ها، روشن/خاموش، آزمایش اتصال، گزارش پرداخت‌ها
├── مسیر بازگشت مشترک  /payment/vesta/<bank>/return/<order_id>/<hmac>
├── قفل، تطبیق توکن، ثبت رسید یکتا، تلاش دوباره (cron)، تبدیل ریال/تومان
└── ابزار SOAP امن، نگاشت سرور اصلی ← سندباکس، پنهان‌سازی رمز در لاگ
vesta_payment_mellat        ← بانک ملت (متن‌باز)
vesta_payment_saman         ← بانک سامان        ┐
vesta_payment_sadad         ← بانک ملی (سداد)   │ درگاه وستا حرفه‌ای
vesta_payment_pasargad      ← بانک پاسارگاد     │ (فایل زیپ)
vesta_payment_parsian       ← بانک پارسیان      ┘
```

هر ماژول بانک فقط پنج متد را پیاده می‌کند و بقیه‌ی کار با هسته است:

| متد | کار | شبکه |
|---|---|---|
| `_vesta_request_payment()` | گرفتن توکن از بانک و ساختن فرم انتقال | بله |
| `_vesta_parse_callback(data)` | خواندن فرم بازگشت و تطبیق آن با تراکنش | خیر |
| `_vesta_verify(callback)` | تأیید (و تسویه) سرور به سرور، بررسی مبلغ | بله |
| `_vesta_reverse()` | برگشت وجه (مغایرت مبلغ و استرداد) | بله |
| `_vesta_test_connection()` | آزمایش رمزها و IP بدون جابه‌جایی پول | بله |

### چرخه‌ی وضعیت

| `vesta_verify_state` | معنی | وضعیت تراکنش اودو |
|---|---|---|
| `new` | توکن صادر شده، مشتری در صفحه‌ی بانک است | پیش‌نویس |
| `pending` | بانک پاسخ تأیید را نداد؛ کران دوباره تلاش می‌کند | در انتظار |
| `verified` | بانک پرداخت را تأیید کرد | انجام‌شده |
| `settled` | تأیید و تسویه شد (ملت، پاسارگاد) | انجام‌شده |
| `reversed` | وجه به کارت مشتری برگشت | خطا / استرداد |
| `failed` | ناموفق، لغو یا رهاشده | لغو / خطا |

### حالت آزمایشی

در حالت آزمایشی، آدرس سرور اصلی بانک خودکار به آدرس سندباکس نگاشت می‌شود:

```
https://<host>/<path>   →   <سرور آزمایشی>/<پیشوند بانک>/<host>/<path>
https://bpm.shaparak.ir/pgwchannel/startpay.mellat
   → https://sandbox.banktest.ir/mellat/bpm.shaparak.ir/pgwchannel/startpay.mellat
```

| بانک | پیشوند سندباکس |
|---|---|
| ملت | `mellat` |
| سامان | `saman` |
| ملی (سداد) | `melli` |
| پاسارگاد | `pasargad` |
| پارسیان | `parsian` |

سرور آزمایشی در فرم هر بانک (بخش «سرور بانک») قابل تغییر است و فقط HTTPS پذیرفته می‌شود.

### مبلغ و ارز

بانک‌ها همیشه **ریال** می‌گیرند. تراکنش‌های ریال (`IRR`) مستقیم و تراکنش‌های تومان (`IRT`، ارز سفارشی رایج در اودوی ایرانی) با ضریب ۱۰ فرستاده می‌شوند. کسر ریال حذف می‌شود، دقیقاً مثل بررسی مبلغ خود اودو.

### شماره سفارش

شماره سفارش بانکی عددی ۱۸ رقمی است: زمان به میلی‌ثانیه + سه رقم آخر شناسه‌ی تراکنش + دو رقم تصادفی. حتی اگر پایگاه‌داده‌ی تست و اصلی یک ترمینال مشترک داشته باشند، شماره تکراری نمی‌شود. شماره‌ی تراکنش اودو (مثلاً `S00042-1`) در فیلد توضیحات بانک (AdditionalData، ResNum1، description) فرستاده می‌شود تا در پنل بانک قابل جست‌وجو باشد.

---

## ۲. بانک ملت (به‌پرداخت ملت)

| | سرور اصلی | سندباکس |
|---|---|---|
| REST | `https://bpm.shaparak.ir/ipg2/rest/<operation>` | `https://sandbox.banktest.ir/mellat/bpm.shaparak.ir/ipg2/rest/<operation>` |
| SOAP (WSDL) | `https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl` | `https://sandbox.banktest.ir/mellat/bpm.shaparak.ir/pgwchannel/services/pgw?wsdl` |
| صفحه‌ی پرداخت | `https://bpm.shaparak.ir/pgwchannel/startpay.mellat` | `https://sandbox.banktest.ir/mellat/bpm.shaparak.ir/pgwchannel/startpay.mellat` |

**اطلاعات لازم:** شناسه ترمینال (Terminal ID)، نام کاربری، رمز عبور. **وب‌سرویس:** REST (پیشنهادی) یا SOAP؛ قابل انتخاب در فرم.

**جریان:**
1. `bpPayRequest(terminalId, userName, userPassword, orderId, amount, localDate=yyyyMMdd, localTime=HHmmss, additionalData, callBackUrl, payerId=0)` ← پاسخ `0,<RefId>` یا کد خطا.
2. فرم POST به `startpay.mellat` با `RefId` و در صورت وجود موبایل مشتری `mobileNo=98912…` (نمایش کارت‌های ذخیره‌شده).
3. بازگشت (POST): `RefId, ResCode, SaleOrderId, SaleReferenceId, CardHolderPan, CardHolderInfo, FinalAmount`. موفق یعنی `ResCode = 0`.
4. `bpVerifyRequest(…, orderId, saleOrderId, saleReferenceId)` ← `0` یا `43` (قبلاً تأیید شده).
5. `bpSettleRequest(…)` ← `0` یا `45` (قبلاً تسویه شده). در خطا: `bpReversalRequest`.

**نکته‌های کشف‌شده در سندباکس:**
- سرویس REST برای `bpPayRequest` رمز را از **HTTP Basic Auth** می‌خواند (فقط بدنه ← خطای ۳۴) ولی برای Verify و Settle از **بدنه** (فقط Basic ← خطای ۲۴). درگاه وستا هر دو را می‌فرستد و هر دو عملیات موفق است.
- پاسخ REST متن ساده است (`0,AF82041A…`)، نه JSON.
- SOAP از نوع rpc است: پارامترها بدون namespace، نتیجه در `<return>`.
- `CardHolderPan` پوشیده و `CardHolderInfo` هش کارت است.

**کدهای مهم:** ۰ موفق · ۱۷ انصراف · ۲۱ پذیرنده نامعتبر · ۲۴ رمز نادرست · ۳۴ خطای سیستمی · ۴۱ شماره سفارش تکراری · ۴۲ خرید پیدا نشد · ۴۳ قبلاً Verify شده · ۴۵ قبلاً Settle شده · ۴۸ برگشت خورده · ۴۱۵ پایان نشست · ۴۲۱ IP نامعتبر · ۶۲ آدرس بازگشت خارج از دامنه. فهرست کامل در `vesta_payment_mellat/const.py`.

**مهلت تأیید:** ۱۵ دقیقه (تلاش دوباره‌ی کران تا همین زمان).

---

## ۳. بانک سامان (پرداخت الکترونیک سامان)

| | سرور اصلی | سندباکس |
|---|---|---|
| دریافت توکن و صفحه‌ی پرداخت | `https://sep.shaparak.ir/OnlinePG/OnlinePG` | `https://sandbox.banktest.ir/saman/sep.shaparak.ir/OnlinePG/OnlinePG` |
| Verify | `https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction` | `https://sandbox.banktest.ir/saman/sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction` |
| Reverse | `https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/ReverseTransaction` | `https://sandbox.banktest.ir/saman/sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/ReverseTransaction` |

مستند مرجع: «راهنمای استفاده از درگاه پرداخت اینترنتی، نگارش ۳.۳، اسفند ۱۴۰۲».

**اطلاعات لازم:** شناسه ترمینال (MID). احراز هویت فقط با **IP سرور** است.

**جریان:**
1. POST JSON: `{"action":"token","TerminalId","Amount","ResNum","RedirectUrl","CellNumber","ResNum1","TokenExpiryInMin":20}` ← `{"status":1,"token":…}` یا `{"status":-1,"errorCode","errorDesc"}`.
2. فرم POST به `OnlinePG` با `Token`.
3. بازگشت (POST): `MID, State, Status, RRN, RefNum, ResNum, TerminalId, TraceNo, Amount, Wage, SecurePan, HashedCardNumber, Token`. موفق یعنی `State = OK` و `Status = 2`.
4. POST JSON `{"RefNum","TerminalNumber"}` به VerifyTransaction ← `{"ResultCode":0,"Success":true,"TransactionDetail":{RRN, RefNum, MaskedPan, HashedPan, TerminalNumber, OrginalAmount, AffectiveAmount, StraceDate, StraceNo}}`.
5. بررسی `TerminalNumber` و `OrginalAmount`؛ در مغایرت: ReverseTransaction.

**نکته‌ها:**
- پاسخ Verify **شماره سفارش (ResNum) را ندارد**؛ پس یکتایی رسید (RefNum) وظیفه‌ی پذیرنده است (بخش «Double Spending» مستند سامان).
- Verify درخواست تکراری را هم موفق جواب می‌دهد (`ResultCode` صفر یا ۲).
- برای RefNum ناموجود، سندباکس به‌جای JSON یک صفحه‌ی HTML «Request Rejected» می‌دهد؛ درگاه وستا آن را خطای قابل تلاش دوباره حساب می‌کند.
- **مهلت‌ها:** Verify تا ۳۰ دقیقه، Reverse تا ۵۰ دقیقه. استرداد از دکمه‌ی «Refund» اودو با Reverse انجام می‌شود.

**کدهای وضعیت بازگشت:** ۱ انصراف · ۲ موفق · ۳ ناموفق · ۴ پایان زمان · ۵ پارامتر نامعتبر · ۸ IP نامعتبر · ۱۰ توکن پیدا نشد · ۱۱ فقط پرداخت توکنی · ۱۲ ترمینال پیدا نشد · ۲۱ قوانین چندحسابی.
**کدهای Verify/Reverse:** ۰ موفق · ۲ تکراری · ۵ برگشت خورده · ۲- پیدا نشد · ۶- بیش از ۳۰ دقیقه · ۱۸- / ۱۰۶- IP نامعتبر · ۱۰۴- ترمینال غیرفعال · ۱۰۵- ترمینال ناموجود.

---

## ۴. بانک ملی (سداد)

| | سرور اصلی | سندباکس |
|---|---|---|
| PaymentRequest | `https://sadad.shaparak.ir/VPG/api/v0/Request/PaymentRequest` | `https://sandbox.banktest.ir/melli/sadad.shaparak.ir/VPG/api/v0/Request/PaymentRequest` |
| Verify | `https://sadad.shaparak.ir/VPG/api/v0/Advice/Verify` | `https://sandbox.banktest.ir/melli/sadad.shaparak.ir/VPG/api/v0/Advice/Verify` |
| صفحه‌ی پرداخت | `https://sadad.shaparak.ir/VPG/Purchase?Token=…` | `https://sandbox.banktest.ir/melli/sadad.shaparak.ir/VPG/Purchase?Token=…` |

مستند مرجع: «مستندات درگاه پرداخت الکترونیک سداد، ویرایش ۱/۲، اسفند ۱۳۹۵».

**اطلاعات لازم:** شناسه پذیرنده (Merchant ID)، شناسه ترمینال (Terminal ID)، کلید تراکنش (Terminal Key، Base64).

**امضا:** `SignData = Base64(TripleDES-ECB-PKCS7(key = Base64Decode(TerminalKey), text))`
- درخواست: `text = "TerminalId;OrderId;Amount"`
- تأیید: `text = Token`

**جریان:**
1. POST JSON `{MerchantId, TerminalId, Amount, OrderId, LocalDateTime="MM/dd/yyyy hh:mm:ss AM", ReturnUrl, SignData, UserId}` ← `{ResCode:0, Token, Description}`.
2. انتقال GET به `Purchase?Token=…`.
3. بازگشت (POST): `OrderId, token, ResCode` (موفق یعنی ResCode صفر).
4. POST JSON `{Token, SignData}` به Verify ← `{ResCode:0, Amount, RetrivalRefNo, SystemTraceNo, OrderId}`؛ هر دو `OrderId` و `Amount` بررسی می‌شوند. `ResCode = 100` یعنی قبلاً تأیید شده.

**نکته‌ها:**
- `LocalDateTime` باید به وقت تهران و نزدیک ساعت بانک باشد (خطای ۱۰۱۸).
- سندباکس فیلد آزاد `AdditionalData` را با خطای ۱۰۳۶ رد می‌کند؛ درگاه وستا آن را نمی‌فرستد.
- `cryptography` نسخه‌ی ۴۳ به بعد TripleDES را به `decrepit` برده است؛ هر دو مسیر پشتیبانی می‌شود.
- سداد در این نسخه‌ی API سرویس برگشت ندارد؛ استرداد از پنل بانک انجام می‌شود.

**کدهای مهم:** ۰ موفق · ۱- پارامتر نادرست یا تراکنش ناموجود · ۱۰۰ تکراری (قبلاً تأیید شده) · ۱۰۱ پایان مهلت · ۱۰۰۳ IP نادرست · ۱۰۱۱ سفارش تکراری · ۱۰۱۲ اطلاعات پذیرنده/کلید/زمان نادرست · ۱۰۱۸ ساعت نادرست · ۱۰۲۳ آدرس بازگشت نامعتبر · ۱۰۲۵ امضای نامعتبر · ۱۰۵۶ / ۱۰۶۵ / ۱۰۶۶ / ۱۰۶۸ قطعی موقت.

---

## ۵. بانک پاسارگاد (پرداخت الکترونیک پاسارگاد، سوییچ پرسا)

| سرویس | سرور اصلی (`https://pep.shaparak.ir/dorsa1` +) | سندباکس (`https://sandbox.banktest.ir/pasargad/pep.shaparak.ir/dorsa1` +) |
|---|---|---|
| دریافت توکن | `/token/getToken` | `/token/getToken` |
| خرید | `/api/payment/purchase` | `/api/payment/purchase` |
| تأیید (Verify) | `/api/payment/verify-payment` | `/api/payment/verify-payment` |
| تأیید نهایی (Confirm) | `/api/payment/confirm-transactions` | `/api/payment/confirm-transactions` |
| برگشت (Reverse) | `/api/payment/reverse-transactions` | `/api/payment/reverse-transactions` |
| استعلام | `/api/payment/payment-inquiry` | `/api/payment/payment-inquiry` |

مستند مرجع: «درگاه پرداخت اینترنتی سوییچ پرسا، نسخه ۱۳، بهمن ۱۴۰۳».

**اطلاعات لازم:** شماره ترمینال، نام کاربری، رمز عبور.

**جریان:**
1. `getToken {username, password}` ← JWT (نگه‌داری تا یک دقیقه پیش از انقضا).
2. `purchase` با `Authorization: Bearer` و `{amount, callbackApi, description, invoice, invoiceDate, mobileNumber, payerMail, payerName, serviceCode:"8", serviceType:"PURCHASE", terminalNumber}` ← `{resultCode:0, data:{urlId, url}}`.
3. انتقال GET به `data.url` (فقط اگر روی دامنه‌ی بانک باشد).
4. بازگشت (**GET**): `invoiceId, status, referenceNumber, trackId`. موفق یعنی `status = success`.
5. `verify-payment {invoice, urlId}` ← `data{invoice, referenceNumber, trackId, maskedCardNumber, hashedCardNumber, amount}`؛ فاکتور و مبلغ بررسی می‌شوند.
6. `confirm-transactions {invoice, urlId}` ← `0` یا `13029` (قبلاً تأیید شده). در خطا: `reverse-transactions`.

**نکته‌های کشف‌شده در سندباکس:**
- **کمترین مبلغ ۱۰٬۰۰۱ ریال** است؛ ۱۰٬۰۰۰ ریال با کد ۱۳۰۵۵ رد می‌شود.
- `resultCode` گاهی عدد و گاهی رشته است؛ همیشه رشته مقایسه می‌شود.
- بازگشت با فرم GET است؛ مرورگر query string آدرس بازگشت را حذف می‌کند. برای همین شماره سفارش و امضا در **مسیر** آدرس هستند، نه query string.
- `referenceNumber` فرم بازگشت با `referenceNumber` پاسخ تأیید یکی نیست؛ رسید از پاسخ تأیید خوانده می‌شود.

**کدهای مهم:** ۰ موفق · ۴۰۱ مجاز نیستید (رمز/IP) · ۵۰۰ خطای سرور · ۱۳۰۰۵ قطعی موقت · ۱۳۰۱۶ پیدا نشد · ۱۳۰۲۱ لغو شده · ۱۳۰۲۲ پرداخت نشده · ۱۳۰۲۵ ناموفق · ۱۳۰۲۹ قبلاً تأیید و موفق · ۱۳۰۳۰ تأیید و ناموفق · ۱۳۰۳۳ برگشت انجام شد · ۱۳۰۵۵ مبلغ نامعتبر.

---

## ۶. بانک پارسیان (تجارت الکترونیک پارسیان)

| | سرور اصلی | سندباکس |
|---|---|---|
| خرید (WSDL) | `https://pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx?wsdl` | `https://sandbox.banktest.ir/parsian/pec.shaparak.ir/NewIPGServices/Sale/SaleService.asmx?wsdl` |
| تأیید (WSDL) | `https://pec.shaparak.ir/NewIPGServices/Confirm/ConfirmService.asmx?wsdl` | `…/parsian/pec.shaparak.ir/NewIPGServices/Confirm/ConfirmService.asmx?wsdl` |
| برگشت (WSDL) | `https://pec.shaparak.ir/NewIPGServices/Reverse/ReversalService.asmx?wsdl` | `…/parsian/pec.shaparak.ir/NewIPGServices/Reverse/ReversalService.asmx?wsdl` |
| صفحه‌ی پرداخت | `https://pec.shaparak.ir/NewIPG/?Token=…` | `https://sandbox.banktest.ir/parsian/pec.shaparak.ir/NewIPG/?Token=…` |

**اطلاعات لازم:** پین (LoginAccount). احراز هویت با پین و **IP سرور**.

**جریان (SOAP، document/literal، پارامترها داخل `requestData`):**
1. `SalePaymentRequest {LoginAccount, Amount, OrderId, CallBackUrl, AdditionalData, Originator}` ← `{Token, Message, Status}`؛ موفق یعنی `Status = 0` و `Token > 0`.
2. انتقال GET به `NewIPG/?Token=…`.
3. بازگشت (POST): `Token, OrderId, TerminalNo, RRN, status, Amount, HashCardNumber, STraceNo`؛ موفق یعنی `status = 0` و `RRN > 0`.
4. `ConfirmPaymentWithAmount {LoginAccount, Token, OrderId, Amount}` ← `{Status, RRN, CardNumberMasked, Token}`؛ موفق یعنی `0` یا `1533-` (قبلاً تأیید شده). این سرویس فقط اگر مبلغ و سفارش با درخواست اولیه یکی باشد تأیید می‌کند.
5. استرداد: `ReversalRequest {LoginAccount, Token}`.

**نکته‌ها:**
- `SOAPAction` برابر `<namespace>/<operation>` است؛ namespace سرویس برگشت `…/Reversal/ReversalService` است در حالی که آدرسش `…/Reverse/…` است.
- مبلغ در فرم بازگشت با جداکننده‌ی هزارگان می‌آید (`25,000`).
- پاسخ‌ها SOAP 1.2 هستند حتی وقتی درخواست SOAP 1.1 باشد؛ پارسر هر دو را می‌پذیرد.

**کدهای مهم:** ۰ موفق · ۱۳۸- انصراف مشتری · ۱۳۰- توکن منقضی · ۱۳۱- توکن نامعتبر · ۱۲۶- پین نامعتبر · ۱۲۷- IP نامعتبر · ۱۱۲- سفارش تکراری · ۱۵۲۸- پرداخت پیدا نشد · ۱۵۳۳- قبلاً تأیید شده · ۱۵۴۰- تأیید ناموفق · ۱۵۴۹- پایان مهلت برگشت · ۱۵۵۱- قبلاً برگشت خورده.

---

## ۷. خلاصه‌ی مقایسه

| | ملت | سامان | ملی (سداد) | پاسارگاد | پارسیان |
|---|---|---|---|---|---|
| پروتکل | REST + SOAP | REST | REST | REST (JWT) | SOAP |
| احراز هویت | نام کاربری/رمز + IP | فقط IP | امضای 3DES + IP | JWT + IP | پین + IP |
| روش بازگشت | POST | POST | POST | GET | POST |
| مبلغ در پاسخ تأیید | — (گره به RefId) | ✔ | ✔ | ✔ | — (تأیید با مبلغ) |
| مرحله‌ی دوم | Settle | — | — | Confirm | — |
| استرداد از اودو | — | ✔ (Reverse، ۵۰ دقیقه) | — | ✔ | ✔ |
| مهلت تأیید | ۱۵ دقیقه | ۳۰ دقیقه | ۱۵ دقیقه | ۱۵ دقیقه | ۱۵ دقیقه |
| آزمایش اتصال | توکن بی‌استفاده | توکن بی‌استفاده | توکن بی‌استفاده | فقط ورود | توکن بی‌استفاده |

</div>
