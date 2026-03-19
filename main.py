import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncpg

# --- НАСТРОЙКИ ---
# Вставь свой токен от BotFather
API_TOKEN = '8717755678:AAFxBTzyDghHPLYOstlvkeNsUjgBStP3KHg'
# Твои ID администраторов
ADMIN_IDS = [8209617821, 8384467554] 
# Твоя ссылка на базу pghost.ru
DATABASE_URL = 'postgresql://bothost_db_29f14895d3aa:tbdVGmS3JoNrcauznAFgzNTJgefFJE3xE33flLLZY5M@node1.pghost.ru:32854/bothost_db_29f14895d3aa'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния для админки
class AdminStates(StatesGroup):
    adding_accounts = State()

# Пул соединений для быстрой работы
db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return db_pool

# --- ОБРАБОТЧИКИ (HANDLERS) ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = [
        [types.KeyboardButton(text="🛒 Купить аккаунт")],
        [types.KeyboardButton(text="📊 Наличие")]
    ]
    if message.from_user.id in ADMIN_IDS:
        kb.append([types.KeyboardButton(text="➕ Добавить базу")])
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "👋 <b>Добро пожаловать в магазин почт!</b>\n\n"
        "Нажмите на кнопку ниже, чтобы получить аккаунт.",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# --- ЛОГИКА ПОКУПКИ (БЕЗ ОШИБОК Markdown) ---
@dp.message(F.text == "🛒 Купить аккаунт")
async def buy_account(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Атомарно забираем и удаляем строку
            row = await conn.fetchrow('''
                DELETE FROM accounts 
                WHERE id = (SELECT id FROM accounts ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED) 
                RETURNING data
            ''')
            
            if row:
                acc_data = row['data']
                # Формируем сообщение в HTML (безопасно для символов ! . @)
                response_text = (
                    f"✅ <b>Ваш аккаунт куплен!</b>\n\n"
                    f"<code>{acc_data}</code>\n\n"
                    f"⚠️ <i>Данные удалены из базы. Сохраните их!</i>"
                )
                
                try:
                    await message.answer(response_text, parse_mode="HTML")
                except Exception as e:
                    logging.error(f"Ошибка HTML-отправки: {e}")
                    # Резервный вариант: чистый текст без оформления
                    await message.answer(f"Ваш аккаунт:\n{acc_data}")
            else:
                await message.answer("❌ Извините, товар закончился. Зайдите позже!")

@dp.message(F.text == "📊 Наличие")
async def check_stock(message: types.Message):
    pool = await get_db_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM accounts")
    await message.answer(f"📦 Сейчас в наличии: <b>{count} шт.</b>", parse_mode="HTML")

# --- АДМИНКА ---

@dp.message(F.text == "➕ Добавить базу")
async def admin_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.adding_accounts)
    await message.answer(
        "📥 <b>Пришли список аккаунтов.</b>\n"
        "Каждый аккаунт с новой строки. Формат: <code>login:pass</code>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.adding_accounts)
async def process_adding(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    # Разбиваем текст на строки и убираем пустые
    accounts = [a.strip() for a in message.text.split('\n') if a.strip()]
    added_count = 0
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        for acc in accounts:
            try:
                # Вставляем, игнорируя дубликаты
                res = await conn.execute(
                    "INSERT INTO accounts (data) VALUES ($1) ON CONFLICT DO NOTHING", 
                    acc
                )
                if res == "INSERT 0 1":
                    added_count += 1
            except Exception as e:
                logging.error(f"Ошибка вставки: {e}")
    
    await state.clear()
    await message.answer(f"✅ Успешно добавлено: <b>{added_count}</b> шт.", parse_mode="HTML")

async def main():
    logging.basicConfig(level=logging.INFO)
    # Создаем таблицу, если её нет
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                data TEXT UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен")
