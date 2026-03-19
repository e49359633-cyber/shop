import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
import asyncpg
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# --- НАСТРОЙКИ ---
API_TOKEN = '8717755678:AAFxBTzyDghHPLYOstlvkeNsUjgBStP3KHg'
# Список ID всех администраторов
ADMIN_IDS = [8209617821, 8384467554] 

# Твоя строка подключения к PostgreSQL на pghost.ru
DATABASE_URL = 'postgresql://bothost_db_29f14895d3aa:tbdVGmS3JoNrcauznAFgzNTJgefFJE3xE33flLLZY5M@node1.pghost.ru:32854/bothost_db_29f14895d3aa'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния для админ-панели
class AdminStates(StatesGroup):
    adding_accounts = State()

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
async def init_db():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        # Создаем таблицу, если ее нет. 'data' UNIQUE — защита от дублей.
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                data TEXT UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await conn.close()
        logging.info("✅ Успешное подключение к PostgreSQL на node1.pghost.ru")
    except Exception as e:
        logging.error(f"❌ Ошибка подключения к БД: {e}")

# --- ОБРАБОТЧИКИ (HANDLERS) ---

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    # Главное меню
    kb = [
        [types.KeyboardButton(text="🛒 Купить аккаунт")],
        [types.KeyboardButton(text="📊 Наличие")]
    ]
    
    # Кнопка админки появляется только у тех, кто в списке ADMIN_IDS
    if message.from_user.id in ADMIN_IDS:
        kb.append([types.KeyboardButton(text="➕ Добавить базу")])
    
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer(
        "👋 Добро пожаловать в сервис продажи почт!\n\n"
        "Нажми кнопку ниже, чтобы купить рабочий аккаунт.",
        reply_markup=keyboard
    )

# ЛОГИКА ПОКУПКИ (СРАЗУ УДАЛЯЕТ ИЗ БАЗЫ)
@dp.message(F.text == "🛒 Купить аккаунт")
async def buy_account(message: types.Message):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # PostgreSQL позволяет атомарно удалить и вернуть строку за один запрос
        row = await conn.fetchrow('''
            DELETE FROM accounts 
            WHERE id = (SELECT id FROM accounts ORDER BY id ASC LIMIT 1) 
            RETURNING data
        ''')
        
        if row:
            await message.answer(
                f"✅ **Ваш аккаунт куплен!**\n\n"
                f"Данные: `{row['data']}`\n\n"
                f"⚠️ *Внимание: данные удалены из нашей базы. Обязательно сохраните их!*", 
                parse_mode="MarkdownV2"
            )
        else:
            await message.answer("❌ Извините, товар закончился. Мы скоро добавим новые почты!")
    finally:
        await conn.close()

# ПРОВЕРКА НАЛИЧИЯ
@dp.message(F.text == "📊 Наличие")
async def check_stock(message: types.Message):
    conn = await asyncpg.connect(DATABASE_URL)
    count = await conn.fetchval("SELECT COUNT(*) FROM accounts")
    await conn.close()
    await message.answer(f"📦 Сейчас в наличии: **{count} шт.**", parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ (ТОЛЬКО ДЛЯ ADMIN_IDS) ---

@dp.message(F.text == "➕ Добавить базу")
async def admin_add(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await state.set_state(AdminStates.adding_accounts)
    await message.answer(
        "📥 Пришли список аккаунтов.\n"
        "Каждый аккаунт с новой строки. Формат:\n`login:password` или `login:pass:recovery`",
        parse_mode="Markdown"
    )

@dp.message(AdminStates.adding_accounts)
async def process_adding(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    accounts = message.text.split('\n')
    added_count = 0
    conn = await asyncpg.connect(DATABASE_URL)
    
    for acc in accounts:
        clean_acc = acc.strip()
        if clean_acc:
            try:
                # Вставляем данные, если такая строка уже есть — ничего не делаем
                await conn.execute('''
                    INSERT INTO accounts (data) VALUES ($1) 
                    ON CONFLICT (data) DO NOTHING
                ''', clean_acc)
                added_count += 1
            except Exception as e:
                logging.error(f"Ошибка при вставке строки: {e}")
    
    await conn.close()
    await state.clear()
    await message.answer(f"✅ Успешно добавлено: **{added_count}** аккаунтов.", parse_mode="Markdown")

# --- ЗАПУСК БОТА ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот выключен")
