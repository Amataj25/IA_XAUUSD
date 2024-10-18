import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def calculate_trend_line(data: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    if len(data) < period:
        logger.warning(f"Datos insuficientes para calcular la línea de tendencia. Se necesitan al menos {period} períodos. Datos disponibles: {len(data)}")
        data['trend_line'] = np.nan
        return data
    
    try:
        data['midpoint'] = (data['high'] + data['low']) / 2
        x = np.arange(len(data))
        y = data['midpoint'].values
        slope, intercept = np.polyfit(x, y, 1)
        data['trend_line'] = slope * x + intercept
        return data
    except Exception as e:
        logger.error(f"Error al calcular la línea de tendencia: {e}")
        data['trend_line'] = np.nan
        return data

def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def check_trend_break(data: pd.DataFrame, atr: pd.Series, tolerance: float = 0.01) -> tuple:
    if 'trend_line' not in data.columns or data['trend_line'].isnull().all():
        return None, 0
    
    last_close = data['close'].iloc[-1]
    last_trend_line_value = data['trend_line'].iloc[-1]
    
    if pd.isnull(last_trend_line_value):
        return None, 0
    
    break_size = atr.iloc[-1] * tolerance
    
    if last_close > last_trend_line_value + break_size:
        return 'buy', (last_close - last_trend_line_value) / atr.iloc[-1]
    
    elif last_close < last_trend_line_value - break_size:
        return 'sell', (last_trend_line_value - last_close) / atr.iloc[-1]
    
    return None, 0

def identify_key_levels(data: pd.DataFrame, lookback: int = 50) -> tuple:
    pivot_highs = data["high"].rolling(window=lookback).max().iloc[-1]
    pivot_lows = data["low"].rolling(window=lookback).min().iloc[-1]
    
    return pivot_lows, pivot_highs

def detect_trend_retest(data: pd.DataFrame, trend_line_value: float, atr: pd.Series) -> bool:
    last_candle_low = data["low"].iloc[-1]
    last_candle_close = data["close"].iloc[-1]
    
    retest_range_upward = trend_line_value + (atr.iloc[-1] * 0.3)
    
    # Verificar si el precio ha tocado la línea de tendencia y ha cerrado por encima
    if last_candle_low <= trend_line_value and last_candle_close > trend_line_value:
        return True
    
    # Verificar si el precio ha tocado el rango de retesteo permitido
    elif last_candle_low <= retest_range_upward and last_candle_close > trend_line_value:
        return True
    
    return False

def analyze_trend(data: dict, timeframes: list) -> dict:
    results = {}
    
    try:
        for tf in timeframes:
            if tf in data and not data[tf].empty:
                tf_data = data[tf].copy()
                tf_data = calculate_trend_line(tf_data)
                atr_values = calculate_atr(tf_data)
                
                direction_signal, strength_signal = check_trend_break(tf_data, atr_values)

                current_price_value = tf_data["close"].iloc[-1] if not tf_data.empty else None
                
                support_level_value , resistance_level_value= identify_key_levels(tf_data)

                trend_retest_signal_value= detect_trend_retest(tf_data , tf_data["trend_line"].iloc[-1],atr_values)

                results[tf] =(direction_signal,strength_signal,current_price_value,support_level_value,resistance_level_value , trend_retest_signal_value)

            else:
                logger.warning(f"No hay datos disponibles para el timeframe {tf}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error en el análisis de tendencia: {e}")
        return {}

# Ejemplo de uso (comentado para evitar ejecución accidental)
"""
if __name__ == "__main__":
    # Asumiendo que tienes una función para obtener datos
    data=get_data_for_all_timeframes() # Debes implementar esta función
    timeframes=[mt5.TIMEFRAME_W1 , mt5.TIMEFRAME_D1 , mt5.TIMEFRAME_H4 , mt5.TIMEFRAME_H1]
    results=analyze_trend(data,timeframes)
    for tf,result in results.items():
        print(f"Timeframe {tf}: {result}")
"""