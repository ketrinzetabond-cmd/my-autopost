import streamlit as st
from aiogram import Bot
from datetime import datetime
import logging
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

# ---------- ЛОГИ ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

# 1) НАСТРОЙКА СТРАНИЦЫ
st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮", layout="wide")
st.title("🔮 Мой Идеальный Автопостинг")

# 2) ПРОВЕРКА TOKEN
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден! Зайдите в Settings -> Secrets.")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel"

try:
    tz = ZoneInfo("Europe/Zaporozhye")
except Exception:
    tz = ZoneInfo("UTC")
    st.warning("Используется UTC часовой пояс.")

# 3) БЕЗОПАСНАЯ РАБОТА С БД
def run_query(query, params=(), fetch=False, return_rowcount=False):
    try:
        with sqlite3.connect("scheduler.db", check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(query, params)
            if fetch: return c.fetchall()
            conn.commit()
            if return_rowcount: return c.rowcount
    except Exception as e:
        logging.exception("DB error: %s", e)
        return [] if fetch else 0

# ИНИЦИАЛИЗАЦИЯ
run_query("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT, date TEXT, time TEXT, 
    status TEXT, last_error TEXT
)
""")

def color_for_status(stat: str) -> str:
    if not stat: return "#FFA500"
    if "✅" in stat: return "#28a745"
    if stat == "failed": return "#dc3545"
    if "🚚" in stat: return "#0dcaf0"
    if stat == "cancelled": return "#6c757d"
    return "#FFA500"

# 4) АВТОПОСТИНГ
async def check_and_send():
    now_key = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    bot = Bot(token=token)
    try:
        for _ in range(20):
            row = run_query("""
                SELECT id, text FROM posts 
                WHERE (date || ' ' || time) <= ? AND status = 'Ожидает' 
                ORDER BY date ASC, time ASC LIMIT 1
            """, (now_key,), fetch=True)
            if not row: break
            p_id, txt = row[0]
            if run_query("UPDATE posts SET status='🚚 Отправляется' WHERE id=? AND status='Ожидает'", (p_id,), return_rowcount=True) != 1:
                continue
            try:
                await bot.send_message(chat_id=chat_id, text=txt)
                run_query("UPDATE posts SET status='✅ Отправлено' WHERE id=?", (p_id,))
            except Exception as e:
                run_query("UPDATE posts SET status='failed', last_error=? WHERE id=?", (str(e), p_id))
    finally:
        await bot.session.close()

# 5) ПЛАНИРОВЩИК
@st.cache_resource
def start_scheduler():
    s = AsyncIOScheduler()
    s.add_job(check_and_send, "interval", minutes=1, max_instances=1, coalesce=True)
    s.start()
    return s

start_scheduler()

# 6) UI
col_left, col_right = st.columns([1, 2])
with col_left:
    st.subheader("📝 Новый пост")
    msg = st.text_area("Текст:", height=200)
    d = st.date_input("Дата")
    t = st.time_input("Время", step=60)
    if st.button("✨ Запланировать"):
        if msg.strip():
            run_query("INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)", 
                      (msg.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            st.rerun()

with col_right:
    st.subheader("📅 Календарь")
    all_p = run_query("SELECT text, date, time, status FROM posts", fetch=True)
    events = [{"title": f"{p[2]} | {p[3]}", "start": f"{p[1]}T{p[2]}:00", "color": color_for_status(p[3])} for p in all_p]
    calendar(events=events, options={"headerToolbar": {"right": "dayGridMonth,timeGridWeek"}, "initialView": "dayGridMonth"})

# 7) УПРАВЛЕНИЕ
st.divider()
st.subheader("🗑️ Управление")
rows = run_query("SELECT id, date, time, text, status, last_error FROM posts ORDER BY date DESC, time DESC", fetch=True)
for r in rows:
    c1, c2, c3 = st.columns([6, 2, 2])
    with c1:
        st.write(f"📌 {r[1]} {r[2]} — {r[4]}")
    with c2:
        if r[4] == "Ожидает" and st.button("🚫", key=f"can_{r[0]}"):
            run_query("UPDATE posts SET status='cancelled' WHERE id=?", (r[0],))
            st.rerun()
    with c3:
        if st.button("❌", key=f"del_{r[0]}"):
            run_query("DELETE FROM posts WHERE id=?", (r[0],))
            st.rerun()
