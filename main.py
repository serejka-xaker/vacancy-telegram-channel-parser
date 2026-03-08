from telethon import TelegramClient
from datetime import datetime
import pytz
import pandas as pd
import re 
import configparser
from telethon.errors import SessionPasswordNeededError
import asyncio
from telethon.errors import FloodWaitError


def read_configuration():
    config = configparser.ConfigParser()
    config.read('Файлы/config.ini')

    # Получите api_id как целое число, чтобы избежать ошибок
    try:
        api_id = config.getint('Settings', 'api_id')
    except ValueError as e:
        print(f"Ошибка чтения api_id из файла: {e}")
        api_id = None

    api_hash = config.get('Settings', 'api_hash')

    # Проверка значения
    if api_id is None or not (1 <= api_id <= 2147483647):
        print("Ошибка: api_id должен быть в диапазоне от 1 до 2147483647.")
    return api_id,api_hash


def check_credentials(api_id, api_hash):
    try:
        client = TelegramClient('Файлы/anon', api_id, api_hash)
        client.start()
        return client  # Возвращаем клиент для дальнейшего использования
    except ValueError:
        print("Ошибка: Неверный формат api_id (должен быть целым числом) или api_hash.")
        return None
    except SessionPasswordNeededError:
        print("Требуется ввод пароля. Пожалуйста, введите пароль двухфакторной аутентификации.")
        return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def get_channels(file_path='Файлы/Опции.xlsx'):
    df = pd.read_excel(file_path)
    channels = df['Каналы'].dropna().astype(str).str.strip().tolist()
    return channels


def get_keywords(file_path='Файлы/Опции.xlsx'):
    df = pd.read_excel(file_path)
    keywords = df['Кодовые слова'].dropna().astype(str).str.strip().str.lower().tolist()  # Привели к нижнему регистру
    return keywords


def extract_words(text):
    words = re.findall(r'\b\w+\b', text.lower())
    return words


async def fetch_messages(channel_link, start_date, end_date,keywords):
    items = []
    print(f'Началась обработка канала {channel_link}')
    # Извлекаем юзернейм из ссылки
    try:
        match = re.search(r't.me/(.+)', channel_link.strip())
        if match:
            username = match.group(1)
            channel = await client.get_entity(username)  # Получаем объект канала по юзернейму

            try:
                async for message in client.iter_messages(channel,offset_date=end_date):
                    message_date = message.date if message.date.tzinfo else pytz.UTC.localize(message.date)
                    
                    if message_date < start_date:
                        break

                    # Проверяем наличие текста в сообщении
                    if start_date <= message_date <= end_date:

                        if not message.text:
                            continue
                        
                        # Получаем ссылку на сообщение
                        link = f"https://t.me/{username}/{message.id}"
                        
                        if message.post_author:
                            author = message.post_author
                        else:
                            author = '-'
                        
                        is_true_vacancy = False
                        message_words = extract_words(message.text.lower())
                        
                        is_true_vacancy = any(keyword in message_words for keyword in keywords)

                        if is_true_vacancy and len(message.text) > 350:
                            items.append([message_date.astimezone(pytz.UTC).replace(tzinfo=None), message.text, link,author])
                    
                    await asyncio.sleep(0.033)
            
            except FloodWaitError as ex:
                print(f"FloodWaitError: ожидание {ex.seconds} секунд.")
                await asyncio.sleep(ex.seconds)  # Ждем нужное время    
        
    except Exception as e:
        print(f'Ошибка при получении канала {username}: {str(e)}')
    
    return items


async def main():
    start_date_input = input("Введите начальную дату (ГГГГ-ММ-ДД): ")
    end_date_input = input("Введите конечную дату (ГГГГ-ММ-ДД): ")

    start_date = datetime.strptime(start_date_input, '%Y-%m-%d').replace(tzinfo=pytz.UTC)
    end_date = datetime.strptime(end_date_input, '%Y-%m-%d').replace(tzinfo=pytz.UTC).replace(hour=23, minute=59, second=59)

    keywords = get_keywords()
    channels = get_channels()

    all_items = []
    for channel in channels:
        try:
            messages = await fetch_messages(channel, start_date, end_date,keywords)
            all_items.extend(messages)
            print(f'Обработан канал: {channel}, найдено сообщений: {len(messages)}')
        except Exception as e:
            print(f'Ошибка при обработке канала {channel}: {str(e)}')

    if all_items:
        df = pd.DataFrame(all_items, columns=['Дата сообщения', 'Текст','Ссылка','Автор'])
        df.to_excel('Сообщения.xlsx', sheet_name='Сообщения', index=False)
        print('Использованные сообщения сохранены в Сообщения.xlsx')
    else:
        print('Сообщения не найдены.')



api_id,api_hash = read_configuration()
client = check_credentials(api_id, api_hash)
if client:
    with client:
        client.loop.run_until_complete(main())

