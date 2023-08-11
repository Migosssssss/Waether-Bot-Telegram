import os
import logging
import requests
import datetime
import ephem
from functools import lru_cache
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import executor

TELEGRAM_API_TOKEN = ''
WEATHER_API_KEY = 'a0dd09dd0d80fbe03d16062a53d'

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_API_TOKEN)
dp = Dispatcher(bot)

BASE_URL = "http://api.openweathermap.org/data/2.5/"
UNITS = "metric"
CACHE_SIZE = 128
CACHE_TIME = 600

@lru_cache(maxsize=CACHE_SIZE, typed=False)
def cached_request(url: str, cache_time: int = CACHE_TIME):
    response = requests.get(url)
    response.raise_for_status()
    
    response_data = response.json()
    response_data['_request_time'] = datetime.datetime.utcnow()
    
    return response_data

def get_weather_data(city, endpoint, cache_time=CACHE_TIME):
    url = f'{BASE_URL}{endpoint}?q={city}&appid={WEATHER_API_KEY}&units={UNITS}'
    now = datetime.datetime.utcnow()
    
    try:
        data = cached_request(url)
        
        if (now - data['_request_time']) > datetime.timedelta(seconds=cache_time):
            data = cached_request(url, cache_time)
    except requests.exceptions.RequestException as e:
        logging.error(e)
        raise RuntimeError("Ошибка получения данных.")
    
    return data

async def start(message: types.Message):
    await message.reply("Привет! Я бот-погодник. Введите /help для списка доступных команд.")

async def help_command(message: types.Message):
    help_text = (
        "Привет! Я могу помочь вам с информацией о погоде, а также предоставить обменные курсы на основе доллара США. "
        "Вот список доступных команд:\n\n"
        "/start - начать работу со мной\n"
        "/help - показать этот список команд\n"
        "/weather <город> - текущая погода в выбранном городе\n"
        "/forecast <город> - прогноз погоды на ближайшие 3 дня в выбранном городе\n"
        "/sunrise_sunset <город> - время восхода и заката солнца в выбранном городе\n"
        "/humidity <город> - текущая влажность воздуха в выбранном городе\n"
        "/wind <город> - текущая скорость ветра в выбранном городе\n"
        "/cloudiness <город> - текущая облачность в выбранном городе\n"
        "/uvi <город> - текущий ультрафиолетовый индекс в выбранном городе\n"
        "/minutely_precipitation <город> - прогноз осадков в течение следующих 60 минут в выбранном городе\n"
        "/exchange_rates - актуальные обменные курсы на основе доллара США\n"
        "/convert <сумма> <из_валюты> <в_валюту> - конвертация суммы из одной валюты в другую на основе текущих обменных курсов\n\n"
        "Введите команду, и я предоставлю вам нужную информацию!"
    )
    await message.reply(help_text)


async def weather(message: types.Message):
    city = message.text[9:]
    if not city:
        await message.reply("Введите /weather <город> для получения информации о погоде.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    text = format_weather_data(weather_data, city)
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

async def sunrise_sunset(message: types.Message):
    city = message.text[15:]
    if not city:
        await message.reply("Введите /sunrise_sunset <город> для получения информации о восходе и закате солнца.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    sunrise = weather_data['sys']['sunrise']
    sunset = weather_data['sys']['sunset']

    sunrise = datetime.datetime.utcfromtimestamp(sunrise).strftime('%H:%M')
    sunset = datetime.datetime.utcfromtimestamp(sunset).strftime('%H:%M')

    info = f"🌅 Восход: {sunrise}\n🌇 Закат: {sunset}"
    await message.reply(info)

def format_forecast_info(forecast_data, city):
    output_lines = [f"🌤 Прогноз погоды в *{city}* на 3 дня:\n"]
    days = {i: [] for i in range(1, 4)}

    for entry in forecast_data['list']:
        timestamp = entry['dt']
        date = datetime.datetime.utcfromtimestamp(timestamp).date()
        day_diff = (date - datetime.datetime.utcnow().date()).days

        if day_diff in days:
            days[day_diff].append(entry)

    for day, weather_entries in days.items():
        daily_weather = min(weather_entries, key=lambda x: x['main']['temp'])
        output_lines.append(format_weather_data(daily_weather, city, day))

    return "\n\n".join(output_lines)

async def forecast(message: types.Message):
    city = message.text[10:]
    if not city:
        await message.reply("Введите /forecast <город> для получения прогноза погоды на 3 дня.")
        return

    try:
        forecast_data = get_weather_data(city, "forecast")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    text = format_forecast_info(forecast_data, city)
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)

def format_weather_data(weather_data, city, day=None):
    main = weather_data['main']
    weather = weather_data['weather'][0]

    temp = main['temp']
    feels_like = main['feels_like']
    temp_min = main['temp_min']
    temp_max = main['temp_max']
    pressure = main['pressure']
    humidity = main['humidity']

    wind = weather_data['wind']
    wind_speed = wind['speed']
    wind_deg = wind['deg']

    weather_desc = weather['description'].capitalize()

    if day is None:
        day_info = ""
    else:
        day_info = f" для *Дня {day}*"

    info = (
        f"🌍 Погода в *{city}*{day_info}\n\n"
        f"☁️ {weather_desc}\n"
        f"🌡 Температура: {temp}°C (ощущается как {feels_like}°C)\n"
        f"↕️ Мин: {temp_min}°C, Макс: {temp_max}°C\n"
        f"📊 Давление: {pressure} hPa\n"
        f"💧 Влажность: {humidity}%\n"
        f"🌬 Ветер: {wind_speed} м/с, {wind_deg}°"
    )
    return info

async def exchange_rates(message: types.Message):
    url = "https://api.exchangerate-api.com/v4/latest/USD"

    try:
        data = cached_request(url, CACHE_TIME)
    except requests.exceptions.RequestException as e:
        logging.error(e)
        await message.reply("Ошибка при получении данных по курсу валют. Попробуйте еще раз позже.")
        return

    info = format_exchange_rates_info(data)
    await message.reply(info)

def format_exchange_rates_info(data):
    output = ["Курс валют на основе {}:\n\n".format(data['base'])]

    for currency, rate in data['rates'].items():
        if currency in ["EUR", "GBP", "JPY", "RUB", "CNY"]:
            output.append("{}: {:.2f}".format(currency, rate))

    return "\n".join(output)

def get_exchange_rate(from_currency, to_currency):
    url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
    data = cached_request(url, CACHE_TIME)
    return data['rates'][to_currency]

def convert_currency(amount, from_currency, to_currency):
    exchange_rate = get_exchange_rate(from_currency, to_currency)
    return amount * exchange_rate

async def currency_conversion(message: types.Message):
    arguments = message.text.split()
    if len(arguments) != 4:
        await message.reply("Используйте следующий формат: `/convert <сумма> <из_валюты> <в_валюту>`")
        return

    _, amount, from_currency, to_currency = arguments

    try:
        amount = float(amount)
        converted_amount = convert_currency(amount, from_currency, to_currency)
        result = f"Конвертация: {amount} {from_currency} ➡️ {converted_amount:.2f} {to_currency}"
        await message.reply(result)
    except ValueError:
        await message.reply("Укажите правильную сумму для конвертации.")
    except KeyError:
        await message.reply("Укажите правильные коды валют для конвертации. Например: USD, EUR, GBP.")
async def on_any_message(message: types.Message):
    logging.info(f"Received message:\n\n{message.text}")

async def humidity(message: types.Message):
    city = message.text[9:]
    if not city:
        await message.reply("Введите /humidity <город> для получения информации о текущей влажности.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    humidity = weather_data["main"]["humidity"]
    await message.reply(f"💧 Влажность в {city}: {humidity}%")

dp.register_message_handler(humidity, commands=['humidity'])

async def wind(message: types.Message):
    city = message.text[6:]
    if not city:
        await message.reply("Введите /wind <город> для получения информации о текущей скорости ветра.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    wind_speed = weather_data["wind"]["speed"]
    await message.reply(f"🌬 Скорость ветра в {city}: {wind_speed} м/с")

dp.register_message_handler(wind, commands=['wind'])

async def cloudiness(message: types.Message):
    city = message.text[12:]
    if not city:
        await message.reply("Введите /cloudiness <город> для получения информации о текущей облачности.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    clouds = weather_data["clouds"]["all"]
    await message.reply(f"☁️ Облачность в {city}: {clouds}%")

dp.register_message_handler(cloudiness, commands=['cloudiness'])

async def uvi(message: types.Message):
    city = message.text[5:]
    if not city:
        await message.reply("Введите /uvi <город> для получения информации о текущем ультрафиолетовом индексе.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
        lat = weather_data["coord"]["lat"]
        lon = weather_data["coord"]["lon"]
        
        url = f'{BASE_URL}uvi?appid={WEATHER_API_KEY}&lat={lat}&lon={lon}'
        uvi_data = cached_request(url)
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    uvi_value = uvi_data["value"]
    await message.reply(f"🌞 Ультрафиолетовый индекс (UVI) в {city}: {uvi_value}")

dp.register_message_handler(uvi, commands=['uvi'])

async def minutely_precipitation(message: types.Message):
    city = message.text[21:]
    if not city:
        await message.reply("Введите /minutely_precipitation <город> для получения информации о минутном прогнозе осадков в течение следующих 60 минут.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
        lat = weather_data["coord"]["lat"]
        lon = weather_data["coord"]["lon"]

        url = f'{BASE_URL}onecall?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units={UNITS}&exclude=current,hourly,daily,alerts'
        minutely_data = cached_request(url)
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    minutely_precipitation = minutely_data["minutely"]

    reply_text = f"🌧 Минутный прогноз осадков в {city} на следующие 60 минут:\n\n"
    for minute_data in minutely_precipitation:
        dt = datetime.datetime.utcfromtimestamp(minute_data["dt"]).strftime("%H:%M")
        precipitation = minute_data["precipitation"]
        reply_text += f"{dt}: {precipitation} мм\n"

    await message.reply(reply_text)

dp.register_message_handler(minutely_precipitation, commands=['minutely_precipitation'])

def get_phase_of_moon(city):
    try:
        weather_data = get_weather_data(city, "weather")
        dt = datetime.datetime.utcfromtimestamp(weather_data["dt"])
    except RuntimeError as e:
        logging.error(e)
        raise

    observer = ephem.city(city)
    moon = ephem.Moon(observer)
    phase = moon.moon_phase
    
    return phase, dt

async def moon_phase(message: types.Message):
    city = message.text[11:]
    if not city:
        await message.reply("Введите /moon_phase <город> для получения информации о текущей фазе луны.")
        return

    try:
        phase, dt = get_phase_of_moon(city)
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    info = f"🌖 Фаза луны в {city} по состоянию на {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC: {phase:.2f}"
    await message.reply(info)

dp.register_message_handler(moon_phase, commands=['moon_phase'])

async def feels_like(message: types.Message):
    city = message.text[11:]
    if not city:
        await message.reply("Введите /feels_like <город> для получения информации о том, какая температура ощущается на улице.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    feels_like_temperature = weather_data["main"]["feels_like"]
    await message.reply(f"🌡 Ощущаемая температура в {city}: {feels_like_temperature}°C")

dp.register_message_handler(feels_like, commands=['feels_like'])

async def visibility(message: types.Message):
    city = message.text[11:]
    if not city:
        await message.reply("Введите /visibility <город> для получения информации о видимости.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    visibility = weather_data["visibility"]
    await message.reply(f"👁 Видимость в {city}: {visibility} метров")

dp.register_message_handler(visibility, commands=['visibility'])

async def air_pressure(message: types.Message):
    city = message.text[13:]
    if not city:
        await message.reply("Введите /air_pressure <город> для получения информации о текущем атмосферном давлении.")
        return

    try:
        weather_data = get_weather_data(city, "weather")
    except RuntimeError as e:
        logging.error(e)
        await message.reply(str(e))
        return

    pressure = weather_data["main"]["pressure"]
    await message.reply(f"📊 Атмосферное давление в {city}: {pressure} hPa")

dp.register_message_handler(air_pressure, commands=['air_pressure'])



dp.register_message_handler(start, commands=['start'])
dp.register_message_handler(help_command, commands=['help'])
dp.register_message_handler(weather, commands=['weather'])
dp.register_message_handler(sunrise_sunset, commands=['sunrise_sunset'])
dp.register_message_handler(forecast, commands=['forecast'])
dp.register_message_handler(exchange_rates, commands=['exchange_rates'])
dp.register_message_handler(currency_conversion, commands=['convert'])
dp.register_message_handler(on_any_message, content_types=['text'])
dp.register_message_handler(humidity, commands=['humidity'])
dp.register_message_handler(wind, commands=['wind'])
dp.register_message_handler(cloudiness, commands=['cloudiness'])
dp.register_message_handler(uvi, commands=['uvi'])
dp.register_message_handler(minutely_precipitation, commands=['minutely_precipitation'])


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
