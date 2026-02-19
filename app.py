import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# Настройки страницы
st.set_page_config(page_title="Нумерология Путеводитель", page_icon="🔮", layout="wide")
st.title("🔮 Пульт управления: Нумерология")

# --- 1. ПРОВЕРКИ И БАЗА ---
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" # Твой тестовый канал [cite: 1, 2026-01-23]

# Инициализируем бота ОДИН раз (как ты и просила, чтобы не "текло")
if 'bot' not in st.session_state:
    st.session_state.bot = Bot(token=token)

conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# --- 2. ВЕЧНЫЙ ДВИГАТЕЛЬ (ОПТИМИЗИРОВАННЫЙ) ---
async def check_and_send():
    now = datetime.now() + timedelta(hours=2) 
    now_key = now.strftime("%Y-%m-%d %H:%M")
    
    # Твоя логика: склейка даты и времени для точного сравнения
    c.execute("""
        SELECT id, text FROM posts 
        WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
    """, (now_key,))
    
    pending = c.fetchall()
    for p_id, txt in pending:
        try:
            # Отправляем с поддержкой Markdown (жирный, курсив)
            await st.session_state.bot.send_message(chat_id=chat_id, text=txt, parse_mode="Markdown")
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            conn.commit()
        except Exception as e:
            # Твоя правка: записываем ошибку в базу, чтобы не "глотать" её
            error_message = f"❌ Ошибка: {str(e)}"
            c.execute("UPDATE posts SET status = ? WHERE id = ?", (error_message, p_id))
            conn.commit()

if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler_started = True

# --- 3. ИНТЕРФЕЙС (КАК В PUBLER) ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    msg = st.text_area("Текст поста (используй **для жирного**):", height=300, 
                       placeholder="Сегодня по нумерологии день цифры 7...")
    
    d = st.date_input("Дата публикации")
    t = st.time_input("Точное время (шаг 1 мин)", step=60)
    
    if st.button("✨ Запланировать в @numerologiputivoditel"):
        if msg:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (msg, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.success("Пост успешно добавлен в очередь!")
            st.rerun()

with col_right:
    st.subheader("📅 Сетка календаря")
    
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = []
    for p in all_p:
        # Цвет: зеленый (ок), красный (ошибка), оранжевый (ждем)
        if "✅" in p[3]: color = "#28a745"
        elif "❌" in p[3]: color = "#dc3545"
        else: color = "#FFA500"
        
        events.append({
            "title": f"{p[2]} | {p[3]}",
            "start": p[1],
            "color": color
        })
    
    calendar(events=events, options={"headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth"}})

# --- 4. УДАЛЕНИЕ ---
st.divider()
st.subheader("🗑️ Управление постами")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC, time DESC").fetchall()

for r in rows:
    c1, c2 = st.columns([5, 1])
    with c1:
        # Выделяем ошибки красным цветом
        status_display = f":red[{r[4]}]" if "❌" in r[4] else f"**{r[4]}**"
        st.write(f"📌 {r[1]} в {r[2]} — {status_display}")
        st.caption(f"{r[3][:100]}...")
    with c2:
        if st.button("❌", key=f"del_{r[0]}"):
            c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
            conn.commit()
            st.rerun()
