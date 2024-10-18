# liquidity_analysis.py

import pandas as pd
import logging

logger = logging.getLogger(__name__)

def identify_liquidity_levels(data, lookback=20):
    """
    Identifica niveles de liquidez basados en máximos y mínimos recientes.
    """
    highs = data['high'].rolling(window=lookback).max()
    lows = data['low'].rolling(window=lookback).min()
    
    recent_high = highs.iloc[-1]
    recent_low = lows.iloc[-1]
    
    previous_day_high = data['high'].shift(1).iloc[-1]
    previous_day_low = data['low'].shift(1).iloc[-1]
    
    levels = {
        'recent_high': recent_high,
        'recent_low': recent_low,
        'previous_day_high': previous_day_high,
        'previous_day_low': previous_day_low
    }
    
    logger.info(f"Niveles de liquidez identificados: {levels}")
    return levels

def detect_liquidity_sweep(current_price, liquidity_levels, tolerance=0.0005):
    """
    Detecta si ha ocurrido un barrido de liquidez.
    """
    for level_name, level_price in liquidity_levels.items():
        if abs(current_price - level_price) < (level_price * tolerance):
            logger.info(f"Barrido de liquidez detectado en {level_name}: {level_price}")
            return True, level_name
    
    return False, None

def analyze_liquidity(data, current_price):
    """
    Analiza la liquidez del mercado y detecta barridos.
    """
    liquidity_levels = identify_liquidity_levels(data)
    sweep_detected, swept_level = detect_liquidity_sweep(current_price, liquidity_levels)
    
    return liquidity_levels, sweep_detected, swept_level