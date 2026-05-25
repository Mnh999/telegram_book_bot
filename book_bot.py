import os
import logging
import io
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PyPDF2 import PdfReader

TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# Хранилище текста книги
book_text = ""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне PDF-книгу, и я запомню её.")


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

    # Сохраняем только первые 3000 символов для экономии памяти
    book_text = text[:3000]
    await update.message.reply_text(f"✅ Книга загружена! Теперь задавай вопросы (первые 3000 символов).")


async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global book_text
    if not book_text:
        await update.message.reply_text("Сначала отправь PDF-книгу.")
        return

    question = update.message.text.lower()
    await update.message.reply_text("🔍 Ищу ответ в книге...")

    # Простой поиск: ищем предложение, где встречается вопрос или его часть
    lines = book_text.split(". ")
    found = []
    for line in lines:
        if any(word in line.lower() for word in question.split()):
            found.append(line.strip())

    if found:
        answer = ". ".join(found[:3])
        await update.message.reply_text(f"📖 Вот что нашлось в книге:\n\n{answer[:1000]}")
    else:
        await update.message.reply_text("🤷 Не нашёл в книге ответа на ваш вопрос.")


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question))
    print("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()
