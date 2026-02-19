import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler

st.set_page_config(page_title="Магия Контента", page_icon="🔮")
st.title("🔮 Мой Автопостинг")

# 1. Проверка токена (берем из Сейфа)
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в настройках Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel" 

# 2. База данных
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# 3. Наш "вечный двигатель"
async def check_and_send():
    now = datetime.now() + timedelta(hours=2)
    current_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")
    
    c.execute("SELECT id, text FROM posts WHERE date <= ? AND time <= ? AND status = 'Ожидает'", 
              (current_date, current_time))
    pending_posts = c.fetchall()
    
    for post_id, text in pending_posts:
        try:
            bot = Bot(token=token)
            await bot.send_message(chat_id=chat_id, text=text)
            await bot.session.close()
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (post_id,))
            conn.commit()
        except Exception:
            pass

if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler_started = True

# 4. Интерфейс
message = st.text_area("Текст твоего послания:")
col1, col2 = st.columns(2)
with col1:
    d = st.date_input("Выбери день")
with col2:
    t = st.time_input("Выбери время (шаг 1 мин)", step=60) 

if st.button("✨ Запланировать"):
    if message:
        c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                  (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
        conn.commit()
        st.success("Успешно! Пост в очереди.")
        st.rerun()
    else:
        st.warning("Сначала напиши текст!")

# 5. Пункт 2: Список постов с кнопкой удаления ❌
st.divider()
st.subheader("📅 Твой план публикаций")
all_posts = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC, time DESC").fetchall()

if not all_posts:
    st.write("Пока здесь пусто. Напиши свой первый пост!")
else:
    for p in all_posts:
        p_id, p_date, p_time, p_text, p_status = p
        col_info, col_del = st.columns([5, 1])
        
        with col_info:
            status_color = "green" if "✅" in p_status else "orange"
            st.write(f"📌 {p_date} в {p_time} — :{status_color}[{p_status}]")
            st.caption(f"{p_text[:100]}...")
        
        with col_del:
            if st.button("❌", key=f"del_{p_id}"):
                c.execute("DELETE FROM posts WHERE id = ?", (p_id,))
                conn.commit()
                st.rerun()
