#!/usr/bin/env python3
"""
يجلب سعر صرف الدولار من موقع sp-today.com ويرسله لموقعك عبر update_currency.php
مصمم ليعمل داخل GitHub Actions (أو أي مكان يدعم بايثون ويسمح بالاتصال الخارجي).

المتغيرات المطلوبة (Environment Variables):
  SITE_URL -> مثال: https://yourdomain.com/update_currency.php
  TOKEN    -> المفتاح السري الظاهر في لوحة التحكم -> أسعار العملات
"""
import os
import re
import sys
import urllib.request
import urllib.parse

SOURCE_URL = os.environ.get("SOURCE_URL", "https://sp-today.com/en/currency/us-dollar")
SITE_URL = os.environ.get("SITE_URL")
TOKEN = os.environ.get("TOKEN")


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def parse_rate(html: str):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

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

    buy = m.group(1).replace(",", "")
    sell = m.group(2).replace(",", "")
    return buy, sell


def push_to_site(buy: str, sell: str):
    data = urllib.parse.urlencode({"token": TOKEN, "buy": buy, "sell": sell}).encode()
    req = urllib.request.Request(SITE_URL, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main():
    if not SITE_URL or not TOKEN:
        print("ERROR: SITE_URL and TOKEN environment variables are required", file=sys.stderr)
        sys.exit(1)

    html = fetch_html(SOURCE_URL)
    rate = parse_rate(html)
    if not rate:
        print("ERROR: could not parse the exchange rate from the source page", file=sys.stderr)
        sys.exit(1)

    buy, sell = rate
    print(f"Parsed rate -> buy: {buy}  sell: {sell}")

    result = push_to_site(buy, sell)
    print("Site response:", result)


if __name__ == "__main__":
    main()
