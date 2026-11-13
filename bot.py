import asyncio
import re
import xml.etree.ElementTree as ET
from maxapi import Bot, Dispatcher
from maxapi.types import MessageCreated, MessageCallback, InputMedia, BotStarted
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons import CallbackButton

bot = Bot(token="f9LHodD0cOImesTPXx55j74ZEmekxW66Y8xo0DZ4NSyNxvaNuZgpBb9Ng_ttcZskPuJ3HhxahHmHD8rH6uEf")
dp = Dispatcher()

user_states = {}

def normalize(text):
    text = text.strip().lower()
    text = text.replace("ё", "е")
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "", text)
    return text

def ballov(n):
    n_abs = abs(n) % 100
    if 11 <= n_abs <= 19:
        word = "баллов"
    else:
        n_last = n_abs % 10
        if n_last == 1:
            word = "балл"
        elif 2 <= n_last <= 4:
            word = "балла"
        else:
            word = "баллов"
    return f"{n} {word}"

def load_questions():
    tree = ET.parse('questions.xml')
    root = tree.getroot()
    questions = []
    for q in root.findall('question'):
        q_data = {
            "text": q.find('text').text,
            "image": q.find('image').text,
            "answers": [ans.text for ans in q.findall('answers/answer')],
            "hint": q.find('hint').text
        }
        questions.append(q_data)
    return questions

QUESTIONS = load_questions()

def make_start_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(CallbackButton(text="Начать тест", payload="start_quest"))
    return keyboard.as_markup()

def make_question_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        CallbackButton(text="Пропустить", payload="skip_quest"),
        CallbackButton(text="Завершить", payload="finish_quest")
    )
    return keyboard.as_markup()

def make_return_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        CallbackButton(text="Вернуться к вопросу", payload="return_quest"),
        CallbackButton(text="Пропустить", payload="skip_quest"),
        CallbackButton(text="Завершить", payload="finish_quest")
    )
    return keyboard.as_markup()

async def send_question(event, user_id):
    state = user_states.get(user_id)
    if not state:
        return
    step = state["step"]
    
    if step >= len(QUESTIONS):
        await finish_quest_async(event, user_id)
        return
        
    q = QUESTIONS[step]
    
    attachments = [make_question_keyboard()]
    
    if q.get("image"):
        attachments.append(InputMedia(path=q["image"]))

    try:
        await event.message.answer(
            text=q["text"], 
            attachments=attachments
        )
    except Exception as e:
        print(f"Ошибка при отправке картинки: {e}")
        await event.message.answer(
            text=q["text"], 
            attachments=[make_question_keyboard()]
        )

async def finish_quest_async(event, user_id):
    state = user_states.get(user_id)
    score = state["score"] if state else 0
    
    if score >= 13:
        msg = "Отличный результат! Ты хорошо помнишь детали текстов."
    elif score >= 9:
        msg = "Хороший результат. Перечитай эпизоды, в которых были ошибки."
    else:
        msg = "Стоит вернуться к текстам произведений."

    await event.message.answer(
        text=f"Ты ответил(а) верно на {ballov(score)} из 15 возможных.\n\n{msg}",
        attachments=[make_start_keyboard()]
    )
    if user_id in user_states:
        del user_states[user_id]

# --- ОБРАБОТЧИКИ ---

@dp.bot_started()
async def on_bot_started(event: BotStarted):
    welcome_text = (
        "Пожалуйста, сначала напиши сюда любое сообщение (например, своё имя или просто «Привет»), чтобы запустить бота. "
        "После этого мы сможем начать."
    )
    # Отправляем текст без кнопки
    await event.bot.send_message(
        chat_id=event.chat_id,
        text=welcome_text
    )

@dp.message_created()
async def hello_handler(event: MessageCreated):
    user_id = event.message.sender.user_id
    
    if user_id in user_states:
        if not event.message.body.text:
            return
            
        text = event.message.body.text.strip().lower()
        state = user_states[user_id]
        q = QUESTIONS[state["step"]]
        
        user_norm = normalize(text)
        is_correct = False
        
        for ans in q["answers"]:
            if user_norm == normalize(ans):
                is_correct = True
                break
                
        if is_correct:
            if not state.get("answered_wrong", False):
                state["score"] += 1
                await event.message.answer(text=f"✅ Верно! У вас {ballov(state['score'])}.")
            else:
                await event.message.answer(text=f"✅ Верно, но баллы не начислены (вы уже ошибались). У вас {ballov(state['score'])}.")
            
            state["step"] += 1
            state["answered_wrong"] = False
            await send_question(event, user_id)
        else:
            state["answered_wrong"] = True
            await event.message.answer(
                text=f"❌ Неверно.\nУ вас {ballov(state['score'])}.\n\n{q['hint']}",
                attachments=[make_return_keyboard()]
            )
        return

    welcome_text = (
        "Привет! Я помогу тебе подготовиться к ЕГЭ по литературе. "
        "Привет! Я помогу тебе подготовиться к ЕГЭ по литературе. Я буду присылать кадры из известных отечественных экранизаций, а ты – отвечать на вопросы по тексту произведений. Кадр поможет вспомнить эпизод, но ответ всегда нужно искать в книге. Всего 15 вопросов, за каждый верный ответ – 1 балл. Начнем с романа-эпопеи Л.Н. Толстого «Война и мир» в экранизации С.Ф. Бондарчука"
    )
    await event.message.answer(
        text=welcome_text,
        attachments=[make_start_keyboard()]
    )

@dp.message_callback()
async def callback_handler(event: MessageCallback):
    # Берем ID напрямую из события нажатия кнопки
    chat_id, user_id = event.get_ids()
    
    print(f"[ТЕСТ] Нажата кнопка. Payload: {event.callback.payload}. User ID: {user_id}")
    
    payload = event.callback.payload

    if payload == "start_quest":
        user_states[user_id] = {"step": 0, "score": 0, "answered_wrong": False}
        await event.answer(new_text="Поехали! Вопрос 1.")
        await send_question(event, user_id)

    elif payload == "finish_quest":
        await event.answer(new_text="Тест завершен.")
        await finish_quest_async(event, user_id)

    elif payload == "return_quest":
        state = user_states.get(user_id)
        if state:
            await event.answer(new_text="Вопрос заново:")
            await send_question(event, user_id)
        else:
            await event.answer(new_text="Сначала напишите боту любое сообщение, чтобы начать тест.")

    elif payload == "skip_quest":
        state = user_states.get(user_id)
        if state:
            state["step"] += 1
            state["answered_wrong"] = False
            if state["step"] >= len(QUESTIONS):
                await event.answer(new_text="Вопрос пропущен. Это был последний вопрос.")
                await finish_quest_async(event, user_id)
            else:
                await event.answer(new_text="Вопрос пропущен.")
                await send_question(event, user_id)

async def main():
    print("Бот запускается...")
    await bot.delete_webhook()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
