import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import logging

def get_atr(symbol, timeframe=mt5.TIMEFRAME_H1, period=14):
    try:
        logging.info(f"Intentando obtener datos para {symbol} en timeframe {timeframe}")
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period * 2)
        if rates is None or len(rates) < period + 1:
            logging.warning(f"No hay suficientes datos para el cálculo de ATR en timeframe {timeframe}")
            return None
        
        data = pd.DataFrame(rates)
        data['high-low'] = data['high'] - data['low']
        data['high-close'] = abs(data['high'] - data['close'].shift(1))
        data['low-close'] = abs(data['low'] - data['close'].shift(1))
        data['tr'] = data[['high-low', 'high-close', 'low-close']].max(axis=1)
        atr = data['tr'].rolling(window=period).mean().iloc[-1]
        logging.info(f"ATR calculado para {symbol} en timeframe {timeframe}: {atr}")
        return atr
    except Exception as e:
        logging.error(f"Error al calcular ATR para {symbol} en timeframe {timeframe}: {e}")
        return None

def analyze_market_conditions(symbol):
    timeframes = [mt5.TIMEFRAME_W1, mt5.TIMEFRAME_D1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_H1]
    timeframe_names = ['Semanal', 'Diario', '4 Horas', '1 Hora']
    volatility_thresholds = [70, 30, 15, 8]  # Ajusta estos valores según sea necesario
    
    market_conditions = {}
    high_volatility_count = 0
    
    for tf, threshold, name in zip(timeframes, volatility_thresholds, timeframe_names):
        atr = get_atr(symbol, tf)
        if atr is not None:
            volatility = "Alta" if atr > threshold else "Normal"
            if volatility == "Alta":
                high_volatility_count += 1
            market_conditions[name] = {
                "ATR": atr,
                "Volatilidad": volatility
            }
            logging.info(f"{name}: ATR = {atr}, Volatilidad = {volatility}")
        else:
            market_conditions[name] = {
                "ATR": None,
                "Volatilidad": "Desconocida"
            }
            logging.warning(f"No se pudo calcular ATR para {symbol} en timeframe {name}")
    
    # Determinar el timeframe más adecuado para operar
    if high_volatility_count >= 3:
        recommended_timeframe = "Semanal"
    elif high_volatility_count == 2:
        recommended_timeframe = "Diario"
    elif market_conditions['4 Horas']['Volatilidad'] == "Normal":
        recommended_timeframe = "4 Horas"
    elif market_conditions['1 Hora']['Volatilidad'] == "Normal":
        recommended_timeframe = "1 Hora"
    else:
        recommended_timeframe = None
    
    return market_conditions, recommended_timeframe, high_volatility_count >= 2

def is_high_volatility(symbol, thresholds):
    _, _, is_volatile = analyze_market_conditions(symbol)
    return is_volatile

def get_recommended_timeframe(symbol):
    _, recommended_timeframe, _ = analyze_market_conditions(symbol)
    return recommended_timeframe