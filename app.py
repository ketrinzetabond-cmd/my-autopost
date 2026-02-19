import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# Настройка страницы
st.set_page_config(page_title="Магия Контента", page_icon="🔮", layout="wide")
st.title("🔮 Мой Идеальный Автопостинг")

# --- 1. ПРОВЕРКИ И БАЗА ДАННЫХ ---
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" # Твой канал [cite: 1]

conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# --- 2. ВЕЧНЫЙ ДВИГАТЕЛЬ (АВТОПОСТИНГ) ---
async def check_and_send():
    now = datetime.now() + timedelta(hours=2) # Твоя коррекция времени 
    curr_d, curr_t = now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
    
    c.execute("SELECT id, text FROM posts WHERE date <= ? AND time <= ? AND status = 'Ожидает'", (curr_d, curr_t))
    pending_posts = c.fetchall()
    
    for p_id, txt in pending_posts:
        try:
            bot = Bot(token=token)
            await bot.send_message(chat_id=chat_id, text=txt)
            await bot.session.close()
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            conn.commit()
        except: pass

if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler_started = True

# --- 3. ИНТЕРФЕЙС (ДВЕ КОЛОНКИ) ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    message = st.text_area("Текст твоего послания:", height=200)
    d = st.date_input("Выбери день")
    t = st.time_input("Время (точно до минуты)", step=60) # Твой шаг в 1 мин
    
    if st.button("✨ Запланировать в календарь"):
        if message:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.success("Магия сработала! Пост в календаре.")
            st.rerun()

with col_right:
    st.subheader("📅 Твой календарь")
    
    # Готовим посты для отображения в сетке
    all_posts = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    calendar_events = []
    for p in all_posts:
        # Оранжевый - ждет, Зеленый - отправлен
        color = "#FFA500" if "Ожидает" in p[3] else "#28a745"
        calendar_events.append({
            "title": f"{p[2]} | {p[3]}",
            "start": p[1],
            "color": color
        })
    
    calendar_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek"},
        "initialView": "dayGridMonth",
        "selectable": True,
    }
    
    calendar(events=calendar_events, options=calendar_options)

# --- 4. СПИСОК ДЛЯ УДАЛЕНИЯ ---
st.divider()
st.subheader("🗑️ Управление очередью")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC").fetchall()

for r in rows:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.write(f"📌 {r[1]} в {r[2]} — **{r[4]}**")
        st.caption(f"{r[3][:100]}...")
    with c2:
        if st.button("❌", key=f"del_{r[0]}"):
            c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
            conn.commit()
            st.rerun()
