import streamlit as st
from aiogram import Bot
from datetime import datetime
import sqlite3
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from streamlit_calendar import calendar
from zoneinfo import ZoneInfo

# Та самая прямая ссылка на твой выбор из Pinterest
BG_URL = "https://i.pinimg.com/originals/74/4d/9d/744d9d8385750896025281781619426d.jpg"

st.set_page_config(page_title="Magic Post", page_icon="✨", layout="wide")

# Дизайн: "Зефирный" фон и светлые карточки
st.markdown(f"""
    <style>
    .stApp {{
        background: url("{BG_URL}");
        background-size: cover;
        background-attachment: fixed;
    }}
    .main .block-container {{
        background-color: rgba(255, 255, 255, 0.75); 
        backdrop-filter: blur(8px);
        border-radius: 25px;
        padding: 35px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }}
    h1, h2, h3, label {{ color: #333 !important; font-weight: 600; }}
    .stButton>button {{
        background: linear-gradient(90deg, #ff9a9e 0%, #fad0c4 100%) !important;
        border: none !important; color: white !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# РАБОТА С БД
def run_query(query, params=(), fetch=False, return_rowcount=False):
    with sqlite3.connect("scheduler.db", check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch: return c.fetchall()
        conn.commit()
        if return_rowcount: return c.rowcount

# Таблица с поддержкой медиа
run_query("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT, date TEXT, time TEXT, 
    status TEXT, last_error TEXT,
    media_blob BLOB, media_type TEXT
)
""")

# ФОНОВАЯ ОТПРАВКА
async def check_and_send():
    token = st.secrets["TELEGRAM_TOKEN"]
    chat_id = "@numerologiputivoditel"
    now_key = datetime.now(ZoneInfo("Europe/Zaporozhye")).strftime("%Y-%m-%d %H:%M")
    
    bot = Bot(token=token)
    try:
        rows = run_query("SELECT id, text, media_blob, media_type FROM posts WHERE (date || ' ' || time) <= ? AND status = 'Ожидает' LIMIT 1", (now_key,), fetch=True)
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

# ИНТЕРФЕЙС
st.title("🔮 Путеводитель Нумеролога: Автопост")
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 Создать Пост")
    msg = st.text_area("Текст поста:", height=150)
    up_file = st.file_uploader("Добавить фото или видео (mp4)", type=["jpg", "png", "jpeg", "mp4"])
    d = st.date_input("Дата")
    t = st.time_input("Время", step=60)
    
    if st.button("✨ Запланировать"):
        m_blob = up_file.read() if up_file else None
        m_type = up_file.name.split('.')[-1].lower() if up_file else None
        run_query("INSERT INTO posts (text, date, time, status, media_blob, media_type) VALUES (?, ?, ?, ?, ?, ?)",
                  (msg.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает", m_blob, m_type))
        st.balloons()
        st.rerun()

with col2:
    st.subheader("📅 Календарь")
    all_p = run_query("SELECT date, time, status FROM posts", fetch=True)
    events = [{"title": f"{p[1]} | {p[2]}", "start": f"{p[0]}T{p[1]}:00"} for p in all_p]
    calendar(events=events)

st.divider()
if st.button("🗑️ Очистить историю"):
    run_query("DELETE FROM posts WHERE status = '✅ Отправлено'")
    st.rerun()
