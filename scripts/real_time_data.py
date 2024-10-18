import yfinance as yf
import pandas as pd

def get_real_time_data(ticker):
    # Obtener datos en tiempo real
    data = yf.download(tickers=ticker, period='1d', interval='1m')
    return data

# Ejemplo: obtener datos de XAU/USD
real_time_data = get_real_time_data('GC=F')
print(real_time_data.head())
