import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

st.set_page_config(page_title="Магия Контента", page_icon="🔮", layout="wide")
st.title("🔮 Мой Идеальный Автопостинг")

# --- 1. ПРОВЕРКИ И БАЗА ---
token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" 

conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# --- 2. ВЕЧНЫЙ ДВИГАТЕЛЬ (ИСПРАВЛЕННЫЙ) ---
async def check_and_send():
    now = datetime.now() + timedelta(hours=2) 
    now_key = now.strftime("%Y-%m-%d %H:%M")
    
    # Твоя правка: склеиваем дату и время для точного поиска
    c.execute("""
        SELECT id, text FROM posts 
        WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
    """, (now_key,))
    
    pending = c.fetchall()
    for p_id, txt in pending:
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
    msg = st.text_area("Текст послания:", height=200)
    d = st.date_input("День")
    t = st.time_input("Время (шаг 1 мин)", step=60)
    
    if st.button("✨ Запланировать"):
        if msg:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (msg, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.rerun()

with col_right:
    st.subheader("📅 Твой календарь")
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = []
    for p in all_p:
        color = "#FFA500" if "Ожидает" in p[3] else "#28a745"
        events.append({"title": f"{p[2]} | {p[3]}", "start": p[1], "color": color})
    
    calendar(events=events, options={"initialView": "dayGridMonth", "selectable": True})

# --- 4. УДАЛЕНИЕ ---
st.divider()
st.subheader("🗑️ Управление очередью")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC").fetchall()
for r in rows:
    c1, c2 = st.columns([5, 1])
    c1.write(f"📌 {r[1]} {r[2]} — **{r[4]}**\n{r[3][:60]}...")
    if c2.button("❌", key=f"del_{r[0]}"):
        c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
        conn.commit()
        st.rerun()
