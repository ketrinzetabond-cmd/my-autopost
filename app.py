import streamlit as st
from aiogram import Bot
from datetime import datetime, timedelta
import sqlite3
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from streamlit_calendar import calendar

# 1. Настройка страницы
st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮", layout="wide")
st.title("🔮 Мой Автопостинг")

# 2. Проверка токена
if "TELEGRAM_TOKEN" not in st.secrets:
    st.error("Ключ TELEGRAM_TOKEN не найден в Secrets!")
    st.stop()

token = st.secrets["TELEGRAM_TOKEN"]
chat_id = "@numerologiputivoditel"

# 3. База данных
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              text TEXT,
              date TEXT,
              time TEXT,
              status TEXT)''')
conn.commit()

# 4. Автопостинг
async def check_and_send():
    now = datetime.now() + timedelta(hours=2)
    now_key = now.strftime("%Y-%m-%d %H:%M")

    # Исправленная строка склейки для SQLite
    c.execute("""
        SELECT id, text FROM posts
        WHERE (date || ' ' || time) <= ? AND status = 'Ожидает'
    """, (now_key,))
    if not pending:
        return

    # ✅ FIX: бот создаём один раз на запуск функции (не на каждый пост)
    bot = Bot(token=token)
    try:
        for p_id, txt in pending:
            try:
                # ✅ Рекомендация: пока убираем Markdown, чтобы текст не ломал отправку
                await bot.send_message(chat_id=chat_id, text=txt)

                c.execute("UPDATE posts SET status = '✅ Отправлено' WHERE id = ?", (p_id,))
            except Exception as e:
                c.execute("UPDATE posts SET status = ? WHERE id = ?",
                          (f"❌ Ошибка: {str(e)}", p_id))
        conn.commit()
    finally:
        await bot.session.close()

# 5. Планировщик (лучше, чем session_state)
@st.cache_resource
def get_scheduler():
    s = AsyncIOScheduler()
    # ✅ FIX: не накладывать новый запуск поверх старого
    s.add_job(check_and_send, 'interval', minutes=1, max_instances=1, coalesce=True)
    s.start()
    return s

get_scheduler()

# 6. Интерфейс (Форма + Календарь)
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📝 Создать пост")
    message = st.text_area("Текст поста:", height=200)
    d = st.date_input("День")
    t = st.time_input("Время", step=60)

    if st.button("✨ Запланировать"):
        if message and message.strip():
            c.execute(
                "INSERT INTO posts (text, date, time, status) VALUES (?, ?, ?, ?)",
                (message.strip(), d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает")
            )
            conn.commit()
            st.rerun()

with col_right:
    st.subheader("📅 Сетка календаря")
    all_p = c.execute("SELECT text, date, time, status FROM posts").fetchall()
    events = []
    for text, date_s, time_s, status in all_p:
        color = "#28a745" if "✅" in status else ("#dc3545" if "❌" in status else "#FFA500")

        # ✅ FIX: календарю отдаём ISO datetime, чтобы учитывалось время
        events.append({
            "title": f"{time_s} | {status}",
            "start": f"{date_s}T{time_s}:00",
            "color": color
        })

    calendar(events=events, options={"initialView": "dayGridMonth"})

# 7. Список для удаления
st.divider()
st.subheader("🗑️ Управление постами")
rows = c.execute("SELECT id, date, time, text, status FROM posts ORDER BY date DESC, time DESC").fetchall()

for r in rows:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.write(f"📌 {r[1]} {r[2]} — {r[4]}")
        st.caption((r[3][:120] + "…") if len(r[3]) > 120 else r[3])
    with c2:
        if st.button("❌", key=f"del_{r[0]}"):
            c.execute("DELETE FROM posts WHERE id = ?", (r[0],))
            conn.commit()
            st.rerun()
