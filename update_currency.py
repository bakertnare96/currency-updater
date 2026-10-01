#!/usr/bin/env python3
"""
يجلب أسعار الصرف (دولار / يورو / ليرة تركية) وأسعار الذهب (أونصة / عيار 21 / عيار 18)
من موقع sp-today.com ويرسلها لموقعك عبر update_currency.php — مصمم ليعمل داخل
GitHub Actions (أو أي مكان يدعم بايثون ويسمح بالاتصال الخارجي).

المتغيرات المطلوبة (Environment Variables):
  SITE_URL   -> مثال: https://yourdomain.com/update_currency.php
  TOKEN      -> المفتاح السري الظاهر في لوحة التحكم -> أسعار العملات

المتغير الاختياري:
  CURRENCIES -> قائمة "code=url" مفصولة بفاصلة، لتحديث أكثر من عملة/معدن بنفس التشغيلة.
                مثال (يحدّث كل شي دفعة وحدة):
                usd=https://sp-today.com/en/currency/us-dollar,eur=https://sp-today.com/en/currency/euro,try=https://sp-today.com/en/currency/turkish-lira,gold_ounce=https://sp-today.com/gold/ounce,gold21=https://sp-today.com/gold/21k/usd,gold18=https://sp-today.com/gold/18k/usd
                إن لم يُحدد، يتم تحديث الدولار فقط بالرابط الافتراضي.
"""
import os
import re
import sys
import urllib.request
import urllib.parse

DEFAULT_URLS = {
    "usd": "https://sp-today.com/en/currency/us-dollar",
    "eur": "https://sp-today.com/en/currency/euro",
    "try": "https://sp-today.com/en/currency/turkish-lira",
    "gold_ounce": "https://sp-today.com/gold/ounce",
    "gold21": "https://sp-today.com/gold/21k/usd",
    "gold18": "https://sp-today.com/gold/18k/usd",
}

GOLD_CODES = {"gold_ounce", "gold21", "gold18"}

SITE_URL = os.environ.get("SITE_URL")
TOKEN = os.environ.get("TOKEN")
CURRENCIES_ENV = os.environ.get("CURRENCIES", "").strip()


def parse_currencies_env(raw: str):
    pairs = {}
    if not raw:
        return {"usd": DEFAULT_URLS["usd"]}
    for item in raw.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        code, url = item.split("=", 1)
        pairs[code.strip().lower()] = url.strip()
    return pairs or {"usd": DEFAULT_URLS["usd"]}


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def clean_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text)


def parse_buy_sell(html: str):
    """لصفحات العملات: تُرجع (buy, sell) أو None إذا لم يُعثر على النمط."""
    text = clean_text(html)

    m = re.search(
        r"is\s+([\d,]+(?:\.\d+)?)\s+new SYP.*?for buying and\s+([\d,]+(?:\.\d+)?)\s+new SYP.*?for selling",
        text, re.I | re.S,
    )
    if not m:
        m = re.search(
            r"Buy\s*([\d,]+(?:\.\d+)?)\s*SYP.*?Sell\s*([\d,]+(?:\.\d+)?)\s*SYP",
            text, re.I | re.S,
        )
    if not m:
        return None

    return m.group(1).replace(",", ""), m.group(2).replace(",", "")


def parse_single_price(html: str):
    """لصفحات الذهب: سعر واحد فقط. نجرب عدة أنماط شائعة، وإن فشلت نأخذ أول رقم كبير معقول كاحتياط."""
    text = clean_text(html)

    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:new\s+)?SYP", text, re.I)
    if m:
        return m.group(1).replace(",", "")

    m = re.search(r"price[^\d]{0,15}([\d,]{4,}(?:\.\d+)?)", text, re.I)
    if m:
        return m.group(1).replace(",", "")

    # احتياطي أخير: أول رقم بأربع خانات فأكثر (سعر بالليرة السورية عادة كبير)
    m = re.search(r"([\d,]{4,}(?:\.\d+)?)", text)
    if m:
        return m.group(1).replace(",", "")

    return None


def push_to_site(code: str, buy, sell):
    payload = {"token": TOKEN, "code": code, "sell": sell}
    if buy:
        payload["buy"] = buy
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(SITE_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main():
    if not SITE_URL or not TOKEN:
        print("ERROR: SITE_URL and TOKEN environment variables are required", file=sys.stderr)
        sys.exit(1)

    currencies = parse_currencies_env(CURRENCIES_ENV)
    had_error = False

    for code, url in currencies.items():
        try:
            html = fetch_html(url)
            is_gold = code in GOLD_CODES

            if is_gold:
                price = parse_single_price(html)
                if not price:
                    print(f"ERROR: could not parse gold price for '{code}' from {url}", file=sys.stderr)
                    had_error = True
                    continue
                print(f"[{code}] parsed -> price: {price}")
                result = push_to_site(code, None, price)
            else:
                rate = parse_buy_sell(html)
                if not rate:
                    print(f"ERROR: could not parse rate for '{code}' from {url}", file=sys.stderr)
                    had_error = True
                    continue
                buy, sell = rate
                print(f"[{code}] parsed -> buy: {buy}  sell: {sell}")
                result = push_to_site(code, buy, sell)

            print(f"[{code}] site response:", result)
        except Exception as e:
            print(f"ERROR updating '{code}': {e}", file=sys.stderr)
            had_error = True

    if had_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
