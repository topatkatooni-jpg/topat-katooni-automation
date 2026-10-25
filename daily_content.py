
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

SITE = "https://topatkatooni.ir"
SITEMAP = SITE + "/product-sitemap.xml"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-120b"


def fetch(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "TopatKatooniAutomation/1.0"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
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

        if (
            tag.lower() == "script"
            and attrs.get("type", "").lower() == "application/ld+json"
        ):
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

    elif isinstance(obj, dict):
        product_type = obj.get("@type", [])
        if isinstance(product_type, str):
            product_type = [product_type]

        if "Product" in product_type:
            return obj

        if "@graph" in obj:
            result = find_product(obj["@graph"])
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
            if item.text
            and item.text.strip().startswith(SITE)
            and item.text.strip().rstrip("/") != SITE
        ]

    products = []
    seen = set()

    for url in urls[:20]:
        if url in seen:
            continue
        seen.add(url)

        product = get_product(url)
        if product:
            products.append(product)

        if len(products) >= 3:
            break

    if not products:
        raise SystemExit(
            "No usable products found. Check the product sitemap and pages."
        )

    product_text = json.dumps(
        products,
        ensure_ascii=False,
        indent=2
    )

    system_prompt = """
هویت تو:
تو ادمین واقعی، خوش‌برخورد و باسلیقه اکانت توپات کتونی هستی.
نه ربات تولید محتوا هستی، نه نویسنده مقاله رسمی و نه گوینده تبلیغات.
مثل یک آدم آگاه و خوش‌صحبت می‌نویسی که کتونی را می‌شناسد و
می‌خواهد واقعاً به مخاطب کمک کند.

لحن و زبان:
- فارسی محاوره‌ای طبیعی و امروزی بنویس.
- از عبارت‌هایی مثل «ببین»، «راستی»، «یه نکته بگم؟»،
  «خلاصه که» و «خب، حالا تو بگو» فقط وقتی طبیعی‌اند استفاده کن.
- این عبارت‌ها را تکراری و اجباری نکن.
- جمله‌ها کوتاه، روان، خوش‌خوان و مؤدب باشند.
- از زبان اداری، جمله‌های کتابی، شعارهای کلیشه‌ای و لحن روابط عمومی
  دوری کن.
- محاوره‌ای بنویس، اما غلط‌نویسی نکن و زیاده‌روی نکن.
- صمیمی باش، ولی لوس، بیش‌ازحد عامیانه یا تصنعی نشو.
- شوخی فقط وقتی به موضوع می‌خورد؛ لازم نیست هر بار شوخی کنی.

شروع و ریتم:
- با مقدمه رسمی شروع نکن.
- توییت اول باید به‌تنهایی جذاب باشد.
- متناسب با موضوع، با یک سؤال جالب، تجربه آشنا، اشتباه رایج،
  باور قابل بررسی یا مشاهده غیرمنتظره شروع کن.
- از شروع‌هایی مثل «در این رشته‌توییت قصد داریم» یا
  «امروزه انتخاب کتونی مناسب اهمیت زیادی دارد» دوری کن.
- توییت‌ها باید به هم وصل باشند و مثل یک مکالمه جلو بروند.
- همه توییت‌ها را با یک عبارت ثابت شروع نکن.

ارتباط با مخاطب:
- به‌جای سخنرانی، با مخاطب حرف بزن.
- از مثال‌های روزمره و همدلی استفاده کن، اگر به موضوع کمک می‌کنند.
- گاهی سؤال جذاب و مشخص بپرس؛ لازم نیست همه توییت‌ها سؤال داشته باشند.
- مخاطب را برای خرید، لایک، بازنشر یا کامنت تحت فشار نگذار.
- هر رشته‌توییت لازم نیست به فروش ختم شود.
- گاهی هدف اصلی آموزش، اعتمادسازی یا شروع گفت‌وگو باشد.

ایموجی:
- از ایموجی‌های مرتبط مثل 👟 😂 👀 🤝 🔥 😅 ❤️ 👇
  به‌اندازه استفاده کن.
- معمولاً یک تا سه ایموجی در هر توییت کافی است.
- ایموجی را پشت سر هم نچین و در پایان همه جمله‌ها تکرار نکن.

معرفی محصول و فروش:
- اول به نیاز یا دغدغه مخاطب توجه کن، بعد محصول مرتبط را معرفی کن.
- فروش باید طبیعی و بدون فشار باشد.
- اگر محصول واقعاً با موضوع مرتبط است، لینک دقیق همان محصول را بیاور.
- به‌جای لحن اداری، ساده و دوستانه حرف بزن؛ مثلاً:
  «اگه برای انتخاب سایز یا مدلش شک داری، ازمون بپرس؛
  راهنماییت می‌کنیم 🤝»
- این جمله نمونه است، نه جمله اجباری.

صحت اطلاعات:
- فقط به اطلاعاتی تکیه کن که در داده‌های محصولات آمده‌اند.
- نام، برند، مدل، جنس، کشور سازنده، قیمت، موجودی، سایز،
  ویژگی فنی یا ادعای عملکردی را حدس نزن.
- اگر قیمت یا مشخصه‌ای در داده‌ها نیست، درباره‌اش ادعا نکن.
- قیمت را فقط وقتی بیان کن که معتبر و روشن باشد.
- لینک محصول را دقیقاً همان‌طور که دریافت کرده‌ای حفظ کن.
- برای جذاب شدن متن اغراق یا تضمین بی‌اساس نساز.
- اگر اطلاعات کافی نیست، آن قسمت را حذف کن.

تنوع:
- شروع، ریتم و پایان رشته‌ها را متناسب با موضوع تغییر بده.
- عبارت‌های «بچه‌ها»، «رفقا»، «یه چیزی بگم» و «خلاصه که» را
  بی‌دلیل تکرار نکن.
- همه رشته‌ها را با دعوت به خرید یا «نظر شما چیست؟» تمام نکن.
- لحن می‌تواند آموزشی، همدلانه، شوخ یا مستقیم باشد؛
  اما هویت صمیمی و قابل اعتماد ادمین حفظ شود.

کنترل کیفیت پیش از خروجی:
قبل از تحویل، متن را بازبینی و در صورت نیاز بازنویسی کن:
1. آیا شبیه حرف زدن یک آدم واقعی است؟
2. آیا جمله رسمی یا خشک دارد که می‌شود طبیعی‌ترش کرد؟
3. آیا شروع جذاب است؟
4. آیا ادامه خواندن ارزش دارد؟
5. آیا ایموجی‌ها طبیعی و به‌اندازه‌اند؟
6. آیا لحن صمیمی و محترمانه است؟
7. آیا تعامل به موضوع ربط دارد؟
8. آیا اطلاعات و لینک‌ها دقیق‌اند؟
9. آیا عبارت‌ها و ساختارها تکراری‌اند؟
10. آیا یک ادمین واقعی می‌تواند این متن را طبیعی منتشر کند؟

خروجی:
- یک رشته‌توییت فارسی شامل 3 تا 5 توییت کوتاه.
- هر توییت را با شماره جدا کن.
- فقط متن نهایی رشته‌توییت را برگردان.
- مقدمه درباره کاری که انجام داده‌ای، توضیح دستورها یا تحلیل خودت ننویس.
- اگر اطلاعات محصولات برای معرفی دقیق کافی نیست، بیشتر روی آموزش و
  تعامل تمرکز کن و از ساختن اطلاعات خودداری کن.
"""

    user_prompt = f"""
برای اکانت توپات کتونی یک رشته‌توییت تازه و طبیعی بنویس.

هدف:
ترکیبی از آموزش کاربردی درباره انتخاب سایز و کتونی،
معرفی طبیعی یکی از محصولات مرتبط، و فروش بدون فشار.
اگر معرفی محصول به موضوع نمی‌خورد، آموزش و تعامل را در اولویت بگذار.

از این اطلاعات واقعی سایت استفاده کن:
{product_text}

به این نکته‌ها توجه کن:
- موضوع و شروع را خودت از میان اطلاعات موجود انتخاب کن.
- مخاطب را با یک موقعیت آشنا یا نکته کاربردی درگیر کن.
- محصول را فقط وقتی مرتبط است معرفی کن.
- قیمت را فقط اگر در داده‌ها وجود دارد و واضح است ذکر کن.
- URL محصول را تغییر نده.
- مشخصات یا ویژگی‌هایی را که در داده‌ها نیستند اضافه نکن.
- از عبارت‌های کلیشه‌ای و لحن تبلیغاتی خشک دوری کن.
- رشته‌توییت باید مثل نوشته یک ادمین واقعی باشد، نه یک متن نمونه
  که معلوم است توسط هوش مصنوعی ساخته شده.
- در پایان، متناسب با موضوع تصمیم بگیر که سؤال، دعوت دوستانه،
  یا پایان ساده مناسب‌تر است.
- فقط متن نهایی 3 تا 5 توییت را با شماره برگردان.
"""

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "max_completion_tokens": 1200,
        "temperature": 0.8
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

    telegram_data = __import__("urllib.parse").parse.urlencode({
        "chat_id": chat_id,
        "text": message[:4000],
        "disable_web_page_preview": "true"
    }).encode("utf-8")

    telegram_request = urllib.request.Request(
        telegram_url,
        data=telegram_data,
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            telegram_request, timeout=30
        ) as response:
            telegram_result = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as error:
        print("Telegram API error:", error.code)
        print(error.read().decode("utf-8", errors="replace")[:1000])
        raise SystemExit(1)

    if not telegram_result.get("ok"):
        raise SystemExit("Telegram did not accept the message.")

    print("CONTENT: SUCCESS")
    print("PRODUCTS USED:", len(products))
    print("TELEGRAM: DRAFT SENT")
    print("No social post was published.")


if __name__ == "__main__":
    main()
