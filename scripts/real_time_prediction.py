import yfinance as yf
import pandas as pd
import joblib
from datetime import datetime

# Cargar el modelo entrenado
model = joblib.load('../models/best_random_forest_model_combined.pkl')

def get_real_time_data(ticker):
    data = yf.download(tickers=ticker, period='1d', interval='1m')
    return data

def process_and_predict(data):
    # Seleccionar las características necesarias
    X_real_time = data[['Open', 'High', 'Low', 'Volume']]

    # Simular una columna de PIB para las predicciones en tiempo real
    X_real_time['value'] = 5  # Valor arbitrario para PIB
    X_real_time = X_real_time.dropna()

    # Predecir con el modelo entrenado
    predictions = model.predict(X_real_time)
    data['Prediction'] = predictions

    return data

# Obtener datos en tiempo real
ticker = 'GC=F'  # Ejemplo con XAU/USD
real_time_data = get_real_time_data(ticker)

# Procesar y predecir
real_time_data = process_and_predict(real_time_data)
print(real_time_data[['Open', 'High', 'Low', 'Close', 'Prediction']].tail())
