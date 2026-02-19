import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime, timedelta # Добавили коррекцию времени
import sqlite3

st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮")
st.title("🔮 Мой Автопостинг")

# --- База данных ---
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

with st.sidebar:
    st.header("Настройки")
    token = st.text_input("Токен бота:", type="password")
    chat_id = "@numerologiputivoditel"

# --- Форма ---
message = st.text_area("Текст поста:")
col1, col2 = st.columns(2)
with col1:
    d = st.date_input("День")
with col2:
    t = st.time_input("Время")

# ВЫЧИСЛЯЕМ ВРЕМЯ (исправляем разницу в 2 часа)
# Теперь 'now' будет показывать то же время, что и на твоем ноутбуке
now = datetime.now() + timedelta(hours=2) 

if st.button("Записать в план"):
    if token and message:
        target_datetime = datetime.combine(d, t)
        wait_seconds = (target_datetime - now).total_seconds()
        
        if wait_seconds < 0:
            st.error(f"Ошибка! Выбранное время ({t}) уже прошло. На сервере сейчас {now.strftime('%H:%M')}")
        else:
            # Сохраняем в память
            c.execute("INSERT INTO posts VALUES (?, ?, ?, ?)", 
                      (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
            conn.commit()
            st.success(f"Пост запланирован! Он выйдет через {int(wait_seconds // 60)} мин.")
            
            # Функция отправки
            async def delayed_send(seconds, txt):
                await asyncio.sleep(seconds)
                bot = Bot(token=token)
                await bot.send_message(chat_id=chat_id, text=txt)
                await bot.session.close()
            
            asyncio.run(delayed_send(wait_seconds, message))
    else:
        st.warning("Введи токен и текст!")

# --- Список постов внизу ---
st.divider()
st.subheader("📅 Твой план публикаций")
all_posts = c.execute("SELECT * FROM posts").fetchall()
for p in all_posts:
    st.write(f"📌 {p[1]} в {p[2]} — {p[0][:30]}...")
