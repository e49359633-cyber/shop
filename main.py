import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncpg

# Твои данные
API_TOKEN = '8717755678:AAFxBTzyDghHPLYOstlvkeNsUjgBStP3KHg'
ADMIN_IDS = [8209617821, 8384467554]
DB_URL = 'postgresql://bothost_db_29f14895d3aa:tbdVGmS3JoNrcauznAFgzNTJgefFJE3xE33flLLZY5M@node1.pghost.ru:32854/bothost_db_29f14895d3aa'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- Логика Базы Данных ---

async def buy_account():
    """Находит 1 аккаунт, помечает его как проданный и возвращает данные"""
    conn = await asyncpg.connect(DB_URL)
    # Используем UPDATE с RETURNING, чтобы атомарно забрать и пометить аккаунт
    row = await conn.fetchrow('''
        UPDATE accounts 
        SET is_sold = TRUE 
        WHERE id = (
            SELECT id FROM accounts WHERE is_sold = FALSE LIMIT 1 FOR UPDATE SKIP LOCKED
        ) 
        RETURNING data
    ''')
    await conn.close()
    return row['data'] if row else None

# --- Клавиатуры ---

def get_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🛒 Купить почту (1 шт.)", callback_data="buy_mail"))
    return builder.as_markup()

# --- Хендлеры ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Добро пожаловать в магазин почт Mail.ru.\n\n"
        "Нажми на кнопку ниже, чтобы получить аккаунт.",
        reply_markup=get_main_kb()
    )

@dp.callback_query(F.data == "buy_mail")
async def process_buy(callback: types.CallbackQuery):
    account_data = await buy_account()
    
    if account_data:
        await callback.message.answer(
            f"✅ **Ваш аккаунт готов:**\n\n`{account_data}`\n\n"
            f"Спасибо за покупку!",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer("❌ К сожалению, все почты распроданы. Зайдите позже!")
    
    await callback.answer() # Убираем "часики" с кнопки

# Хендлер для админов (добавление почт)
@dp.message(F.text, F.from_user.id.in_(ADMIN_IDS))
async def admin_add_mails(message: types.Message):
    if ":" in message.text:
        accounts = [line.strip() for line in message.text.split('\n') if ":" in line]
        conn = await asyncpg.connect(DB_URL)
        await conn.executemany(
            "INSERT INTO accounts (data) VALUES ($1) ON CONFLICT (data) DO NOTHING",
            [(acc,) for acc in accounts]
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM accounts WHERE is_sold = FALSE")
        await conn.close()
        await message.answer(f"📦 Добавлено! Сейчас в наличии: {count} шт.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
