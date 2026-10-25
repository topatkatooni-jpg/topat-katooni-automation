
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

SITE = "https://topatkatooni.ir"
SITEMAP = SITE + "/product-sitemap.xml"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "TopatKatooniAutomation/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


class PageData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.jsonld = []
        self.in_jsonld = False
        self.jsonld_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)

        if tag.lower() == "meta":
            key = attrs.get("property") or attrs.get("name")
            value = attrs.get("content")
            if key and value:
                self.meta[key.lower()] = value.strip()

        if tag.lower() == "script" and \
                attrs.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self.jsonld_text = ""

    def handle_data(self, data):
        if self.in_jsonld:
            self.jsonld_text += data

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_jsonld:
            try:
                self.jsonld.append(json.loads(self.jsonld_text))
            except Exception:
                pass
            self.in_jsonld = False
            self.jsonld_text = ""


def find_product(obj):
    if isinstance(obj, list):
        for item in obj:
            result = find_product(item)
            if result:
                return result

    if isinstance(obj, dict):
        if obj.get("@type") in ("Product", ["Product"]):
            return obj

        graph = obj.get("@graph")
        if graph:
            result = find_product(graph)
            if result:
                return result

    return None


def get_product(url):
    try:
        html = fetch(url)
        page = PageData()
        page.feed(html)

        title = (
            page.meta.get("og:title")
            or page.meta.get("twitter:title")
            or ""
        )

        description = (
            page.meta.get("og:description")
            or page.meta.get("description")
            or ""
        )

        product = None
        for data in page.jsonld:
            product = find_product(data)
            if product:
                break

        price = ""
        currency = ""

        if product:
            title = title or product.get("name", "")
            description = description or product.get("description", "")

            offers = product.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            if isinstance(offers, dict):
                price = str(offers.get("price", ""))
                currency = str(offers.get("priceCurrency", ""))

        title = re.sub(r"\s+", " ", title).strip()
        description = re.sub(r"\s+", " ", description).strip()

        if not title:
            return None

        return {
            "name": title[:180],
            "description": description[:500],
            "price": price,
            "currency": currency,
            "url": url,
        }

    except Exception as error:
        print("Product read failed:", url, str(error)[:200])
        return None


def main():
    api_key = os.environ.get("GROQ_API_KEY")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not api_key or not bot_token or not chat_id:
        raise SystemExit(
            "Missing GROQ_API_KEY, TELEGRAM_BOT_TOKEN, or TELEGRAM_CHAT_ID."
        )

    sitemap_xml = fetch(SITEMAP)
    root = ET.fromstring(sitemap_xml)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls = [
        item.text.strip()
        for item in root.findall(".//sm:loc", ns)
        if item.text and "/product/" in item.text
    ]

    if not urls:
        urls = [
            item.text.strip()
            for item in root.findall(".//sm:loc", ns)
            if item.text and item.text.strip().startswith(SITE)
        ]

    products = []
    seen = set()

    for url in urls[:15]:
        if url in seen:
            continue
        seen.add(url)

        product = get_product(url)
        if product:
            products.append(product)

        if len(products) >= 3:
            break

    if not products:
        raise SystemExit("No usable products found in the product sitemap.")

    product_text = json.dumps(products, ensure_ascii=False, indent=2)

    prompt = (
        "برای فروشگاه فارسی کتونی توپات کتونی یک رشته‌توییت "
        "شامل 3 تا 5 توییت کوتاه و جذاب بنویس. ترکیب محتوا: "
        "آموزش انتخاب سایز و قالب، معرفی طبیعی محصول واقعی و دعوت "
        "محترمانه به بررسی یا خرید. از اطلاعات محصولات زیر استفاده کن. "
        "هیچ قیمت، ویژگی، موجودی، سایز یا ادعایی را که در داده‌ها نیست "
        "اضافه نکن. اگر قیمت نامشخص است، قیمت ننویس. "
        "خروجی فارسی باشد و هر توییت با شماره جدا شود. "
        "لینک محصول را فقط وقتی مرتبط است از URL واقعی داده‌ها بیاور.\n\n"
        "اطلاعات محصولات:\n" + product_text
    )

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "تو نویسنده حرفه‌ای فارسی برای فروشگاه کتونی هستی. "
                    "اطلاعات محصول را جعل نکن و متن را طبیعی و مفید بنویس."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "max_completion_tokens": 700,
        "temperature": 0.5
    }

    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TopatKatooniAutomation/1.0"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print("Groq API error:", error.code)
        print(error.read().decode("utf-8", errors="replace")[:1500])
        raise SystemExit(1)

    content = result["choices"][0]["message"]["content"].strip()

    message = (
        "📝 پیش‌نویس رشته‌توییت توپات کتونی\n"
        "وضعیت: منتظر بررسی شما؛ هنوز منتشر نشده.\n\n"
        + content
    )

    telegram_url = (
        "https://api.telegram.org/bot"
        + bot_token
        + "/sendMessage"
    )

    telegram_data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message[:4000],
        "disable_web_page_preview": "true"
    }).encode("utf-8")

    telegram_request = urllib.request.Request(
        telegram_url,
        data=telegram_data,
        method="POST"
    )

    with urllib.request.urlopen(telegram_request, timeout=30) as response:
        telegram_result = json.loads(response.read().decode("utf-8"))

    if not telegram_result.get("ok"):
        raise SystemExit("Telegram did not accept the message.")

    print("CONTENT: SUCCESS")
    print("PRODUCTS USED:", len(products))
    print("TELEGRAM: DRAFT SENT")
    print("No social post was published.")


if __name__ == "__main__":
    main()
