import streamlit as st
from aiogram import Bot
from datetime import datetime
import logging
import sqlite3
import asyncio

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # pip install backports.zoneinfo

from apscheduler.schedulers.background import BackgroundScheduler
from streamlit_calendar import calendar


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
    st.warning("Не удалось загрузить таймзону Europe/Zaporozhye — использую UTC.")


# 3) БЕЗОПАСНАЯ РАБОТА С БД
def run_query(query, params=(), fetch=False, return_rowcount=False):
    try:
        with sqlite3.connect("scheduler.db", check_same_thread=False) as conn:
            c = conn.cursor()
            c.execute(query, params)

            if fetch:
                return c.fetchall()

            conn.commit()

            if return_rowcount:
                return c.rowcount

            return None
    except Exception as e:
        # Важно: не дергать st.error из фоновой задачи
        logging.exception("DB error: %s | query=%s | params=%s", e, query, params)
        if fetch:
            return []
        if return_rowcount:
            return 0
        return None


# 4) ИНИЦИАЛИЗАЦИЯ ТАБЛИЦЫ
run_query("""
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    date TEXT,
    time TEXT,
    status TEXT,
    last_error TEXT
)
""")

# (опционально) индекс для скорости
run_query("CREATE INDEX IF NOT EXISTS idx_posts_status_dt ON posts(status, date, time)")


def color_for_status(stat: str) -> str:
    if not stat:
        return "#FFA500"
    if "✅" in stat:
        return "#28a745"
    if stat == "failed":
        return "#dc3545"
    if "🚚" in stat:
        return "#0dcaf0"
    if stat == "cancelled":
        return "#6c757d"
    return "#FFA500"


# 5) АВТОПОСТИНГ (pick-one)
async def check_and_send():
    now_key = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    bot = Bot(token=token)
    try:
        # За один тик отправим до 20 сообщений
        for _ in range(20):
            row = run_query(
                """
                SELECT id, text
                FROM posts
                WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
                ORDER BY date ASC, time ASC, id ASC
                LIMIT 1
                """,
                (now_key,),
                fetch=True
            )
            if not row:
                break

            p_id, txt = row[0]

            # атомарно "занимаем" пост (защита от дублей)
            rc = run_query(
                "UPDATE posts SET status = '🚚 Отправляется' WHERE id = ? AND status = 'Ожидает'",
                (p_id,),
                return_rowcount=True
            )
            if rc != 1:
                continue

            try:
                await bot.send_message(chat_id=chat_id, text=txt)
                run_query(
                    "UPDATE posts SET status = '✅ Отправлено', last_error = NULL WHERE id = ?",
                    (p_id,)
                )
            except Exception as e:
                run_query(
                    "UPDATE posts SET status = 'failed', last_error = ? WHERE id = ?",
                    (str(e), p_id)
                )
    finally:
        await bot.session.close()


# 6) APSCHEDULER ДЛЯ STREAMLIT: BackgroundScheduler + asyncio.run
def check_and_send_job():
    """
    BackgroundScheduler работает в отдельном потоке.
    Там нет running event loop, поэтому запускаем async через asyncio.run().
    """
    try:
        asyncio.run(check_and_send())
    except Exception:
        logging.exception("Scheduler job failed")


@st.cache_resource
def start_scheduler():
    s = BackgroundScheduler(daemon=True)
    s.add_job(check_and_send_job, "interval", minutes=1, max_instances=1, coalesce=True)
    s.start()
    return s


start_scheduler()


# 7) UI: создание + календарь
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Новый пост")
    msg = st.text_area("Текст:", height=200)
    d = st.date_input("Дата")
    t = st.time_input("Время", step=60)

    if st.button("✨ Запланировать"):
        if msg and msg.strip():
            run_query(
                "INSERT INTO posts (text, date, time, status, last_error) VALUES (?, ?, ?, ?, NULL)",
                (msg.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает")
            )
            st.success("Готово!")
            st.rerun()
        else:
            st.error("Текст поста пустой.")


with col_right:
    st.subheader("📅 Календарь")

    all_p = run_query("SELECT text, date, time, status FROM posts", fetch=True)

    events = []
    for text, d_s, t_s, stat in all_p:
        events.append({
            "title": f"{t_s} | {stat}",
            "start": f"{d_s}T{t_s}:00",
            "color": color_for_status(stat)
        })

    calendar(events=events, options={
        "headerToolbar": {"left": "prev,next today", "center": "title", "right": "dayGridMonth,timeGridWeek"},
        "initialView": "dayGridMonth",
        "nowIndicator": True
    })


# 8) УПРАВЛЕНИЕ ПОСТАМИ
st.divider()
st.subheader("🗑️ Управление постами")

top_actions = st.columns([1, 1, 3])
with top_actions[0]:
    if st.button("🧹 Очистить отправленные"):
        run_query("DELETE FROM posts WHERE status = '✅ Отправлено'")
        st.rerun()

with top_actions[1]:
    if st.button("🔁 Повторить все failed"):
        run_query("UPDATE posts SET status = 'Ожидает' WHERE status = 'failed'")
        st.rerun()

rows = run_query(
    "SELECT id, date, time, text, status, last_error FROM posts "
    "ORDER BY date DESC, time DESC, id DESC",
    fetch=True
)

for post_id, date_s, time_s, text, status, last_error in rows:
    c1, c2, c3 = st.columns([6, 2, 2])

    with c1:
        err = f" — (:red[{last_error}])" if last_error else ""
        st.write(f"📌 **{date_s} {time_s}** — `{status}`{err}")
        preview = text[:140] + ("..." if len(text) > 140 else "")
        st.caption(preview)

    with c2:
        if status == "Ожидает":
            if st.button("🚫 Отменить", key=f"cancel_{post_id}"):
                run_query("UPDATE posts SET status='cancelled' WHERE id=? AND status='Ожидает'", (post_id,))
                st.rerun()

        if status == "failed":
            if st.button("🔁 Повторить", key=f"retry_{post_id}"):
                run_query("UPDATE posts SET status='Ожидает' WHERE id=? AND status='failed'", (post_id,))
                st.rerun()

    with c3:
        if st.button("❌ Удалить", key=f"del_{post_id}"):
            run_query("DELETE FROM posts WHERE id = ?", (post_id,))
            st.rerun()
