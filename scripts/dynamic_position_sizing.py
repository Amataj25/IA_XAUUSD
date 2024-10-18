# dynamic_position_sizing.py

import MetaTrader5 as mt5
import logging

logger = logging.getLogger(__name__)

def calculate_dynamic_lot_size(symbol, account_balance, risk_percentage, sl_pips, target_profit):
    """
    Calcula el tamaño del lote dinámicamente basado en el balance de la cuenta y el riesgo deseado.
    """
    risk_amount = account_balance * (risk_percentage / 100)
    symbol_info = mt5.symbol_info(symbol)
    
    if symbol_info is None:
        logger.error(f"No se pudo obtener información para el símbolo {symbol}")
        return None

    pip_value = symbol_info.trade_tick_value
    contract_size = symbol_info.trade_contract_size
    
    lot_step = symbol_info.volume_step
    min_lot = symbol_info.volume_min
    max_lot = symbol_info.volume_max

    lot_size = risk_amount / (sl_pips * pip_value * contract_size)
    min_profit_lot = target_profit / (sl_pips * 3 * pip_value * contract_size)
    
    lot_size = max(lot_size, min_profit_lot)
    lot_size = min(max(round(lot_size / lot_step) * lot_step, min_lot), max_lot)

    logger.info(f"Lote calculado: {lot_size} (balance: {account_balance}, riesgo: {risk_percentage}%, SL: {sl_pips} pips)")
    return lot_size

def calculate_dynamic_sl_tp(symbol, current_price, atr, entry_type):
    """
    Calcula los niveles de Stop Loss y Take Profit dinámicamente basados en el ATR.
    """
    symbol_info = mt5.symbol_info(symbol)
    
    if symbol_info is None:
        logger.error(f"No se pudo obtener información para el símbolo {symbol}")
        return None, None

    sl_factor = 2
    tp_factor = 6
    
    point = symbol_info.point
    digits = symbol_info.digits

    if entry_type == 'buy':
        sl = round(current_price - (atr * sl_factor), digits)
        tp = round(current_price + (atr * tp_factor), digits)
    else:  # 'sell'
        sl = round(current_price + (atr * sl_factor), digits)
        tp = round(current_price - (atr * tp_factor), digits)
    
    logger.info(f"SL calculado: {sl}, TP calculado: {tp} (ATR: {atr}, tipo de entrada: {entry_type})")
    return sl, tp