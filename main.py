import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncpg

# --- НАСТРОЙКИ ---
API_TOKEN = '8717755678:AAFxBTzyDghHPLYOstlvkeNsUjgBStP3KHg'
ADMIN_IDS = [8209617821, 8384467554] 
DATABASE_URL = 'postgresql://bothost_db_29f14895d3aa:tbdVGmS3JoNrcauznAFgzNTJgefFJE3xE33flLLZY5M@node1.pghost.ru:32854/bothost_db_29f14895d3aa'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class AdminStates(StatesGroup):
    adding_accounts = State()

db_pool = None

async def get_db_pool():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return db_pool

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    kb = [
        [types.KeyboardButton(text="🛒 Купить аккаунт")],
        [types.KeyboardButton(text="📊 Наличие")]
    ]
    if message.from_user.id in ADMIN_IDS:
        kb.append([types.KeyboardButton(text="➕ Добавить базу")])
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Бот перезапущен. Пробуем голый текст.", reply_markup=keyboard)

# --- САМАЯ ПРОСТАЯ ВЫДАЧА (БЕЗ ФОРМАТИРОВАНИЯ) ---
@dp.message(F.text == "🛒 Купить аккаунт")
async def buy_account(message: types.Message):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow('''
                DELETE FROM accounts 
                WHERE id = (SELECT id FROM accounts ORDER BY id ASC LIMIT 1 FOR UPDATE SKIP LOCKED) 
                RETURNING data
            ''')
            
            if row:
                # ОТПРАВЛЯЕМ ПРОСТО ТЕКСТ. БЕЗ ПАРАМЕТРОВ.
                await message.answer(f"Твой товар:\n{row['data']}")
            else:
                await message.answer("Товар закончился.")

@dp.message(F.text == "📊 Наличие")
async def check_stock(message: types.Message):
    pool = await get_db_pool()
    count = await pool.fetchval("SELECT COUNT(*) FROM accounts")
    await message.answer(f"В наличии: {count} шт.")

@dp.message(F.text == "➕ Добавить базу")
async def admin_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    await state.set_state(AdminStates.adding_accounts)
    await message.answer("Кидай список.")

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
    await message.answer(f"Добавлено: {added_count}")

async def main():
    logging.basicConfig(level=logging.INFO)
    await get_db_pool()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
