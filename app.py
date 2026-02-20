import streamlit as st
from aiogram import Bot
from datetime import datetime
import sqlite3
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from streamlit_calendar import calendar
from zoneinfo import ZoneInfo

# 1. ТЕМНЫЙ МАГИЧЕСКИЙ ИНТЕРФЕЙС
st.set_page_config(page_title="Magic Scheduler", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(rgba(0, 0, 0, 0.7), rgba(0, 0, 0, 0.7)), 
                    url("https://images.unsplash.com/photo-1515037028865-0a2a82603f7c?q=80&w=2000");
        background-size: cover;
        background-attachment: fixed;
    }
    
    .main .block-container {
        background-color: rgba(20, 20, 20, 0.6); 
        backdrop-filter: blur(15px);
        border-radius: 30px;
        padding: 40px;
        border: 1px solid rgba(241, 196, 15, 0.3);
        box-shadow: 0 0 20px rgba(0,0,0,0.5);
    }

    h1, h2, h3, label, p {
        color: #f1c40f !important; /* Золотой цвет */
        text-shadow: 1px 1px 3px #000;
    }

    .stButton>button {
        background: linear-gradient(45deg, #f1c40f, #d4af37) !important;
        color: black !important;
        font-weight: bold !important;
        border-radius: 15px !important;
        border: none !important;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 15px #f1c40f;
    }
    
    /* Стилизация полей ввода: делаем текст черным */
    .stTextArea textarea, .stTextInput input {
        background-color: rgba(255, 255, 255, 0.9) !important; /* Почти белый фон */
        color: #000000 !important; /* ЧЕРНЫЙ текст */
        border: 2px solid #f1c40f !important; /* Золотая рамка */
        border-radius: 10px !important;
    }

    /* Состояние при вводе (фокус) */
    .stTextArea textarea:focus, .stTextInput input:focus {
        background-color: #ffffff !important; /* Чисто белый фон при печати */
        color: #000000 !important; /* ЧЕРНЫЙ текст */
        box-shadow: 0 0 15px rgba(241, 196, 15, 0.6) !important;
        outline: none !important;
    }
    
    /* Цвет текста-подсказки (placeholder) сделаем серым, чтобы не сливался */
    .stTextArea textarea::placeholder, .stTextInput input::placeholder {
        color: #666666 !important;
    }    }
    </style>
    """, unsafe_allow_html=True)

# 2. ФУНКЦИИ БАЗЫ ДАННЫХ
def run_query(query, params=(), fetch=False, return_rowcount=False):
    with sqlite3.connect("scheduler.db", check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch: return c.fetchall()
        conn.commit()
        if return_rowcount: return c.rowcount

# Создаем таблицу сразу со всеми полями для медиа
run_query("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT, 
    date TEXT, 
    time TEXT, 
    status TEXT, 
    last_error TEXT,
    media_blob BLOB, 
    media_type TEXT
)
""")

# 3. ЛОГИКА ОТПРАВКИ (МЕДИА + ТЕКСТ)
async def check_and_send():
    if "TELEGRAM_TOKEN" not in st.secrets: return
    
    token = st.secrets["TELEGRAM_TOKEN"]
    chat_id = "@numerologiputivoditel"
    now_key = datetime.now(ZoneInfo("Europe/Zaporozhye")).strftime("%Y-%m-%d %H:%M")
    
    bot = Bot(token=token)
    try:
        rows = run_query("""
            SELECT id, text, media_blob, media_type FROM posts 
            WHERE (date || ' ' || time) <= ? AND status = 'Ожидает' 
            ORDER BY date ASC, time ASC LIMIT 1
        """, (now_key,), fetch=True)
        
        if rows:
            p_id, txt, blob, m_type = rows[0]
            if run_query("UPDATE posts SET status='🚚 Отправляется' WHERE id=? AND status='Ожидает'", (p_id,), return_rowcount=True) == 1:
                try:
                    if blob:
                        from aiogram.types import BufferedInputFile
                        file = BufferedInputFile(blob, filename=f"file.{m_type}")
                        if m_type in ['jpg', 'png', 'jpeg']:
                            await bot.send_photo(chat_id=chat_id, photo=file, caption=txt)
                        else:
                            await bot.send_video(chat_id=chat_id, video=file, caption=txt)
                    else:
                        await bot.send_message(chat_id=chat_id, text=txt)
                    run_query("UPDATE posts SET status='✅ Отправлено' WHERE id=?", (p_id,))
                except Exception as e:
                    run_query("UPDATE posts SET status='failed', last_error=? WHERE id=?", (str(e), p_id))
    finally:
        await bot.session.close()

@st.cache_resource
def start_scheduler():
    s = BackgroundScheduler(timezone="Europe/Zaporozhye")
    s.add_job(lambda: asyncio.run(check_and_send()), "interval", minutes=1)
    s.start()
    return s

start_scheduler()

# 4. ИНТЕРФЕЙС ПРИЛОЖЕНИЯ
st.title("🔮 Мой идеальный автопостинг")
st.write("Панель управления контентом")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 Создать Публикацию")
    msg = st.text_area("Текст поста:", height=200, placeholder="Введите текст...")
    
    # Загрузка фото/видео
    up_file = st.file_uploader("Прикрепить медиа (фото или видео)", type=["jpg", "png", "jpeg", "mp4"])
    
    d = st.date_input("Дата публикации")
    t = st.time_input("Время публикации", step=60)
    
    if st.button("✨ Забросить в будущее"):
        if msg.strip() or up_file:
            m_blob = up_file.read() if up_file else None
            m_type = up_file.name.split('.')[-1].lower() if up_file else None
            
            run_query("""
                INSERT INTO posts (text, date, time, status, media_blob, media_type) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (msg.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает", m_blob, m_type))
            st.success("Пост успешно запланирован!")
            st.rerun()

with col2:
    st.subheader("📅 Календарь событий")
    all_p = run_query("SELECT date, time, status FROM posts", fetch=True)
    
    events = []
    for p in all_p:
        # Цвета для маленьких маркеров
        if p[2] == "✅ Отправлено":
            dot_color = "#28a745" # Зеленая точка
        elif p[2] == "failed":
            dot_color = "#dc3545" # Красная точка
        else:
            dot_color = "#f1c40f" # Золотая точка для планов
            
        events.append({
            "title": f"{p[1]} | {p[2]}", 
            "start": f"{p[0]}T{p[1]}:00",
            "display": "block", # Делает событие компактной полоской, а не фоном ячейки
            "backgroundColor": dot_color,
            "borderColor": dot_color,
            "textColor": "white" if p[2] != "Ожидает" else "black"
        })
    
    calendar(
        events=events,
        options={
            "headerToolbar": {
                "left": "prev,next today",
                "center": "title",
                "right": "dayGridMonth,timeGridWeek,timeGridDay",
            },
            "initialView": "dayGridMonth",
            "eventDisplay": "block", # Важно: события отображаются как блоки-полоски
            "dayMaxEvents": True,    # Если постов много, они спрячутся под кнопку "+ еще"
        }
    )               
  # УПРАВЛЕНИЕ АРХИВОМ
st.divider()
if st.button("🗑️ Очистить архив"):
    run_query("DELETE FROM posts WHERE status = '✅ Отправлено'")
    st.rerun()

# Список текущих постов
st.subheader("📜 Текущие планы")
rows = run_query("SELECT id, date, time, status, text FROM posts ORDER BY date ASC, time ASC", fetch=True)
for r in rows:
    with st.expander(f"{r[1]} {r[2]} — {r[3]}"):
        st.write(r[4])
        if st.button("Удалить", key=f"del_{r[0]}"):
            run_query("DELETE FROM posts WHERE id=?", (r[0],))
            st.rerun()
