import streamlit as st
from aiogram import Bot
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# 1. НАСТРОЙКА СТРАНИЦЫ
st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮", layout="wide")
st.title("🔮 Мой Идеальный Автопостинг")

# 2. ПРОВЕРКА TOKЕN
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel"
tz = ZoneInfo("Europe/Zaporozhye")

# 3. ФУНКЦИЯ ДЛЯ БЕЗОПАСНОЙ РАБОТЫ С БД
def run_query(query, params=(), fetch=False, return_rowcount=False):
    with sqlite3.connect("scheduler.db", check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetch:
            return c.fetchall()
        conn.commit()
        if return_rowcount:
            return c.rowcount

# 4. ИНИЦИАЛИЗАЦИЯ БД (с отдельной колонкой ошибок)
run_query(
    """CREATE TABLE IF NOT EXISTS posts
       (id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        date TEXT,
        time TEXT,
        status TEXT,
        last_error TEXT)"""
)

# 5. АТОМАРНЫЙ АВТОПОСТИНГ (pick-one, без зависших pending_*)
async def check_and_send():
    now_key = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    bot = Bot(token=token)
    try:
        # За один тик отправим до 20 сообщений (если накопилось)
        for _ in range(20):
            row = run_query(
                """
                SELECT id, text FROM posts
                WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
                ORDER BY date ASC, time ASC, id ASC
                LIMIT 1
                """,
                (now_key,),
                fetch=True,
            )

            if not row:
                break

            p_id, txt = row[0]

            # Атомарно "занимаем" пост, чтобы не было дублей даже при 2 инстансах
            rc = run_query(
                "UPDATE posts SET status = '🚚 Отправляется' WHERE id = ? AND status = 'Ожидает'",
                (p_id,),
                return_rowcount=True,
            )
            if rc != 1:
                continue

            try:
                # Без parse_mode, чтобы не падать на спецсимволах
                await bot.send_message(chat_id=chat_id, text=txt)
                run_query(
                    "UPDATE posts SET status = '✅ Отправлено', last_error = NULL WHERE id = ?",
                    (p_id,),
                )
            except Exception as e:
                run_query(
                    "UPDATE posts SET status = 'failed', last_error = ? WHERE id = ?",
                    (str(e), p_id),
                )
    finally:
        await bot.session.close()

# 6. ПЛАНИРОВЩИК (один на инстанс)
@st.cache_resource
def start_scheduler():
    s = AsyncIOScheduler()
    s.add_job(check_and_send, "interval", minutes=1, max_instances=1, coalesce=True)
    s.start()
    return s

start_scheduler()

# 7. ИНТЕРФЕЙС
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Новый пост")
    msg = st.text_area("Текст:", height=250)
    d = st.date_input("Дата")
    t = st.time_input("Время", step=60)

    if st.button("✨ Запланировать"):
        if msg.strip():
            run_query(
                "INSERT INTO posts (text, date, time, status, last_error) VALUES (?, ?, ?, ?, NULL)",
                (msg.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"),
            )
            st.rerun()

with col_right:
    st.subheader("📅 Календарь")
    all_p = run_query("SELECT text, date, time, status FROM posts", fetch=True)

    events = []
    for txt, d_s, t_s, stat in all_p:
        if "✅" in stat:
            color = "#28a745"
        elif stat == "failed":
            color = "#dc3545"
        elif "🚚" in stat:
            color = "#0dcaf0"
        else:
            color = "#FFA500"

        events.append(
            {
                "title": f"{t_s} | {stat}",
                "start": f"{d_s}T{t_s}:00",
                "color": color,
            }
        )

    cal_options = {
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek"},
        "initialView": "dayGridMonth",
        "nowIndicator": True,
    }

    calendar(events=events, options=cal_options)

# 8. УПРАВЛЕНИЕ
st.divider()
st.subheader("🗑️ Управление постами")

rows = run_query(
    "SELECT id, date, time, text, status, last_error FROM posts ORDER BY date DESC, time DESC, id DESC",
    fetch=True,
)

for r in rows:
    c1, c2 = st.columns([5, 1])
    with c1:
        err_msg = f" (:red[{r[5]}])" if r[5] else ""
        st.write(f"📌 {r[1]} {r[2]} — **{r[4]}**{err_msg}")
        preview = r[3][:120] + ("..." if len(r[3]) > 120 else "")
        st.caption(preview)

    with c2:
        if st.button("❌", key=f"del_{r[0]}"):
            run_query("DELETE FROM posts WHERE id = ?", (r[0],))
            st.rerun()
