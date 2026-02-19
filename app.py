import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# --- НАСТРОЙКИ СТРАНИЦЫ ---
st.set_page_config(page_title="Магия Контента", page_icon="🔮", layout="wide")
st.title("🔮 Мой Идеальный Автопостинг")

# --- 1. ПРОВЕРКИ И БАЗА ДАННЫХ ---
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в настройках Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel"  # Твой канал 

# Инициализируем бота ОДИН раз (чтобы не было утечек памяти)
if 'bot' not in st.session_state:
    st.session_state.bot = Bot(token=token)

# Подключение к базе
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# --- 2. ВЕЧНЫЙ ДВИГАТЕЛЬ (ОПТИМИЗИРОВАННЫЙ) ---
async def check_and_send():
    # Твоя правка: берем текущее время + 2 часа для коррекции
    now = datetime.now() + timedelta(hours=2) 
    now_key = now.strftime("%Y-%m-%d %H:%M")
    
    # Твоя правка: точное сравнение через склейку даты и времени
    c.execute("""
        SELECT id, text FROM posts 
        WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
    """, (now_key,))
    
    pending = c.fetchall()
    for p_id, txt in pending:
        try:
            # Используем глобального бота БЕЗ постоянного закрытия сессии
            await st.session_state.bot.send_message(chat_id=chat_id, text=txt)
            c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            conn.commit()
        except Exception as e:
            # Если что-то пошло не так, записываем ошибку в статус
            error_message = f"❌ Ошибка: {str(e)}"
            c.execute("UPDATE posts SET status = ? WHERE id = ?", (error_message, p_id))
            conn.commit()

# Запуск планировщика (раз в минуту)
if 'scheduler_started' not in st.session_state:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_send, 'interval', minutes=1)
    scheduler.start()
    st.session_state.scheduler_started = True

# --- 3. ИНТЕРФЕЙС (ЛЕВАЯ И ПРАВАЯ КОЛОНКИ) ---
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    msg = st.text_area("Текст твоего послания:", height=200)
    d = st.date_input("Выбери день")
    t = st.time_input("Время (точно до минуты)", step=60) # Твоя просьба про шаг в 1 мин
    
    if st.button("✨ Запланировать"):
        if msg:
            c.execute("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (msg, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.success("Пост успешно добавлен!")
            st.rerun()
        else:
            st.warning("Сначала введи текст!")

with col_right:
    st.subheader("📅 Календарь публикаций")
    
    # Готовим данные для сетки календаря
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = []
    for p in all_p:
        # Цвет: зеленый (ок), красный (ошибка), оранжевый (ждет)
        if "✅" in p[3]: color = "#28a745"
        elif "❌" in p[3]: color = "#dc3545"
        else: color = "#FFA500"
        
        events.append({
            "title": f"{p[2]} | {p[3]}",
            "start": p[1],
            "color": color
        })
    
    calendar(events=events, options={"headerToolbar": {"left": "prev,next", "center": "title", "right": "today"}, "initialView": "dayGridMonth"})

# --- 4. УПРАВЛЕНИЕ И УДАЛЕНИЕ ---
st.divider()
st.subheader("🗑️ Управление очередью")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC, time DESC").fetchall()

if not rows:
    st.info("Тут будут твои запланированные посты.")
else:
    for r in rows:
        c1, c2 = st.columns([5, 1])
        with c1:
            status_style = f":red[{r[4]}]" if "❌" in r[4] else f"**{r[4]}**"
            st.write(f"📌 {r[1]} в {r[2]} — {status_style}")
            st.caption(f"{r[3][:100]}...")
        with c2:
            if st.button("❌", key=f"del_{r[0]}"):
                c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
                conn.commit()
                st.rerun()
