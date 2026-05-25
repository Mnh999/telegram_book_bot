import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import io

TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

index = None
chunks = []
model = SentenceTransformer('all-MiniLM-L6-v2')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне PDF-книгу, и я смогу по ней отвечать.")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global index, chunks
    file = await update.message.document.get_file()
    pdf_bytes = await file.download_as_bytearray()
    
    await update.message.reply_text("📖 Читаю книгу, подожди минуту...")

    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)

    embeddings = model.encode(chunks)
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(np.array(embeddings).astype('float32'))

    await update.message.reply_text(f"✅ Готово! Книга из {len(chunks)} отрывков загружена. Теперь задавай вопросы.")

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global index, chunks
    if index is None:
        await update.message.reply_text("Сначала отправь PDF-книгу.")
        return

    question = update.message.text
    q_emb = model.encode([question])
    distances, idxs = index.search(np.array(q_emb).astype('float32'), k=3)

    context_text = "\n\n".join([chunks[i] for i in idxs[0]])

    answer = f"🔍 Вот что я нашёл в книге:\n\n{context_text[:1500]}"
    await update.message.reply_text(answer)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ask_question))
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
