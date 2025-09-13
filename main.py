import telebot
from telebot import types
import random
import math
import threading
import time
import os

# Безопасное получение токена (обязательно используйте .env в продакшене)
BOT_TOKEN = os.getenv('BOT_TOKEN', '8476730469:AAEcYyXei67710RA44tZJunKPC8z60veN7Y')
bot = telebot.TeleBot(BOT_TOKEN)

# Храним игры по коду комнаты
games = {}
# Храним кто в какой комнате: user_id -> room_code
user_rooms = {}

# Список заданий
tasks = ["НАЙТИ КРАСНЫЙ ЦВЕТ", "СФОТОГРАФИРОВАТЬ ДЕРЕВО", "ВВЕСТИ КОД 1234", "ДОТРОНУТЬСЯ ДО СТЕНЫ"]

# Флаг для авто-обновления локации
auto_location_enabled = True
# Интервал авто-обновления в секундах
LOCATION_UPDATE_INTERVAL = 30

# Создаем клавиатуру с основными кнопками
def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        types.KeyboardButton("📍 Отправить локацию", request_location=True),
        types.KeyboardButton("👥 Кто в игре"),
        types.KeyboardButton("🎮 Моя роль"),
        types.KeyboardButton("❌ Выйти из игры"),
        types.KeyboardButton("⚙️ Настройки")
    ]
    markup.add(*buttons)
    return markup

# Создаем клавиатуру настроек
def create_settings_keyboard():
    markup = types.InlineKeyboardMarkup()
    auto_text = "📍 Авто-локация: ВКЛ" if auto_location_enabled else "📍 Авто-локация: ВЫКЛ"
    markup.add(
        types.InlineKeyboardButton(auto_text, callback_data="toggle_auto_location"),
        types.InlineKeyboardButton("⏰ Интервал: 30сек", callback_data="change_interval")
    )
    return markup

# Функция для расчета расстояния в метрах
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Радиус Земли в метрах
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    distance = R * c
    return distance

# Фоновая задача для авто-обновления локации — ТОЛЬКО для предателей
def auto_location_updater():
    while True:
        try:
            if auto_location_enabled:
                # Проходим по всем игрокам во всех играх
                for user_id, room_code in list(user_rooms.items()):
                    if room_code not in games or games[room_code]['state'] != 'playing':
                        continue

                    game = games[room_code]
                    username = None
                    for uname, data in game['players'].items():
                        if data.get('user_id') == user_id:  # Ищем username по user_id
                            username = uname
                            break

                    if not username:
                        continue

                    # Только если игрок — предатель
                    if game['players'][username]['role'] == 'impostor' and game['players'][username]['alive']:
                        try:
                            # Отправляем напоминание предателю обновить локацию
                            bot.send_message(
                                user_id,
                                "🔪 Ты — предатель! 📍 Отправь свою локацию, чтобы найти жертву.\n"
                                "(Ты можешь сделать это вручную — или жди следующего авто-обновления)",
                                reply_markup=create_main_keyboard()
                            )
                            print(f"🔔 Авто-напоминание предателю @{username} в комнате {room_code}")
                        except Exception as e:
                            print(f"❌ Не удалось отправить авто-напоминание предателю {user_id}: {e}")
                            # Если бот заблокирован — удаляем игрока
                            if user_id in user_rooms:
                                del user_rooms[user_id]

            time.sleep(LOCATION_UPDATE_INTERVAL)  # Каждые 30 секунд — только для предателей
        except Exception as e:
            print(f"Ошибка в авто-обновлении локации: {e}")
            time.sleep(60)

# Запускаем фоновый поток
location_thread = threading.Thread(target=auto_location_updater, daemon=True)
location_thread.start()

# Команда старта
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    markup = create_main_keyboard()
    bot.reply_to(message, "👋 Добро пожаловать в Real Among Us!\n\n"
                          "🎯 Создать комнату: /create\n"
                          "🔗 Присоединиться: /join_1234\n"
                          "📋 Список игроков: /list\n"
                          "🚀 Начать игру: /startgame\n"
                          "⚙️ Настройки: кнопка 'Настройки'\n\n"
                          "📍 Локация автоматически обновляется каждые 30 сек!",
                 reply_markup=markup)

# Кнопка настроек
@bot.message_handler(func=lambda message: message.text == "⚙️ Настройки")
def handle_settings(message):
    markup = create_settings_keyboard()
    bot.reply_to(message, "⚙️ Настройки игры:\n\n"
                         "📍 Авто-обновление локации - каждые 30 секунд\n"
                         "📏 Дистанция для убийства - 5 метров\n"
                         "🎯 Задания - 4 различных типа",
                 reply_markup=markup)

# Обработка callback кнопок настроек
@bot.callback_query_handler(func=lambda call: call.data.startswith(('toggle_auto_location', 'change_interval')))
def handle_settings_callback(call):
    global auto_location_enabled
    
    if call.data == 'toggle_auto_location':
        auto_location_enabled = not auto_location_enabled
        status = "включена" if auto_location_enabled else "выключена"
        bot.answer_callback_query(call.id, f"📍 Авто-локация {status}")
        
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id, 
                call.message.message_id, 
                reply_markup=create_settings_keyboard()
            )
        except Exception as e:
            print(f"Ошибка обновления клавиатуры: {e}")
    
    elif call.data == 'change_interval':
        bot.answer_callback_query(call.id, "Функция изменения интервала в разработке")

# Создать игру
@bot.message_handler(commands=['create'])
def create_game(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not username:
            bot.reply_to(message, "❌ Создай себе username в настройках Telegram!")
            return

        room_code = str(random.randint(1000, 9999))
        
        games[room_code] = {
            'creator': user_id,
            'players': {},  # username -> {user_id, role, alive, location}
            'state': 'lobby',
            'tasks': tasks.copy()
        }
        
        user_rooms[user_id] = room_code
        
        # Добавляем создателя как игрока
        games[room_code]['players'][username] = {
            'user_id': user_id,
            'role': None,
            'alive': True,
            'location': None
        }
        
        markup = types.InlineKeyboardMarkup()
        share_btn = types.InlineKeyboardButton("📤 Поделиться кодом", url=f"https://t.me/share/url?url=/join_{room_code}")
        markup.add(share_btn)
        
        bot.reply_to(message, f"🎮 Комната создана!\n🔢 Код комнаты: {room_code}\n\n"
                             f"Дай этот код друзьям, чтобы они присоединились:\n"
                             f"Они должны написать: /join_{room_code}\n\n"
                             f"Когда все присоединятся, напиши /startgame",
                     reply_markup=markup)
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при создании игры: {e}")

# Помощь по присоединению
@bot.message_handler(commands=['join'])
def join_help(message):
    markup = types.InlineKeyboardMarkup()
    example_btn = types.InlineKeyboardButton("🎯 Пример", callback_data="join_example")
    markup.add(example_btn)
    
    bot.reply_to(message, "Чтобы присоединиться, напиши:\n/join_1234\n\n"
                         "Где 1234 - код комнаты, который тебе дал создатель игры",
                 reply_markup=markup)

# Обработка callback кнопок
@bot.callback_query_handler(func=lambda call: call.data in ["join_example", "show_players", "refresh_players", "start_game"])
def handle_callback(call):
    if call.data == "join_example":
        bot.answer_callback_query(call.id, "Например: /join_5678")
    elif call.data == "show_players" or call.data == "refresh_players":
        show_players(call.message)
    elif call.data == "start_game":
        start_game(call.message)

# Присоединиться к комнате
@bot.message_handler(regexp=r'^/join_(\d{4})$')
def join_game(message):
    try:
        room_code = message.text.split('_')[1]
        user_id = message.from_user.id
        username = message.from_user.username
        
        if not username:
            bot.reply_to(message, "❌ Создай себе username в настройках Telegram!")
            return
            
        if room_code not in games:
            bot.reply_to(message, "❌ Комната не найдена! Проверь код.")
            return
            
        game = games[room_code]
        
        if username in game['players']:
            bot.reply_to(message, "✅ Ты уже в игре!")
            return
            
        # Добавляем игрока
        game['players'][username] = {
            'user_id': user_id,
            'role': None,
            'alive': True,
            'location': None
        }
        user_rooms[user_id] = room_code
        
        markup = create_main_keyboard()
        bot.reply_to(message, f"🎉 Ты присоединился к комнате {room_code}!\n\n"
                             f"📍 Локация будет автоматически обновляться\n"
                             f"Ожидай начала игры от создателя...",
                     reply_markup=markup)
        
        # Сообщаем создателю
        creator_id = game['creator']
        try:
            markup = types.InlineKeyboardMarkup()
            start_btn = types.InlineKeyboardButton("🚀 Начать игру", callback_data="start_game")
            players_btn = types.InlineKeyboardButton("👥 Посмотреть игроков", callback_data="show_players")
            markup.add(start_btn, players_btn)
            
            bot.send_message(creator_id, f"🎉 @{username} присоединился к твоей игре!",
                           reply_markup=markup)
        except Exception as e:
            print(f"Не удалось уведомить создателя: {e}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при присоединении к игре: {e}")

# Показать список игроков
# Показать список игроков
def show_players(message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_rooms:
            bot.send_message(message.chat.id, "❌ Ты не в комнате! Сначала присоединись.")
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games:
            bot.send_message(message.chat.id, "❌ Комната не найдена!")
            return
            
        game = games[room_code]
        
        player_list = "👥 Игроки в комнате:\n"
        for i, (player, data) in enumerate(game['players'].items(), 1):
            status = "✅" if data['alive'] else "💀"
            role_icon = "🔪" if data['role'] == 'impostor' else "👨‍🚀"
            role_text = " (Предатель)" if data['role'] == 'impostor' else " (Мирный)"
            player_list += f"{i}. {status} {role_icon} @{player}{role_text if data['role'] else ''}\n"
        
        player_list += f"\nВсего игроков: {len(game['players'])}"
        
        markup = types.InlineKeyboardMarkup()
        refresh_btn = types.InlineKeyboardButton("🔄 Обновить", callback_data="refresh_players")
        markup.add(refresh_btn)

        # Пытаемся отредактировать сообщение, если это callback
        if hasattr(message, 'message_id') and hasattr(message, 'chat'):
            try:
                bot.edit_message_text(
                    player_list,
                    message.chat.id,
                    message.message_id,
                    reply_markup=markup
                )
            except telebot.apihelper.ApiTelegramException as e:
                if e.error_code == 400 and "message can't be edited" in str(e):
                    # Если нельзя редактировать — отправляем новое сообщение
                    bot.send_message(message.chat.id, player_list, reply_markup=markup)
                else:
                    print(f"Неожиданная ошибка при редактировании: {e}")
        else:
            # Это обычное сообщение от пользователя (например, по кнопке "Кто в игре")
            bot.send_message(message.chat.id, player_list, reply_markup=markup)
            
    except Exception as e:
        print(f"Ошибка показа игроков: {e}")

# Кнопка "Кто в игре"
@bot.message_handler(func=lambda message: message.text == "👥 Кто в игре")
def handle_players_button(message):
    show_players(message)

# Кнопка "Моя роль"
@bot.message_handler(func=lambda message: message.text == "🎮 Моя роль")
def handle_role_button(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        if user_id not in user_rooms:
            bot.reply_to(message, "❌ Ты не в игре!")
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games:
            bot.reply_to(message, "❌ Комната не найдена!")
            return
            
        game = games[room_code]
        
        if username not in game['players']:
            bot.reply_to(message, "❌ Ты не в игре!")
            return
            
        role_data = game['players'][username]
        
        if role_data['role'] is None:
            bot.reply_to(message, "🎭 Игра еще не началась! Ожидай...")
        elif role_data['role'] == 'impostor':
            bot.reply_to(message, "🔪 Ты ПРЕДАТЕЛЬ!\n\n"
                                 "Твоя цель - убить всех мирных жителей!\n"
                                 "Подходи близко к жертвам и отправляй локацию для убийства.")
        else:
            bot.reply_to(message, "👨‍🚀 Ты МИРНЫЙ ЖИТЕЛЬ!\n\n"
                                 "Выполняй задания и ищи предателя!\n"
                                 "Отправляй локацию для перемещения.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при получении роли: {e}")

# Кнопка "Выйти из игры"
@bot.message_handler(func=lambda message: message.text == "❌ Выйти из игры")
def handle_leave_button(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        if user_id in user_rooms:
            room_code = user_rooms[user_id]
            
            if room_code in games and username in games[room_code]['players']:
                del games[room_code]['players'][username]
                
            del user_rooms[user_id]
            
            bot.reply_to(message, "👋 Ты вышел из игры! Чтобы вернуться, присоединись снова.")
        else:
            bot.reply_to(message, "❌ Ты не в игре!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при выходе из игры: {e}")

# Команда /list — показать список игроков
@bot.message_handler(commands=['list'])
def list_players(message):
    show_players(message)

# Начать игру
@bot.message_handler(commands=['startgame'])
def start_game(message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_rooms:
            bot.reply_to(message, "❌ Ты не в комнате!")
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games:
            bot.reply_to(message, "❌ Комната не найдена!")
            return
            
        game = games[room_code]
        
        # Проверяем, что команду дает создатель
        if game['creator'] != user_id:
            bot.reply_to(message, "❌ Только создатель игры может её начать!")
            return
            
        players = list(game['players'].keys())
        if len(players) < 2:
            bot.reply_to(message, "❌ Нужно хотя бы 2 игрока!")
            return
            
        # Выбираем предателей (1 на 4-5 игроков)
        imp_count = max(1, len(players) // 4)
        impostors = random.sample(players, imp_count)
        
        # Раздаём роли
        for player_username in players:
            player_data = game['players'][player_username]
            player_user_id = player_data['user_id']
            
            if player_username in impostors:
                player_data['role'] = 'impostor'
                try:
                    bot.send_message(player_user_id, 
                                   f"🔪 ТЫ ПРЕДАТЕЛЬ!\n\n"
                                   f"Твоя цель - убить всех мирных жителей!\n"
                                   f"Подойди близко к жертве (5 метров) для убийства\n"
                                   f"📍 Локация обновляется автоматически\n\n"
                                   f"Не попадись!")
                except Exception as e:
                    print(f"Не удалось отправить сообщение предателю: {e}")
            else:
                player_data['role'] = 'crewmate'
                try:
                    task = random.choice(game['tasks'])
                    bot.send_message(player_user_id, 
                                   f"👨‍🚀 ТЫ МИРНЫЙ ЖИТЕЛЬ!\n\n"
                                   f"Твое задание: {task}\n"
                                   f"Выполни задание и напиши боту: /taskdone\n"
                                   f"📍 Локация обновляется автоматически\n\n"
                                   f"Найди предателя прежде чем он убьет тебя!")
                except Exception as e:
                    print(f"Не удалось отправить сообщение мирному: {e}")
        
        game['state'] = 'playing'
        
        # Отправляем общее сообщение всем игрокам
        for uid, room in user_rooms.items():
            if room == room_code:
                try:
                    markup = create_main_keyboard()
                    bot.send_message(uid, 
                                   "🚀 ИГРА НАЧАЛАСЬ!\n\n"
                                   "📱 Проверь личные сообщения - там твоя роль!\n"
                                   "📍 Локация обновляется автоматически каждые 30 сек\n"
                                   "🎯 Мирные: выполняйте задания!\n"
                                   "🔪 Предатели: устраняйте враги!",
                                   reply_markup=markup)
                except Exception as e:
                    print(f"Не удалось отправить сообщение игроку {uid}: {e}")
        
        bot.reply_to(message, "🎮 Игра началась! Все игроки получили свои роли.")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при запуске игры: {e}")

# Выполнить задание
@bot.message_handler(commands=['taskdone'])
def complete_task(message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_rooms:
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games or games[room_code]['state'] != 'playing':
            return
            
        game = games[room_code]
        username = message.from_user.username
        
        if game['players'][username]['role'] != 'crewmate':
            bot.reply_to(message, "❌ Только мирные жители могут выполнять задания!")
            return
            
        if game['tasks']:
            completed_task = game['tasks'].pop(0)
            bot.reply_to(message, f"✅ Задание '{completed_task}' выполнено!\n"
                                f"Осталось заданий: {len(game['tasks'])}")
            
            if not game['tasks']:
                end_game(room_code, "crewmate")
        else:
            bot.reply_to(message, "❌ Все задания уже выполнены!")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при выполнении задания: {e}")

# Обработка локации
@bot.message_handler(content_types=['location'])
def handle_location(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        
        if user_id not in user_rooms:
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games or games[room_code]['state'] != 'playing':
            return
            
        game = games[room_code]
        player_data = game['players'][username]
        
        if not player_data['alive']:
            bot.reply_to(message, "💀 Ты мертв и не можешь двигаться!")
            return
        
        # Сохраняем локацию игрока
        lat = message.location.latitude
        lon = message.location.longitude
        player_data['location'] = {'lat': lat, 'lon': lon}
        
        # Проверяем убийства (если игрок - предатель)
        if player_data['role'] == 'impostor':
            check_kills(room_code, username, lat, lon)
        
        bot.reply_to(message, "📍 Локация обновлена!")
    except Exception as e:
        print(f"Ошибка обработки локации: {e}")

# Проверить возможность убийства
def check_kills(room_code, killer_username, killer_lat, killer_lon):
    try:
        game = games[room_code]
        
        for victim_username, victim_data in game['players'].items():
            if (victim_username != killer_username and 
                victim_data['alive'] and 
                victim_data['location'] and
                victim_data['role'] == 'crewmate'):
                
                victim_lat = victim_data['location']['lat']
                victim_lon = victim_data['location']['lon']
                
                distance = calculate_distance(killer_lat, killer_lon, victim_lat, victim_lon)
                
                if distance < 5:
                    # Совершаем убийство
                    victim_data['alive'] = False
                    
                    killer_id = game['players'][killer_username]['user_id']
                    victim_id = victim_data['user_id']
                    
                    if killer_id:
                        bot.send_message(killer_id, f"🔪 Ты убил @{victim_username}!")
                    if victim_id:
                        bot.send_message(victim_id, f"💀 Тебя убил предатель! Ты теперь призрак.")
                    
                    # Сообщаем всем об убийстве
                    for uid, room in user_rooms.items():
                        if room == room_code:
                            try:
                                bot.send_message(uid, f"⚰️ @{victim_username} был убит! Начинаем голосование!")
                            except:
                                pass
                    
                    start_voting(room_code)
                    break
    except Exception as e:
        print(f"Ошибка проверки убийств: {e}")

# Начать голосование
def start_voting(room_code):
    try:
        game = games[room_code]
        game['state'] = 'voting'
        game['votes'] = {}
        
        alive_players = [p for p, data in game['players'].items() if data['alive']]
        
        for uid, room in user_rooms.items():
            if room == room_code:
                try:
                    markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
                    for player in alive_players:
                        markup.add(types.KeyboardButton(f"🗳️ {player}"))
                    
                    bot.send_message(uid, 
                                   "🗳️ ГОЛОСОВАНИЕ!\n\n"
                                   "Кто по-твоему предатель? Выбери игрока:",
                                   reply_markup=markup)
                except Exception as e:
                    print(f"Не удалось отправить сообщение о голосовании: {e}")
    except Exception as e:
        print(f"Ошибка начала голосования: {e}")

# Обработка голосов
@bot.message_handler(func=lambda message: message.text.startswith("🗳️"))
def handle_vote(message):
    try:
        user_id = message.from_user.id
        
        if user_id not in user_rooms:
            return
            
        room_code = user_rooms[user_id]
        
        if room_code not in games or games[room_code]['state'] != 'voting':
            return
            
        game = games[room_code]
        username = message.from_user.username
        
        if not game['players'][username]['alive']:
            bot.reply_to(message, "💀 Мертвые не могут голосовать!")
            return
        
        voted_player = message.text.replace("🗳️ ", "").strip()
        if voted_player not in game['players']:
            bot.reply_to(message, "❌ Такого игрока нет!")
            return
        
        # Запрещаем голосовать за себя
        if voted_player == username:
            bot.reply_to(message, "❌ Нельзя голосовать против самого себя!")
            return
            
        game['votes'][username] = voted_player
        bot.reply_to(message, f"✅ Ты проголосовал против @{voted_player}")
        
        # Проверяем все ли проголосовали
        alive_count = sum(1 for data in game['players'].values() if data['alive'])
        if len(game['votes']) == alive_count:
            finish_voting(room_code)
    except Exception as e:
        print(f"Ошибка обработки голоса: {e}")

# Завершить голосование
def finish_voting(room_code):
    try:
        game = games[room_code]
        
        vote_count = {}
        for voted_player in game['votes'].values():
            vote_count[voted_player] = vote_count.get(voted_player, 0) + 1
        
        if vote_count:
            ejected_player = max(vote_count.items(), key=lambda x: x[1])[0]
            game['players'][ejected_player]['alive'] = False
            
            # Сообщаем результат
            for uid, room in user_rooms.items():
                if room == room_code:
                    try:
                        markup = create_main_keyboard()
                        bot.send_message(uid, f"🚪 Игрок @{ejected_player} был изгнан!",
                                       reply_markup=markup)
                    except Exception as e:
                        print(f"Не удалось отправить результат голосования: {e}")
            
            # Проверяем условия победы
            check_win_conditions(room_code)
        else:
            for uid, room in user_rooms.items():
                if room == room_code:
                    try:
                        markup = create_main_keyboard()
                        bot.send_message(uid, "🤷 Никто не был изгнан. Игра продолжается!",
                                       reply_markup=markup)
                    except Exception as e:
                        print(f"Не удалось отправить результат голосования: {e}")
        
        game['state'] = 'playing'
    except Exception as e:
        print(f"Ошибка завершения голосования: {e}")

# Проверить условия победы
def check_win_conditions(room_code):
    try:
        game = games[room_code]
        
        alive_players = [p for p, data in game['players'].items() if data['alive']]
        impostors_alive = [p for p in alive_players if game['players'][p]['role'] == 'impostor']
        crewmates_alive = [p for p in alive_players if game['players'][p]['role'] == 'crewmate']
        
        if not impostors_alive:
            end_game(room_code, "crewmate")
        elif len(impostors_alive) >= len(crewmates_alive):
            end_game(room_code, "impostor")
        elif not game['tasks']:
            end_game(room_code, "crewmate")
    except Exception as e:
        print(f"Ошибка проверки условий победы: {e}")

# Завершить игру
def end_game(room_code, winner):
    try:
        game = games[room_code]
        game['state'] = 'finished'
        
        winner_text = "МИРНЫЕ ЖИТЕЛИ" if winner == "crewmate" else "ПРЕДАТЕЛИ"
        
        for uid, room in user_rooms.items():
            if room == room_code:
                try:
                    result_message = f"🎉 ИГРА ОКОНЧЕНА!\n🏆 ПОБЕДИЛИ: {winner_text}\n\n"
                    result_message += "📊 Результаты:\n"
                    
                    for player, data in game['players'].items():
                        status = "✅ Жив" if data['alive'] else "💀 Мертв"
                        role = "🔪 Предатель" if data['role'] == 'impostor' else "👨‍🚀 Мирный"
                        result_message += f"{status} - @{player} ({role})\n"
                    
                    markup = types.ReplyKeyboardRemove()
                    bot.send_message(uid, result_message, reply_markup=markup)
                except Exception as e:
                    print(f"Не удалось отправить результаты игры: {e}")
        
        # Очищаем игру
        if room_code in games:
            del games[room_code]
        
        # Удаляем пользователей из комнаты
        users_to_remove = [uid for uid, room in user_rooms.items() if room == room_code]
        for uid in users_to_remove:
            del user_rooms[uid]
    except Exception as e:
        print(f"Ошибка завершения игры: {e}")

if __name__ == "__main__":
    print("🟢 Бот запущен с авто-обновлением локации!")
    print("📍 Локация автоматически обновляется каждые 30 секунд")
    print("Найди своего бота в Telegram и напиши /start")
    
    try:
        bot.polling(none_stop=True, interval=0)
    except Exception as e:
        print(f"Ошибка запуска бота: {e}")