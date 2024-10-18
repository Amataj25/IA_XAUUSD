import yfinance as yf
import pandas as pd
import joblib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# Cargar el modelo entrenado
model = joblib.load('../models/best_random_forest_model_combined.pkl')

def get_real_time_data(ticker):
    data = yf.download(tickers=ticker, period='1d', interval='1m')
    return data

def process_and_predict(data):
    # Renombrar columnas para que coincidan con las del modelo entrenado
    data = data.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'})
    X_real_time = data[['open', 'high', 'low', 'volume']]
    X_real_time.loc[:, 'value'] = 5  # Valor arbitrario para PIB
    X_real_time = X_real_time.dropna()
    predictions = model.predict(X_real_time)
    data['Prediction'] = predictions
    return data

def send_notification(subject, body, to):
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    smtp_user = 'tu_correo@gmail.com'
    smtp_password = 'CONTRASEÑA_DE_APLICACIÓN'  # Reemplaza por la contraseña de aplicación generada
    msg = MIMEText(body, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = smtp_user
    msg['To'] = to
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to, msg.as_string())

ticker = 'GC=F'
real_time_data = get_real_time_data(ticker)
real_time_data = process_and_predict(real_time_data)

# Generar una señal y enviar notificación si hay una nueva señal
signal = real_time_data['Prediction'].iloc[-1]
subject = 'Alerta de Trading en Tiempo Real'
body = f'Se ha generado una nueva señal de trading: {signal}.'
to = 'destinatario@gmail.com'
send_notification(subject, body, to)

print(real_time_data[['open', 'high', 'low', 'close', 'Prediction']].tail())
