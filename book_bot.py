import os
import logging
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PyPDF2 import PdfReader
from openai import OpenAI

TOKEN = os.environ.get("BOT_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# Настройка клиента OpenRouter
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

logging.basicConfig(level=logging.INFO)

book_text = ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Привет! Я ИИ-бот по книгам!\n\n"
        "1. Отправь мне PDF-файл книги\n"
        "2. Задавай любые вопросы по содержанию\n\n"
        "⚡ Бесплатный тариф: ~50 вопросов в день."
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global book_text
    file = await update.message.document.get_file()
    pdf_bytes = await file.download_as_bytearray()

    await update.message.reply_text("📖 Читаю книгу, подожди немного...")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    book_text = text[:12000]
    await update.message.reply_text(
        f"✅ Книга загружена! (≈ {len(book_text)} символов)\n\n"
        f"Теперь задавай вопросы. Бот будет отвечать с помощью нейросети."
    )

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global book_text
    if not book_text:
        await update.message.reply_text("Сначала отправь PDF-книгу.")
        return

    if not OPENROUTER_API_KEY:
        await update.message.reply_text(
            "❌ OpenRouter API ключ не настроен.\n"
            "Добавьте переменную OPENROUTER_API_KEY в настройках Render."
        )
        return

    question = update.message.text
    await update.message.reply_text("🤔 Анализирую книгу... (ИИ-модель)")

    try:
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[
                {"role": "system", "content": f"Ты — помощник. Отвечай на вопросы строго на основе текста книги. Не выдумывай фактов. Вот текст книги:\n\n{book_text}"},
                {"role": "user", "content": question}
            ],
            max_tokens=500,
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(f"📖 **Ответ:**\n\n{answer}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nПопробуйте позже или задайте другой вопрос.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question))
    print("Бот с ИИ запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
