import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

logging.basicConfig(level=logging.INFO)

# Хранилища данных (в памяти, для простоты)
users = {}
bookings = {}
schedule = {}

# Простая структура расписания (можно расширить)
available_slots = [
    "2026-06-01 18:00",
    "2026-06-01 19:00",
    "2026-06-02 18:00",
    "2026-06-02 19:00",
    "2026-06-03 18:00",
]

admin_sessions = {}

# Клавиатуры
def main_keyboard():
    keyboard = [
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings")],
        [InlineKeyboardButton("ℹ️ О студии", callback_data="info")],
        [InlineKeyboardButton("💰 Цены", callback_data="prices")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Добавить слот", callback_data="admin_add_slot")],
        [InlineKeyboardButton("❌ Удалить слот", callback_data="admin_remove_slot")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🚪 Выйти", callback_data="admin_logout")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in users:
        users[user_id] = {
            "id": user_id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
        }
    
    await update.message.reply_text(
        "💃 Добро пожаловать в студию танцев!\n\n"
        "Здесь вы можете:\n"
        "• Записаться на занятие\n"
        "• Посмотреть свои записи\n"
        "• Узнать цены и контакты\n\n"
        "Выберите действие:",
        reply_markup=main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == "book":
        # Показать доступные слоты
        keyboard = []
        for slot in available_slots:
            # Проверяем, не занят ли слот
            is_taken = False
            for b in bookings.values():
                if b.get("slot") == slot and b.get("status") == "active":
                    is_taken = True
                    break
            if not is_taken:
                keyboard.append([InlineKeyboardButton(slot, callback_data=f"book_{slot}")])
        
        if not keyboard:
            await query.edit_message_text(
                "К сожалению, пока нет доступных слотов. Загляните позже!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]])
            )
            return
        
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
        await query.edit_message_text(
            "Выберите дату и время занятия:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("book_"):
        slot = data[5:]
        # Проверяем, не занят ли слот
        for b in bookings.values():
            if b.get("slot") == slot and b.get("status") == "active":
                await query.edit_message_text(
                    "❌ Этот слот уже занят! Выберите другой.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]])
                )
                return
        
        # Создаём запись
        booking_id = len(bookings) + 1
        bookings[booking_id] = {
            "id": booking_id,
            "user_id": user_id,
            "slot": slot,
            "status": "active",
            "created_at": datetime.now()
        }
        
        await query.edit_message_text(
            f"✅ Вы успешно записаны!\n\n"
            f"📅 Дата: {slot}\n\n"
            f"Ждём вас!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")]])
        )
    
    elif data == "my_bookings":
        user_bookings = [b for b in bookings.values() if b["user_id"] == user_id and b["status"] == "active"]
        
        if not user_bookings:
            await query.edit_message_text(
                "📋 У вас пока нет активных записей.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]])
            )
            return
        
        text = "📋 **Ваши записи:**\n\n"
        keyboard = []
        for booking in user_bookings:
            text += f"• {booking['slot']}\n"
            keyboard.append([InlineKeyboardButton(f"❌ Отменить {booking['slot']}", callback_data=f"cancel_{booking['id']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("cancel_"):
        booking_id = int(data[7:])
        booking = bookings.get(booking_id)
        
        if booking and booking["user_id"] == user_id:
            booking["status"] = "cancelled"
            await query.edit_message_text(
                "✅ Запись отменена!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")]])
            )
        else:
            await query.edit_message_text(
                "❌ Запись не найдена.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]])
            )
    
    elif data == "info":
        text = (
            "🏢 **О нашей студии**\n\n"
            "Мы — современная школа танцев с профессиональными преподавателями.\n\n"
            "📍 **Адрес:** ул. Танцевальная, 15\n"
            "📞 **Телефон:** +7 (999) 123-45-67\n"
            "📧 **Email:** dance@studio.ru\n\n"
            "🕒 **Время работы:** Пн-Вс 10:00 - 22:00"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]),
            parse_mode="Markdown"
        )
    
    elif data == "prices":
        text = (
            "💰 **Наши цены**\n\n"
            "• Разовое занятие — 500₽\n"
            "• Абонемент на 4 занятия — 1800₽\n"
            "• Абонемент на 8 занятий — 3200₽\n"
            "• Пробное занятие — 300₽\n\n"
            "❄️ Действуют скидки для студентов!"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]),
            parse_mode="Markdown"
        )
    
    elif data == "back_to_menu":
        await query.edit_message_text(
            "💃 Главное меню:\n\nВыберите действие:",
            reply_markup=main_keyboard()
        )
    
    # Административные команды
    elif data == "admin_panel":
        if user_id in admin_sessions:
            await query.edit_message_text(
                "🔐 Админ-панель\n\nВыберите действие:",
                reply_markup=admin_keyboard()
            )
        else:
            await query.edit_message_text("Доступ запрещён!")
    
    elif data == "admin_add_slot":
        await query.edit_message_text(
            "➕ **Добавление слота**\n\n"
            "Пока эта функция в разработке.\n\n"
            "Слоты можно добавить вручную в список available_slots в коде.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )
    
    elif data == "admin_remove_slot":
        await query.edit_message_text(
            "❌ **Удаление слота**\n\n"
            "Пока эта функция в разработке.\n\n"
            "Слоты можно удалить вручную из списка available_slots в коде.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )
    
    elif data == "admin_stats":
        text = (
            "📊 **Статистика**\n\n"
            f"👥 Всего пользователей: {len(users)}\n"
            f"📅 Активных записей: {len([b for b in bookings.values() if b['status'] == 'active'])}\n"
            f"📋 Всего записей: {len(bookings)}\n"
        )
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_panel")]]),
            parse_mode="Markdown"
        )
    
    elif data == "admin_logout":
        if user_id in admin_sessions:
            del admin_sessions[user_id]
        await query.edit_message_text(
            "Вы вышли из админ-панели.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")]])
        )

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("Введите пароль: /admin ваш_пароль")
        return
    
    if args[0] == ADMIN_PASSWORD:
        admin_sessions[user_id] = True
        await update.message.reply_text(
            "🔐 Добро пожаловать в админ-панель!\n\n"
            "Выберите действие:",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_text("❌ Неверный пароль!")

def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("Бот для записи на танцы запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
