import yfinance as yf
import pandas as pd
import joblib
import requests

# Cargar el modelo entrenado
model = joblib.load('../models/best_random_forest_model_combined.pkl')

def get_real_time_data(ticker):
    data = yf.download(tickers=ticker, period='1d', interval='1m')
    return data

def process_and_predict(data):
    data = data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'})
    X_real_time = data[['open', 'high', 'low', 'volume']].copy()
    X_real_time['value'] = 5  # Valor arbitrario para PIB
    X_real_time = X_real_time.dropna()
    predictions = model.predict(X_real_time)
    data['Prediction'] = predictions
    return data

def send_telegram_message(token, chat_id, message):
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    requests.post(url, data=payload)

# Variables de estado para trailing stop
entry_price = None
trailing_stop_loss = None

def update_trailing_stop(current_price, direction):
    global trailing_stop_loss
    if direction == 'buy':
        if trailing_stop_loss is None or current_price > trailing_stop_loss:
            trailing_stop_loss = current_price * 0.99  # Ejemplo: 1% por debajo del precio actual
    elif direction == 'sell':
        if trailing_stop_loss is None or current_price < trailing_stop_loss:
            trailing_stop_loss = current_price * 1.01  # Ejemplo: 1% por encima del precio actual

ticker = 'GC=F'
real_time_data = get_real_time_data(ticker)
real_time_data = process_and_predict(real_time_data)

# Generar una señal
signal = real_time_data['Prediction'].iloc[-1]
current_price = real_time_data['open'].iloc[-1]

if entry_price is None:
    entry_price = current_price

# Determinar la dirección de la señal
if signal > entry_price:
    direction = 'buy'
    subject = 'Señal de Compra'
    update_trailing_stop(current_price, direction)
    body = f'Se ha generado una señal de compra a {entry_price}. Trailing Stop Loss: {trailing_stop_loss}.'
else:
    direction = 'sell'
    subject = 'Señal de Venta'
    update_trailing_stop(current_price, direction)
    body = f'Se ha generado una señal de venta a {entry_price}. Trailing Stop Loss: {trailing_stop_loss}.'

telegram_token = '7635259719:AAFnWapsNFwdlJqSOEIbJJYDSv5wzS9egbk'
chat_id = '1434149527'
send_telegram_message(telegram_token, chat_id, body)

print(real_time_data[['open', 'high', 'low', 'Prediction']].tail())
