import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# 1. Настройки страницы
st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮", layout="wide")
st.title("🔮 Мой Автопостинг (Рабочая версия)")

# 2. Проверка токена
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" 

# Инициализируем бота ОДИН раз (твоя наводка про утечки!)
if 'bot' not in st.session_state:
    st.session_state.bot = Bot(token=token)

# 3. База данных (с ID для удаления)
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# 4. "Вечный двигатель" (APScheduler) - работает даже если вкладка закрыта
async def check_and_send():
    now = datetime.now() + timedelta(hours=2) # Твоя коррекция времени
    now_key = now.strftime("%Y-%m-%d %H:%M")
    
    # Ищем посты, время которых наступило (твоя логика склейки!)
    c.execute("SELECT id, text FROM posts WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'", (now_key,))
    pending = c.fetchall()
    
    for p_id, txt in pending:
        try:
            await st.session_state.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            conn.commit()
        except Exception as e:
            # Твоя правка: не "глотаем" ошибку, а пишем её в базу
            c.execute("UPDATE posts SET status = ? WHERE id = ?", (f"❌ Ошибка: {str(e)}", p_id))
            conn.commit()

if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1) # Проверка каждую минуту
    scheduler.start()
    st.session_state.scheduler_started = True

# 5. Интерфейс (Форма + Календарь)
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    message = st.text_area("Текст:", height=200)
    d = st.date_input("День")
    t = st.time_input("Время", step=60) # Шаг в 1 минуту по твоей просьбе
    
    if st.button("✨ Запланировать"):
        if message:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.success("Добавлено!")
            st.rerun()

with col_right:
    st.subheader("📅 Календарь")
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = [{"title": f"{p[2]} | {p[3]}", "start": p[1], "color": "#28a745" if "✅" in p[3] else "#FFA500"} for p in all_p]
    calendar(events=events, options={"initialView": "dayGridMonth"})

# 6. Список для удаления
st.divider()
st.subheader("🗑️ Управление")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC").fetchall()
for r in rows:
    c1, c2 = st.columns([5, 1])
    c1.write(f"📌 {r[1]} {r[2]} — {r[4]}")
    if c2.button("❌", key=f"del_{r[0]}"):
        c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
        conn.commit()
        st.rerun()
