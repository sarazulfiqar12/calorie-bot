import os
import threading
import requests
import base64
from http.server import HTTPServer, BaseHTTPRequestHandler
from groq import Groq
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GROQ_KEY = os.environ["GROQ_KEY"]

client = Groq(api_key=GROQ_KEY)

SYSTEM_PROMPT = """You are Nouri, a friendly and caring personal nutritionist chatbot on Telegram.
You talk like a close friend — casual, warm, funny, and supportive. Never preachy or boring.
Use simple language. Keep replies short but interesting .
Use emojis occasionally to feel friendly.

Your jobs:
- Chat naturally to find out what the user is eating
- When they mention food, estimate calories in a friendly way
- Ask them about their health goal (lose weight, gain muscle, eat healthier or getting glowing skin)
- Encourage them warmly when they make healthy choices
- if they don't want to do exercise due to tough routine , don't suggest them any heavy task just suggest them to do light exercise like taking half hour walk or any light exercise that they can do easily while sitting or lying down.
- Gently warn them (never lecture!) if something is very unhealthy
- Ask them to share a photo of their food sometimes

When analyzing food photos:
- Identify all food items you can see
- Estimate total calories
- Mention if anything is too high calorie for a diet
- Give one friendly suggestion

Never give medical advice. Always be positive and supportive."""

conversations = {}


def get_response(user_id, user_text):
    if user_id not in conversations:
        conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversations[user_id].append({"role": "user", "content": user_text})

    if len(conversations[user_id]) > 20:
        conversations[user_id] = [conversations[user_id][0]] + conversations[user_id][
            -19:
        ]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile", messages=conversations[user_id], max_tokens=300
    )

    reply = response.choices[0].message.content

    conversations[user_id].append({"role": "assistant", "content": reply})

    return reply


def analyze_photo(image_bytes):
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                    {
                        "type": "text",
                        "text": """You are Nouri, a friendly nutritionist. Analyze this food photo and:
1. List what foods you see
2. Estimate total calories
3. Say if it fits a healthy diet
4. Give proper calorie estimation of each food item if there are more than one dish in the photo
Keep it short, warm and friendly. also Use emojis! encourage person to eat healthy and if in photo, if something is unhealthy and high in calorie , point it out and suggest it to leave it out or eat it in moderation and then motivate them for weight loss and healthy eating""",
                    },
                ],
            }
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.effective_user.first_name
    user_id = update.effective_user.id
    conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    await update.message.reply_text(
        f"Hey {user_name}! 👋 I'm Nouri, your personal calorie tracker and nutrition buddy!\n\n"
        "I'm here to help you:\n"
        "🍎 Track what you eat\n"
        "📸 Analyze food from photos\n"
        "🚶 Track your daily steps\n"
        "💪 Reach your health goals\n\n"
        "First things first — what's your health goal right now?\n\n"
        "1 - Lose weight\n"
        "2 - Gain muscle\n"
        "3 - Just eat healthier"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    await update.message.chat.send_action("typing")

    try:
        reply = get_response(user_id, user_text)
        await update.message.reply_text(reply)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("Oops! Something went wrong 😅 Try again!")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action("typing")

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()

        await update.message.reply_text("📸 Let me check out what you're eating...")

        reply = analyze_photo(bytes(image_bytes))
        await update.message.reply_text(reply)

    except Exception as e:
        print(f"Photo error: {e}")
        await update.message.reply_text(
            "Hmm I couldn't analyze that photo 😅 Try sending it again!"
        )


class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Nouri bot is alive!")

    def log_message(self, format, *args):
        pass


def run_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()


def main():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()
    print("Web server started...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
