
import json
import os
import urllib.error
import urllib.request

API_KEY = os.environ.get("GROQ_API_KEY")

if not API_KEY:
    raise SystemExit("ERROR: GROQ_API_KEY is not configured.")

url = "https://api.groq.com/openai/v1/chat/completions"

payload = {
"model": "openai/gpt-oss-120b",
    "messages": [
        {
            "role": "system",
            "content": (
                "تو نویسنده فارسی فروشگاه کتونی توپات کتونی هستی. "
                "فقط متن فارسی کوتاه، طبیعی و روان بنویس. "
                "هیچ قیمت یا مشخصات محصولی را جعل نکن."
            )
        },
        {
            "role": "user",
            "content": (
                "یک رشته‌توییت آزمایشی شامل 3 توییت کوتاه درباره "
                "اشتباه رایج در انتخاب سایز کتونی بنویس. "
                "محصول یا قیمت فرضی معرفی نکن."
            )
        }
    ],
    "max_completion_tokens": 350,
    "temperature": 0.5
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "TopatKatooni-Automation/1.0"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    print("CONNECTION: SUCCESS")
    print("MODEL:", result.get("model", "unknown"))
    print(
        "USAGE:",
        json.dumps(result.get("usage", {}), ensure_ascii=False)
    )
    print("OUTPUT:")
    print(result["choices"][0]["message"]["content"])

except urllib.error.HTTPError as error:
    print("API ERROR:", error.code)

    details = error.read().decode("utf-8", errors="replace")
    print("ERROR DETAILS:")
    print(details[:2000])

    raise SystemExit(1)

except Exception as error:
    print("CONNECTION ERROR:", str(error))
    raise SystemExit(1)
