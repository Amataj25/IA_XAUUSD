# trend_analysis.py

import pandas as pd

def analyze_trend(data):
    """
    Analiza la tendencia usando una media móvil simple.
    """
    sma_short = data['close'].rolling(window=20).mean()
    sma_long = data['close'].rolling(window=50).mean()
    
    if sma_short.iloc[-1] > sma_long.iloc[-1]:
        return 'up'
    elif sma_short.iloc[-1] < sma_long.iloc[-1]:
        return 'down'
    else:
        return 'neutral'

def confirm_trend_multiple_timeframes(data_1h, data_4h):
    """
    Confirma la tendencia en los timeframes de 1 hora y 4 horas.
    """
    trend_1h = analyze_trend(data_1h)
    trend_4h = analyze_trend(data_4h)
    
    if trend_1h == trend_4h:
        return trend_1h
    else:
        return None