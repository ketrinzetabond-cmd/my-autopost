import streamlit as st
import asyncio
from aiogram import Bot
from datetime import datetime
import time

st.set_page_config(page_title="Помощник Нумеролога", page_icon="🔮")
st.title("🔮 Автопостинг: Путеводитель")

# Настройки в боковой панели
with st.sidebar:
    st.header("Настройки")
    token = st.text_input("Токен бота:", type="password")
    chat_id = st.text_input("Канал:", value="@numerologiputivoditel")

# Основная часть
message = st.text_area("Текст твоего послания:", height=200)
col1, col2 = st.columns(2)

with col1:
    date = st.date_input("День публикации")
with col2:
    post_time = st.time_input("Время публикации")

if st.button("Запланировать пост"):
    if token and message:
        # Соединяем дату и время
        target_datetime = datetime.combine(date, post_time)
        now = datetime.now()
        
        if target_datetime > now:
            wait_seconds = (target_datetime - now).total_seconds()
            st.info(f"Пост запланирован! Он выйдет через {round(wait_seconds/60)} мин.")
            
            # Маленькая хитрость для личного пользования:
            # Мы заставляем сайт подождать и отправить
            async def delayed_send():
                await asyncio.sleep(wait_seconds)
                bot = Bot(token=token)
                await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
                await bot.session.close()
            
            # Запускаем ожидание в фоновом режиме
            asyncio.run(delayed_send())
            st.success("Ура! Пост только что был отправлен в канал!")
        else:
            st.error("Ошибка: Время уже прошло! Выбери будущее время.")
    else:
        st.warning("Пожалуйста, введи текст и проверь токен.")
