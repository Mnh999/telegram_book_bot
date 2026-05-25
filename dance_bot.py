import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# База данных
engine = create_engine('sqlite:///dance_bot.db', connect_args={'check_same_thread': False})
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

# Модели базы данных
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String)
    full_name = Column(String)

class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    date = Column(DateTime)
    status = Column(String, default='active')

class Schedule(Base):
    __tablename__ = 'schedule'
    id = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True)
    is_available = Column(Boolean, default=True)

Base.metadata.create_all(engine)

# Настройка бота
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Хранилище сессий администратора
admin_sessions = {}

# Клавиатуры
def main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📅 Записаться", callback_data="book"),
        InlineKeyboardButton("📋 Мои записи", callback_data="my_bookings"),
        InlineKeyboardButton("ℹ️ О студии", callback_data="info"),
        InlineKeyboardButton("💰 Цены", callback_data="prices")
    )
    return keyboard

def admin_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ Добавить слот", callback_data="admin_add_slot"),
        InlineKeyboardButton("❌ Удалить слот", callback_data="admin_remove_slot"),
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("💰 Сменить цену", callback_data="admin_price"),
        InlineKeyboardButton("📝 Контакты", callback_data="admin_contacts"),
        InlineKeyboardButton("🚪 Выйти", callback_data="admin_logout")
    )
    return keyboard

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    # Сохраняем пользователя
    user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
    if not user:
        user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        session.add(user)
        session.commit()
    
    await message.answer(
        "💃 Добро пожаловать в студию танцев!\n\n"
        "Здесь вы можете:\n"
        "• Записаться на занятие\n"
        "• Посмотреть свои записи\n"
        "• Узнать цены и контакты\n\n"
        "Выберите действие:",
        reply_markup=main_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "book")
async def process_book(callback_query: types.CallbackQuery):
    # Получаем доступные слоты
    tomorrow = datetime.now() + timedelta(days=1)
    slots = session.query(Schedule).filter(
        Schedule.date >= tomorrow,
        Schedule.is_available == True
    ).limit(10).all()
    
    if not slots:
        await bot.answer_callback_query(
            callback_query.id,
            "К сожалению, пока нет доступных слотов. Загляните позже!",
            show_alert=True
        )
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for slot in slots:
        date_str = slot.date.strftime("%d.%m.%Y %H:%M")
        keyboard.add(InlineKeyboardButton(date_str, callback_data=f"select_slot_{slot.id}"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu"))
    
    await bot.edit_message_text(
        "Выберите дату и время занятия:",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith("select_slot_"))
async def process_select_slot(callback_query: types.CallbackQuery):
    slot_id = int(callback_query.data.split("_")[2])
    slot = session.query(Schedule).filter_by(id=slot_id).first()
    
    if not slot or not slot.is_available:
        await bot.answer_callback_query(
            callback_query.id,
            "Этот слот уже занят или недоступен!",
            show_alert=True
        )
        return
    
    # Создаём запись
    booking = Booking(
        user_id=callback_query.from_user.id,
        date=slot.date
    )
    slot.is_available = False
    session.add(booking)
    session.commit()
    
    await bot.answer_callback_query(
        callback_query.id,
        f"✅ Вы записаны на {slot.date.strftime('%d.%m.%Y %H:%M')}!",
        show_alert=True
    )
    
    await bot.edit_message_text(
        f"✅ Вы успешно записаны!\n\n"
        f"📅 Дата: {slot.date.strftime('%d.%m.%Y %H:%M')}\n\n"
        "Ждём вас!",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")
        )
    )

@dp.callback_query_handler(lambda c: c.data == "my_bookings")
async def process_my_bookings(callback_query: types.CallbackQuery):
    bookings = session.query(Booking).filter_by(
        user_id=callback_query.from_user.id,
        status='active'
    ).order_by(Booking.date).all()
    
    if not bookings:
        await bot.answer_callback_query(
            callback_query.id,
            "У вас пока нет активных записей.",
            show_alert=True
        )
        return
    
    text = "📋 **Ваши записи:**\n\n"
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for booking in bookings:
        date_str = booking.date.strftime("%d.%m.%Y %H:%M")
        text += f"• {date_str}\n"
        keyboard.add(InlineKeyboardButton(f"❌ Отменить {date_str}", callback_data=f"cancel_{booking.id}"))
    
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu"))
    
    await bot.edit_message_text(
        text,
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("cancel_"))
async def process_cancel_booking(callback_query: types.CallbackQuery):
    booking_id = int(callback_query.data.split("_")[1])
    booking = session.query(Booking).filter_by(id=booking_id).first()
    
    if booking:
        # Возвращаем слот в расписание
        slot = session.query(Schedule).filter_by(date=booking.date).first()
        if slot:
            slot.is_available = True
        booking.status = 'cancelled'
        session.commit()
        
        await bot.answer_callback_query(
            callback_query.id,
            "Запись отменена!",
            show_alert=True
        )
    
    # Обновляем список записей
    await process_my_bookings(callback_query)

@dp.callback_query_handler(lambda c: c.data == "info")
async def process_info(callback_query: types.CallbackQuery):
    text = (
        "🏢 **О нашей студии**\n\n"
        "Мы — современная школа танцев с профессиональными преподавателями.\n\n"
        "📍 **Адрес:** ул. Танцевальная, 15\n"
        "📞 **Телефон:** +7 (999) 123-45-67\n"
        "📧 **Email:** dance@studio.ru\n\n"
        "🕒 **Время работы:** Пн-Вс 10:00 - 22:00"
    )
    
    await bot.edit_message_text(
        text,
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "prices")
async def process_prices(callback_query: types.CallbackQuery):
    text = (
        "💰 **Наши цены**\n\n"
        "• Разовое занятие — 500₽\n"
        "• Абонемент на 4 занятия — 1800₽\n"
        "• Абонемент на 8 занятий — 3200₽\n"
        "• Пробное занятие — 300₽\n\n"
        "❄️ Действуют скидки для студентов!"
    )
    
    await bot.edit_message_text(
        text,
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")
        ),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "back_to_menu")
async def process_back_to_menu(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        "💃 Главное меню:\n\nВыберите действие:",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=main_keyboard()
    )

# Административная часть
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    args = message.get_args()
    if not args:
        await message.answer("Введите пароль: /admin ваш_пароль")
        return
    
    if args == ADMIN_PASSWORD:
        admin_sessions[message.from_user.id] = True
        await message.answer(
            "🔐 Добро пожаловать в админ-панель!\n\n"
            "Выберите действие:",
            reply_markup=admin_keyboard()
        )
    else:
        await message.answer("❌ Неверный пароль!")

@dp.callback_query_handler(lambda c: c.data == "admin_add_slot")
async def admin_add_slot(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admin_sessions:
        await bot.answer_callback_query(callback_query.id, "Доступ запрещён!")
        return
    
    await bot.edit_message_text(
        "➕ **Добавление слота**\n\n"
        "Введите дату и время в формате:\n"
        "`2024-12-25 18:30`\n\n"
        "Например: 2024-12-25 18:30\n\n"
        "Для отмены введите /cancel",
        callback_query.from_user.id,
        callback_query.message.message_id,
        parse_mode="Markdown"
    )
    
    # Устанавливаем состояние ожидания ввода
    # (в реальном коде нужно добавить state machine)

@dp.callback_query_handler(lambda c: c.data == "admin_remove_slot")
async def admin_remove_slot(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admin_sessions:
        await bot.answer_callback_query(callback_query.id, "Доступ запрещён!")
        return
    
    slots = session.query(Schedule).filter_by(is_available=True).order_by(Schedule.date).all()
    
    if not slots:
        await bot.answer_callback_query(callback_query.id, "Нет доступных слотов для удаления!")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for slot in slots:
        date_str = slot.date.strftime("%d.%m.%Y %H:%M")
        keyboard.add(InlineKeyboardButton(f"❌ {date_str}", callback_data=f"admin_del_slot_{slot.id}"))
    keyboard.add(InlineKeyboardButton("◀️ Назад", callback_data="admin_back"))
    
    await bot.edit_message_text(
        "Выберите слот для удаления:",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data == "admin_stats")
async def admin_stats(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admin_sessions:
        await bot.answer_callback_query(callback_query.id, "Доступ запрещён!")
        return
    
    total_users = session.query(User).count()
    active_bookings = session.query(Booking).filter_by(status='active').count()
    total_bookings = session.query(Booking).count()
    
    text = (
        "📊 **Статистика**\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"📅 Активных записей: {active_bookings}\n"
        f"📋 Всего записей: {total_bookings}\n"
        f"💰 Выручка: {active_bookings * 500}₽ (при цене 500₽)"
    )
    
    await bot.edit_message_text(
        text,
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        ),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "admin_back")
async def admin_back(callback_query: types.CallbackQuery):
    await bot.edit_message_text(
        "🔐 Админ-панель\n\nВыберите действие:",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=admin_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == "admin_logout")
async def admin_logout(callback_query: types.CallbackQuery):
    if callback_query.from_user.id in admin_sessions:
        del admin_sessions[callback_query.from_user.id]
    
    await bot.edit_message_text(
        "Вы вышли из админ-панели.",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_menu")
        )
    )

@dp.callback_query_handler(lambda c: c.data == "admin_price")
async def admin_price(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admin_sessions:
        await bot.answer_callback_query(callback_query.id, "Доступ запрещён!")
        return
    
    await bot.edit_message_text(
        "💰 **Изменение цен**\n\n"
        "Эта функция в разработке.\n"
        "Пока что цены хранятся в коде.\n\n"
        "Вы можете отредактировать их вручную в файле `bot.py`.",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        ),
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "admin_contacts")
async def admin_contacts(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admin_sessions:
        await bot.answer_callback_query(callback_query.id, "Доступ запрещён!")
        return
    
    await bot.edit_message_text(
        "📝 **Редактирование контактов**\n\n"
        "Эта функция в разработке.\n"
        "Пока что контакты хранятся в коде.\n\n"
        "Вы можете отредактировать их вручную в файле `bot.py`.",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("◀️ Назад", callback_data="admin_back")
        ),
        parse_mode="Markdown"
    )

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
