import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# 1. Настройка страницы
st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮", layout="wide")
st.title("🔮 Мой Автопостинг")

# 2. Проверка токена (сначала проверяем, потом берем — как ты и говорила!)
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" 

# 3. Инициализация бота ОДИН раз (чтобы не "текло")
if 'bot' not in st.session_state:
    st.session_state.bot = Bot(token=token)

# 4. База данных (добавляем ID, чтобы работало удаление)
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# 5. Вечный двигатель (Исправленная логика времени)
async def check_and_send():
    # Твоя поправка времени
    now = datetime.now() + timedelta(hours=2) 
    now_key = now.strftime("%Y-%m-%d %H:%M")
    
    # Твоя логика: склейка даты и времени для поиска
    c.execute("""
        SELECT id, text FROM posts 
        WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
    """, (now_key,))
    
    pending = c.fetchall()
    for p_id, txt in pending:
        try:
            # Отправляем через глобального бота
            await st.session_state.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            conn.commit()
        except Exception as e:
            # Не "глотаем" ошибку, а пишем в базу
            c.execute("UPDATE posts SET status = ? WHERE id = ?", (f"❌ Ошибка: {str(e)}", p_id))
            conn.commit()

# Запуск планировщика
if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler_started = True

# 6. Интерфейс (Форма + Календарь)
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    message = st.text_area("Текст поста:", height=200)
    d = st.date_input("День")
    t = st.time_input("Время", step=60) # Шаг 1 минута
    
    if st.button("✨ Запланировать"):
        if message:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.rerun()

with col_right:
    st.subheader("📅 Сетка календаря")
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = []
    for p in all_p:
        color = "#28a745" if "✅" in p[3] else ("#dc3545" if "❌" in p[3] else "#FFA500")
        events.append({"title": f"{p[2]}", "start": p[1], "color": color})
    
    calendar(events=events, options={"initialView": "dayGridMonth"})

# 7. Список для удаления (теперь с ID!)
st.divider()
st.subheader("🗑️ Управление постами")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC").fetchall()
for r in rows:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.write(f"📌 {r[1]} {r[2]} — {r[4]}")
    with c2:
        if st.button("❌", key=f"del_{r[0]}"):
            c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
            conn.commit()
            st.rerun()
