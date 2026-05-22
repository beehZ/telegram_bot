import os
from openai import OpenAI
from dotenv import load_dotenv

# .env faylidan o'zgaruvchilarni yuklash
load_dotenv()

def check_grok_api():
    # .env faylidan kalitni o'qish
    api_key = os.getenv("GROK_API_KEY")

    if not api_key:
        print("❌ Xatolik: .env faylida GROK_API_KEY topilmadi!")
        return

    print("🔄 Grok API tekshirilmoqda...")

    try:
        # xAI (Grok) uchun mijozni sozlash
        # Grok API'ning asosiy URL manzili xAI tomonidan taqdim etiladi
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

        completion = client.chat.completions.create(
            model="grok-4.3",
            messages=[
                {"role": "user", "content": "Hello, Grok! Just a quick test to see if you are working."}
            ]
        )

        # Javobni konsolga chiqarish
        reply = completion.choices[0].message.content
        print("✅ API muvaffaqiyatli ishlayapti!")
        print(f"🤖 Grok javobi: {reply}")

    except Exception as e:
        print(f"❌ Xatolik yuz berdi: {e}")

if __name__ == "__main__":
    check_grok_api()