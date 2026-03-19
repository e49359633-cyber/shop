import asyncio
import logging
import asyncpg
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
API_TOKEN = '8717755678:AAFxBTzyDghHPLYOstlvkeNsUjgBStP3KHg'
ADMIN_IDS = [8209617821, 8384467554]
DATABASE_URL = 'postgresql://bothost_db_29f14895d3aa:tbdVGmS3JoNrcauznAFgzNTJgefFJE3xE33flLLZY5M@node1.pghost.ru:32854/bothost_db_29f14895d3aa'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    adding_accounts = State()

# Глобальная переменная для пула соединений
db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        # Создаем пул: минимум 1 соединение, максимум 10
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return db_pool

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = [
        [types.KeyboardButton(text="🛒 Купить аккаунт")],
        [types.KeyboardButton(text="📊 Наличие")]
    ]
    if message.from_user.id in ADMIN_IDS:
        kb.append([types.KeyboardButton(text="➕ Добавить базу")])
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("🚀 Бот готов к быстрой работе!", reply_markup=keyboard)

@dp.message(F.text == "🛒 Купить аккаунт")
async def buy_account(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Используем транзакцию для максимальной надежности
        async with conn.transaction():
            row = await conn.fetchrow('''
                DELETE FROM accounts 
                WHERE id = (SELECT id FROM accounts ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED) 
                RETURNING data
            ''')
            
            if row:
                await message.answer(f"✅ **Ваш аккаунт:**\n`{row['data']}`", parse_mode="MarkdownV2")
            else:
                await message.answer("❌ Товар закончился. Зайдите позже!")

@dp.message(F.text == "📊 Наличие")
async def check_stock(message: types.Message):
    pool = await get_db_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM accounts")
    await message.answer(f"📦 В наличии: {count} шт.")

@dp.message(F.text == "➕ Добавить базу")
async def admin_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminStates.adding_accounts)
    await message.answer("Отправь список аккаунтов (каждый с новой строки).")

@dp.message(AdminStates.adding_accounts)
async def process_adding(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    accounts = [a.strip() for a in message.text.split('\n') if a.strip()]
    
    pool = await get_db_pool()
    added_count = 0
    async with pool.acquire() as conn:
        for acc in accounts:
            res = await conn.execute("INSERT INTO accounts (data) VALUES ($1) ON CONFLICT DO NOTHING", acc)
            if res == "INSERT 0 1":
                added_count += 1
    
    await state.clear()
    await message.answer(f"✅ Успешно добавлено: {added_count}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await get_db_pool() # Инициализируем пул при старте
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
