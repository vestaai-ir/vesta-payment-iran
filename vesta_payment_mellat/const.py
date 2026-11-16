# Copyright 2026 Vesta AI (https://vestaai.ir)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

# Behpardakht Mellat (bpm.shaparak.ir). Test mode maps these URLs to the sandbox server.
REST_URL = "https://bpm.shaparak.ir/ipg2/rest/"
SOAP_URL = "https://bpm.shaparak.ir/pgwchannel/services/pgw"
SOAP_NAMESPACE = "http://interfaces.core.sw.bps.com/"
PAYMENT_URL = "https://bpm.shaparak.ir/pgwchannel/startpay.mellat"

DEFAULT_PAYMENT_METHOD_CODES = {"mellat"}

# Minutes during which Mellat accepts bpVerifyRequest after the payment.
VERIFY_WINDOW_MINUTES = 15

# Result codes that mean the request already went through (safe to treat as success on retry).
ALREADY_VERIFIED = "43"
ALREADY_SETTLED = "45"

# Result codes of Behpardakht Mellat: {code: (English, Persian)}.
RESULT_CODES = {
    "0": ("Transaction approved", "تراکنش با موفقیت انجام شد"),
    "11": ("Invalid card number", "شماره کارت نامعتبر است"),
    "12": ("Insufficient funds", "موجودی کافی نیست"),
    "13": ("Incorrect PIN", "رمز نادرست است"),
    "14": ("Too many wrong PIN attempts", "تعداد دفعات وارد کردن رمز بیش از حد مجاز است"),
    "15": ("Invalid card", "کارت نامعتبر است"),
    "16": ("Too many withdrawals", "دفعات برداشت وجه بیش از حد مجاز است"),
    "17": ("Canceled by the customer", "کاربر از انجام تراکنش منصرف شده است"),
    "18": ("Card expired", "تاریخ انقضای کارت گذشته است"),
    "19": ("Withdrawal amount over the limit", "مبلغ برداشت وجه بیش از حد مجاز است"),
    "111": ("Invalid card issuer", "صادر کننده کارت نامعتبر است"),
    "112": ("Card issuer switch error", "خطای سوییچ صادر کننده کارت"),
    "113": ("No response from the card issuer", "پاسخی از صادر کننده کارت دریافت نشد"),
    "114": ("Cardholder not allowed to do this transaction", "دارنده کارت مجاز به انجام این تراکنش نیست"),
    "21": ("Invalid merchant", "پذیرنده نامعتبر است"),
    "23": ("Security error", "خطای امنیتی رخ داده است"),
    "24": ("Invalid merchant credentials", "اطلاعات کاربری پذیرنده نامعتبر است"),
    "25": ("Invalid amount", "مبلغ نامعتبر است"),
    "31": ("Invalid response", "پاسخ نامعتبر است"),
    "32": ("Invalid data format", "فرمت اطلاعات وارد شده صحیح نمی باشد"),
    "33": ("Invalid account", "حساب نامعتبر است"),
    "34": ("System error", "خطای سیستمی"),
    "35": ("Invalid date", "تاریخ نامعتبر است"),
    "41": ("Duplicate order id", "شماره درخواست تکراری است"),
    "42": ("Sale transaction not found", "تراکنش Sale یافت نشد"),
    "43": ("Already verified", "قبلا درخواست Verify داده شده است"),
    "44": ("Verify request not found", "درخواست Verify یافت نشد"),
    "45": ("Already settled", "تراکنش قبلا Settle شده است"),
    "46": ("Transaction not settled", "تراکنش Settle نشده است"),
    "47": ("Settle transaction not found", "تراکنش Settle یافت نشد"),
    "48": ("Transaction reversed", "تراکنش Reverse شده است"),
    "49": ("Refund transaction not found", "تراکنش Refund یافت نشد"),
    "412": ("Invalid bill id", "شناسه قبض نادرست است"),
    "413": ("Invalid payment id", "شناسه پرداخت نادرست است"),
    "414": ("Invalid bill issuer", "سازمان صادر کننده قبض نامعتبر است"),
    "415": ("Session expired", "زمان جلسه کاری به پایان رسیده است"),
    "416": ("Error while saving data", "خطا در ثبت اطلاعات"),
    "417": ("Invalid payer id", "شناسه پرداخت کننده نامعتبر است"),
    "418": ("Error in customer data", "اشکال در تعریف اطلاعات مشتری"),
    "419": ("Too many data entry attempts", "تعداد دفعات ورود اطلاعات از حد مجاز گذشته است"),
    "421": ("Invalid server IP address", "IP نامعتبر است"),
    "51": ("Duplicate transaction", "تراکنش تکراری است"),
    "54": ("Reference transaction not found", "تراکنش مرجع موجود نیست"),
    "55": ("Invalid transaction", "تراکنش نامعتبر است"),
    "61": ("Deposit error", "خطا در واریز"),
    "62": (
        "Return URL is not on the merchant's domain",
        "مسیر بازگشت به سایت در دامنه ثبت شده برای پذیرنده قرار ندارد",
    ),
    "98": ("Static password limit reached", "سقف استفاده از رمز ایستا به پایان رسیده است"),
}
