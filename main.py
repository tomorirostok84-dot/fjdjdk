import logging
import asyncio
import json
import os
import uuid
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# --- НАСТРОЙКИ ---
API_TOKEN = '8125972892:AAEsUWz2s1t3dSJCxWpUeiaLzG6VTpvJHjg'
OWNER_ID = 8777986259
DB_FILE = 'data.json'

logging.basicConfig(level=logging.INFO)

def load_data():
    default_data = {
        "admins": [OWNER_ID], 
        "tokens": {}, 
        "stats": {"v_count": 0, "s_count": 0, "v_list": [], "s_list": []}
    }
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                d = json.load(f)
                # Проверка наличия всех ключей статистики
                if "stats" not in d: d["stats"] = default_data["stats"]
                for key in ["v_count", "s_count", "v_list", "s_list"]:
                    if key not in d["stats"]:
                        d["stats"][key] = default_data["stats"][key]
                return d
        except Exception as e:
            logging.error(f"Ошибка загрузки БД: {e}")
    return default_data

def save_data(d):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=4)

data = load_data()
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

class States(StatesGroup):
    add_admin = State()
    add_token = State()

def main_kb(uid):
    kb_list = [[KeyboardButton(text="📋 Список токенов")], [KeyboardButton(text="📊 Статистика")]]
    if uid == OWNER_ID or uid in data.get("admins", []):
        kb_list.append([KeyboardButton(text="⚙️ Админка")])
    return ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)

# --- ОБРАБОТКА ---

@dp.message(Command("start"))
async def start(m: types.Message):
    await m.answer("🚀 Бот готов к работе!", reply_markup=main_kb(m.from_user.id))

@dp.message(F.text == "📊 Статистика")
@dp.message(Command("stats"))
async def show_stats(m: types.Message):
    st = data.get("stats", {"v_count": 0, "s_count": 0, "v_list": [], "s_list": []})
    v_count = st.get("v_count", 0)
    s_count = st.get("s_count", 0)
    
    text = f"📈 **ОБЩАЯ СТАТИСТИКА**\n\n✅ Встало: `{v_count}`\n🧨 Слетел: `{s_count}`\n"
    
    # Детализация для админов
    if m.from_user.id == OWNER_ID or m.from_user.id in data.get("admins", []):
        text += "\n📄 **ПОСЛЕДНИЕ СОБЫТИЯ:**\n"
        
        v_list = st.get("v_list", [])
        if v_list:
            text += f"\n🟢 **Встали:**\n— " + "\n— ".join(v_list[-10:]) + "\n"
        
        s_list = st.get("s_list", [])
        if s_list:
            text += f"\n🔴 **Слетели:**\n— " + "\n— ".join(s_list[-10:]) + "\n"
            
    await m.answer(text, parse_mode="Markdown")

@dp.message(F.text == "⚙️ Админка")
async def admin_menu(m: types.Message):
    if m.from_user.id == OWNER_ID or m.from_user.id in data.get("admins", []):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Добавить админа", callback_data="add_admin")],
            [InlineKeyboardButton(text="📥 Добавить токен", callback_data="add_token")]
        ])
        await m.answer("🛠 **МЕНЮ АДМИНИСТРАТОРА**", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "add_admin")
async def call_add_admin(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("⌨️ Введите ID нового админа:")
    await state.set_state(States.add_admin)

@dp.message(States.add_admin)
async def process_add_admin(m: types.Message, state: FSMContext):
    if m.text.isdigit():
        new_id = int(m.text)
        if new_id not in data["admins"]:
            data["admins"].append(new_id)
            save_data(data)
        await m.answer(f"✅ ID {new_id} добавлен в админы!")
    else:
        await m.answer("❌ Введи числовой ID!")
    await state.clear()

@dp.callback_query(F.data == "add_token")
async def call_add_token(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("📁 Отправь файл (токен):")
    await state.set_state(States.add_token)

@dp.message(States.add_token, F.document)
async def process_token(m: types.Message, state: FSMContext):
    tid = str(uuid.uuid4())[:8]
    name = m.caption if m.caption else m.document.file_name
    data["tokens"][tid] = {"name": name, "file_id": m.document.file_id}
    save_data(data)
    await m.answer(f"💾 Токен '{name}' добавлен!")
    await state.clear()

@dp.message(F.text == "📋 Список токенов")
@dp.message(Command("token"))
async def token_list(m: types.Message):
    if not data.get("tokens"):
        return await m.answer("📭 Список токенов пуст.")
    
    btns = []
    for tid, info in data["tokens"].items():
        btns.append([InlineKeyboardButton(text=f"📄 {info['name']}", callback_data=f"view_{tid}")])
    
    await m.answer("📋 **Выберите токен:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("view_"))
async def view_token(c: types.CallbackQuery):
    tid = c.data.split("_")[1]
    token_info = data.get("tokens", {}).get(tid)
    
    if token_info:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Встал", callback_data=f"done_v_{tid}"),
             InlineKeyboardButton(text="🧨 Слёт", callback_data=f"done_s_{tid}")]
        ])
        await c.message.answer_document(token_info['file_id'], caption=f"🎫 Токен: {token_info['name']}", reply_markup=kb)
        await c.answer()
    else:
        await c.answer("❌ Токен не найден или уже удален.", show_alert=True)

@dp.callback_query(F.data.startswith("done_"))
async def done_token(c: types.CallbackQuery):
    parts = c.data.split("_")
    status_code = parts[1]
    tid = parts[2]
    
    if tid in data.get("tokens", {}):
        token_info = data["tokens"].pop(tid)
        name = token_info['name']
        
        if status_code == "v":
            data["stats"]["v_count"] += 1
            data["stats"]["v_list"].append(name)
            status_text = "✅ ВСТАЛ"
        else:
            data["stats"]["s_count"] += 1
            data["stats"]["s_list"].append(name)
            status_text = "🧨 СЛЁТ"
            
        save_data(data)
        await c.message.edit_caption(caption=f"🏁 **{name}**\nСтатус: {status_text}\n\n🗑 Удален из активных.")
    else:
        await c.answer("⚠️ Уже обработан другим пользователем.", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
  
