# Телеграм-бот для напоминаний (версия для Railway)

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime, timedelta
import asyncio

# Токен берётся из переменных окружения Railway
TOKEN = os.getenv("BOT_TOKEN")

# Файл для хранения задач
TASKS_FILE = "tasks.json"

def load_tasks():
    """Загружаем задачи из файла"""
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_tasks(tasks):
    """Сохраняем задачи в файл"""
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

# Глобальная переменная для задач
tasks = load_tasks()

def get_chat_id(update: Update):
    """Получаем ID чата (работает и в личке, и в группах)"""
    return str(update.effective_chat.id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - приветствие"""
    chat_id = get_chat_id(update)
    if chat_id not in tasks:
        tasks[chat_id] = []
        save_tasks(tasks)
    
    chat_type = "группе" if update.effective_chat.type != "private" else "личке"
    
    welcome_text = f"""
👋 Привет! Я бот-напоминалка!
Работаю в {chat_type}!

📝 Команды:
/add - добавить задачу
/remind - напоминание через время
/list - показать все задачи
/done - отметить выполненной
/clear - удалить все задачи
/help - помощь

Примеры:
• "Купить молоко" - добавит задачу
• /remind 30 Позвонить маме - напомнит через 30 минут
• /remind 2ч Встреча - напомнит через 2 часа
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    help_text = """
🤖 Как пользоваться:

📝 ДОБАВИТЬ ЗАДАЧУ:
• Просто напиши: "Купить хлеб"
• Или: /add Сходить в зал

⏰ НАПОМИНАНИЕ:
• /remind 15 Проверить почту
  (напомнит через 15 минут)
• /remind 2ч Встреча с клиентом
  (напомнит через 2 часа)
• /remind 30м Перерыв
  (напомнит через 30 минут)

📋 СПИСОК ЗАДАЧ:
• /list - покажет все дела

✅ ВЫПОЛНИТЬ:
• /done 1 - отметит первую

🗑️ ОЧИСТИТЬ:
• /clear - удалит все

👥 В ГРУППАХ:
Бот работает для всех участников чата!
Все видят общие задачи.
"""
    await update.message.reply_text(help_text)

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление задачи"""
    chat_id = get_chat_id(update)
    
    if context.args:
        task_text = " ".join(context.args)
    else:
        await update.message.reply_text("❌ Напиши задачу!\nПример: /add Купить хлеб")
        return
    
    if chat_id not in tasks:
        tasks[chat_id] = []
    
    task = {
        "text": task_text,
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "created_by": update.effective_user.first_name,
        "done": False
    }
    
    tasks[chat_id].append(task)
    save_tasks(tasks)
    
    await update.message.reply_text(f"✅ Добавлено: {task_text}\n📋 Всего задач: {len(tasks[chat_id])}")

async def remind_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Напоминание через определённое время"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ Укажи время и текст!\n\n"
            "Примеры:\n"
            "• /remind 15 Позвонить клиенту\n"
            "• /remind 2ч Встреча\n"
            "• /remind 30м Обед"
        )
        return
    
    time_str = context.args[0]
    reminder_text = " ".join(context.args[1:])
    
    # Парсим время
    try:
        if time_str.endswith('ч') or time_str.endswith('h'):
            minutes = int(time_str[:-1]) * 60
        elif time_str.endswith('м') or time_str.endswith('m'):
            minutes = int(time_str[:-1])
        else:
            minutes = int(time_str)
        
        if minutes <= 0 or minutes > 1440:  # Максимум 24 часа
            await update.message.reply_text("❌ Время должно быть от 1 минуты до 24 часов!")
            return
        
        # Вычисляем время напоминания
        remind_time = datetime.now() + timedelta(minutes=minutes)
        
        # Добавляем задачу с напоминанием
        chat_id = get_chat_id(update)
        if chat_id not in tasks:
            tasks[chat_id] = []
        
        task = {
            "text": reminder_text,
            "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "created_by": update.effective_user.first_name,
            "done": False,
            "reminder": remind_time.strftime("%d.%m.%Y %H:%M")
        }
        
        tasks[chat_id].append(task)
        save_tasks(tasks)
        
        hours = minutes // 60
        mins = minutes % 60
        
        time_text = ""
        if hours > 0:
            time_text += f"{hours} ч "
        if mins > 0:
            time_text += f"{mins} мин"
        
        await update.message.reply_text(
            f"⏰ Напомню через {time_text}!\n"
            f"📝 {reminder_text}\n"
            f"🕐 Время: {remind_time.strftime('%H:%M')}"
        )
        
        # Запускаем таймер
        asyncio.create_task(send_reminder(context, update.effective_chat.id, reminder_text, minutes * 60))
        
    except ValueError:
        await update.message.reply_text(
            "❌ Неправильный формат времени!\n\n"
            "Используй:\n"
            "• Число (минуты): /remind 30 Текст\n"
            "• С 'м': /remind 45м Текст\n"
            "• С 'ч': /remind 2ч Текст"
        )

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, seconds: int):
    """Отправляет напоминание через заданное время"""
    await asyncio.sleep(seconds)
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⏰ НАПОМИНАНИЕ!\n\n📝 {text}\n\n✅ /list - посмотреть все задачи"
    )

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все задачи"""
    chat_id = get_chat_id(update)
    
    if chat_id not in tasks or not tasks[chat_id]:
        await update.message.reply_text("📭 Пока нет задач!\n\nДобавь задачу, просто написав мне.")
        return
    
    message = "📋 Список задач:\n\n"
    
    active_count = 0
    done_count = 0
    
    for i, task in enumerate(tasks[chat_id], 1):
        creator = task.get("created_by", "Кто-то")
        reminder = task.get("reminder", "")
        
        if task["done"]:
            message += f"✅ {i}. ~~{task['text']}~~\n"
            message += f"   👤 {creator}\n"
            done_count += 1
        else:
            message += f"⬜ {i}. {task['text']}\n"
            message += f"   👤 {creator}"
            if reminder:
                message += f" | ⏰ {reminder}"
            message += "\n"
            active_count += 1
        message += "\n"
    
    message += f"📊 Активных: {active_count} | Выполнено: {done_count}"
    
    await update.message.reply_text(message)

async def done_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отметить задачу выполненной"""
    chat_id = get_chat_id(update)
    
    if not context.args:
        await update.message.reply_text("❌ Укажи номер!\nПример: /done 1")
        return
    
    try:
        task_num = int(context.args[0])
        
        if chat_id not in tasks or not tasks[chat_id]:
            await update.message.reply_text("📭 Нет задач!")
            return
        
        if task_num < 1 or task_num > len(tasks[chat_id]):
            await update.message.reply_text(f"❌ Нет задачи #{task_num}")
            return
        
        task = tasks[chat_id][task_num - 1]
        task["done"] = True
        task["completed_by"] = update.effective_user.first_name
        save_tasks(tasks)
        
        await update.message.reply_text(
            f"🎉 Выполнено!\n"
            f"📝 {task['text']}\n"
            f"✅ Отметил(а): {update.effective_user.first_name}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Введи номер цифрой!")

async def clear_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить все задачи"""
    chat_id = get_chat_id(update)
    
    if chat_id in tasks:
        count = len(tasks[chat_id])
        tasks[chat_id] = []
        save_tasks(tasks)
        await update.message.reply_text(f"🗑️ Удалено {count} задач!\n\nНачинаем с чистого листа!")
    else:
        await update.message.reply_text("📭 И так нет задач!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка обычных сообщений - добавление задачи"""
    chat_id = get_chat_id(update)
    task_text = update.message.text
    
    if chat_id not in tasks:
        tasks[chat_id] = []
    
    task = {
        "text": task_text,
        "created": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "created_by": update.effective_user.first_name,
        "done": False
    }
    
    tasks[chat_id].append(task)
    save_tasks(tasks)
    
    await update.message.reply_text(f"✅ Добавлено: {task_text}\n\n💡 /list - все задачи")

def main():
    """Запуск бота"""
    # Проверяем что токен установлен
    if not TOKEN:
        print("❌ ОШИБКА: Не установлена переменная BOT_TOKEN!")
        print("Добавь токен в настройках Railway (Variables)")
        return
    
    print("🤖 Бот запускается...")
    print(f"✅ Токен найден: {TOKEN[:10]}...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add", add_task))
    app.add_handler(CommandHandler("remind", remind_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("done", done_task))
    app.add_handler(CommandHandler("clear", clear_tasks))
    
    # Обработчик обычных сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен успешно!")
    print("📡 Ожидание сообщений...")
    
    # Запускаем бота (для Railway)
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
