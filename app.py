import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime
import sqlite3 # Это наша база данных (записная книжка)

st.set_page_config(page_title="Путеводитель Нумеролога", page_icon="🔮")
st.title("🔮 Мой Автопостинг")

# --- ШАГ А: Создаем базу данных (записную книжку) ---
conn = sqlite3.connect('scheduler.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS posts 
             (text TEXT, date TEXT, time TEXT, status TEXT)''')
conn.commit()

# --- ШАГ Б: Настройки ---
with st.sidebar:
    st.header("Настройки")
    token = st.text_input("Токен бота:", type="password")
    chat_id = "@numerologiputivoditel"

# --- ШАГ В: Форма для нового поста ---
message = st.text_area("Текст твоего послания:")
col1, col2 = st.columns(2)
with col1:
    d = st.date_input("День")
with col2:
    t = st.time_input("Время")

if st.button("Записать в план"):
    if token and message:
        # Сохраняем пост в базу данных
        c.execute("INSERT INTO posts VALUES (?, ?, ?, ?)", 
                  (message, d.strftime("%Y-%m-%d"), t.strftime("%H:%M"), "Ожидает"))
        conn.commit()
        st.success("Пост записан в память!")
    else:
        st.warning("Заполни текст и проверь токен.")

# --- ШАГ Г: Показываем список всех постов ---
st.divider()
st.subheader("📅 Твой план на ближайшее время")
all_posts = c.execute("SELECT * FROM posts").fetchall()

for p in all_posts:
    st.write(f"📌 **{p[1]} в {p[2]}** — {p[0][:30]}... ({p[3]})")
