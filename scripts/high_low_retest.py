import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def identify_highs_lows(data: pd.DataFrame, lookback: int = 10) -> pd.DataFrame:
    data['high_point'] = data['high'].rolling(window=lookback, center=True).max()
    data['low_point'] = data['low'].rolling(window=lookback, center=True).min()
    return data

def calculate_atr(data: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = data['high'] - data['low']
    high_close = np.abs(data['high'] - data['close'].shift())
    low_close = np.abs(data['low'] - data['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.rolling(period).mean()

def check_break_and_retest(data: pd.DataFrame, atr: pd.Series, breakout_threshold: float = 0.001, retest_threshold: float = 0.0003) -> tuple:
    if len(data) < 3:
        return None, None, 0

    last_candle = data.iloc[-1]
    prev_candle = data.iloc[-2]
    
    breakout_size = atr.iloc[-1] * breakout_threshold
    retest_size = atr.iloc[-1] * retest_threshold
    
    # Ruptura alcista
    if last_candle['close'] > prev_candle['high_point'] + breakout_size:
        if last_candle['low'] <= prev_candle['high_point'] + retest_size:
            # Verificar mecha fuerte
            if (last_candle['high'] - last_candle['close']) > (last_candle['close'] - last_candle['open']) * 1.5:  # Cambiado a 1.5
                # Verificar retroceso no mayor al 50%
                if last_candle['close'] > prev_candle['high_point'] + (0.5 * (prev_candle['high_point'] - prev_candle['low_point'])):
                    return 'buy', last_candle['close'], (last_candle['close'] - prev_candle['high_point']) / atr.iloc[-1]
    
    # Ruptura bajista
    elif last_candle['close'] < prev_candle['low_point'] - breakout_size:
        if last_candle['high'] >= prev_candle['low_point'] - retest_size:
            # Verificar mecha fuerte
            if (last_candle['close'] - last_candle['low']) > (last_candle['open'] - last_candle['close']) * 1.5:  # Cambiado a 1.5
                # Verificar retroceso no mayor al 50%
                if last_candle['close'] < prev_candle['low_point'] - (0.5 * (prev_candle['high_point'] - prev_candle['low_point'])):
                    return 'sell', last_candle['close'], (prev_candle['low_point'] - last_candle['close']) / atr.iloc[-1]
    
    return None, None, 0

def identify_liquidity_levels(data: pd.DataFrame, lookback: int = 50) -> tuple:
    high_volume_levels = data[data['volume'] > data['volume'].rolling(lookback).mean() * 1.5]
    resistance = high_volume_levels['high'].max()
    support = high_volume_levels['low'].min()
    return support, resistance

def detect_liquidity_sweep(data: pd.DataFrame, support: float, resistance: float, atr: pd.Series) -> bool:
    last_candle = data.iloc[-1]
    if last_candle['low'] < support - 0.2 * atr.iloc[-1] and last_candle['close'] > support:
        return True
    if last_candle['high'] > resistance + 0.2 * atr.iloc[-1] and last_candle['close'] < resistance:
        return True
    return False

def analyze_high_low_retest(data: dict, timeframes: list) -> dict:
    results = {}
    try:
        for tf in timeframes:
            if tf in data and not data[tf].empty:
                tf_data = data[tf].copy()
                tf_data = identify_highs_lows(tf_data)
                atr = calculate_atr(tf_data)
                direction, price, strength = check_break_and_retest(tf_data, atr)
                support, resistance = identify_liquidity_levels(tf_data)
                liquidity_sweep = detect_liquidity_sweep(tf_data, support, resistance, atr)
                results[tf] = (direction, price, strength, support, resistance, liquidity_sweep)
            else:
                logger.warning(f"No hay datos disponibles para el timeframe {tf}")
        return results
    except Exception as e:
        logger.error(f"Error en el análisis de ruptura y retesteo: {e}")
        return {}

# Ejemplo de uso (comentado para evitar ejecución accidental)
"""
if __name__ == "__main__":
    # Asumiendo que tienes una función para obtener datos
    data = get_data_for_all_timeframes()  # Debes implementar esta función
    timeframes = [16408, 16388, 16385]  # Ejemplo: Diario, 4 Horas, 1 Hora
    results = analyze_high_low_retest(data, timeframes)
    for tf, result in results.items():
        print(f"Timeframe {tf}: {result}")
"""