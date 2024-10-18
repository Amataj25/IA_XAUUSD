import time
import logging
import MetaTrader5 as mt5
import pandas as pd
from integration import initialize_mt5, shutdown_mt5, get_account_info
from strategy import get_real_time_data, process_and_predict
from volatility_filter import analyze_market_conditions
from risk_management import manage_risk
from monitoring import log_trade_result
from high_low_retest import analyze_high_low_retest
from trend_lines import analyze_trend
from telegram_notifications import send_telegram_message

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurar MetaTrader 5
ACCOUNT = 31302194  # Tu número de cuenta demo
PASSWORD = "L1m1c0y_198o"
SERVER = "Deriv-Demo"

# Parámetros de trading
SYMBOL = "XAUUSD"
INITIAL_LOT = 0.01  # Tamaño de lote inicial
SL_PIPS = 100  # Stop Loss en pips
TP_PIPS = 200  # Take Profit en pips
MAX_DAILY_PROFIT = 10  # Límite de ganancia diaria en dólares (ajustado)
MIN_PRICE_DIFFERENCE = 0.00005  # Diferencia mínima entre señal y precio actual (ajustado)

# Definir el umbral para la fuerza del retesteo (ajustado)
THRESHOLD = 30  

# Definir timeframes y umbrales de volatilidad
TIMEFRAMES = [mt5.TIMEFRAME_W1, mt5.TIMEFRAME_D1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_H1]

def check_daily_profit():
    today = pd.Timestamp.now().floor('D')
    deals = mt5.history_deals_get(date_from=today.to_pydatetime())
    if deals is None:
        logger.debug("No se encontraron operaciones.")
        return 0
    
    profit = sum(deal.profit for deal in deals)
    return profit

def adjust_lot_size(symbol, base_lot, account_balance, market_volatility):
    volatility_factor = 1 - (market_volatility / 100)  
    balance_factor = min(account_balance / 10000, 2)  
    
    adjusted_lot = base_lot * volatility_factor * balance_factor
    
    symbol_info = mt5.symbol_info(symbol)
    min_lot = symbol_info.volume_min
    max_lot = symbol_info.volume_max
    step = symbol_info.volume_step
    
    adjusted_lot = max(min_lot, min(adjusted_lot, max_lot))
    adjusted_lot = round(adjusted_lot / step) * step
    
    logger.info(f"Lote ajustado: {adjusted_lot} (base: {base_lot}, volatilidad: {market_volatility}, balance: {account_balance})")
    return adjusted_lot

def adjust_sl_tp(volatility, current_price, order_type):
    volatility_factor = volatility / 20
    symbol_info = mt5.symbol_info(SYMBOL)
    min_distance = symbol_info.point * symbol_info.trade_stops_level

    if order_type == mt5.ORDER_TYPE_BUY:
        adjusted_sl = max(min_distance, min(200, int(SL_PIPS * volatility_factor)))
        adjusted_tp = max(min_distance, min(400, int(TP_PIPS * volatility_factor)))
        
        sl_price = current_price - adjusted_sl * symbol_info.point
        tp_price = current_price + adjusted_tp * symbol_info.point
        
    else:  # SELL order
        adjusted_sl = max(min_distance, min(200, int(SL_PIPS * volatility_factor)))
        adjusted_tp = max(min_distance, min(400, int(TP_PIPS * volatility_factor)))
        
        sl_price = current_price + adjusted_sl * symbol_info.point
        tp_price = current_price - adjusted_tp * symbol_info.point

    logger.info(f"SL ajustado: {adjusted_sl}, TP ajustado: {adjusted_tp}")
    return sl_price, tp_price

def manage_open_positions(symbol):
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        for position in positions:
            logger.info(f"Posición abierta: {position.ticket}, Profit: {position.profit}")

def calculate_dynamic_support_resistance(data):
    support = min(data['low'])
    resistance = max(data['high'])
    return support, resistance

def calculate_retest_strength(current_price, previous_high, previous_low):
    range_high_low = previous_high - previous_low
    
    if range_high_low == 0:
        return 0
    
    strength = (current_price - previous_low) / range_high_low * 100
    return strength

def get_current_price(symbol):
    """
    Obtiene el precio actual utilizando diferentes métodos.
    """
    # Método 1: Usar symbol_info_tick
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None and tick.last > 0:
        return tick.last

    # Método 2: Obtener las últimas velas
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['close']

    # Método 3: Usar symbol_info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is not None and symbol_info.last > 0:
        return symbol_info.last

    return None

def place_order_with_sl_tp(symbol, order_type, lot_size, price, sl_price, tp_price):
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": 234000,
        "comment": "orden automática",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    logger.info(f"Enviando orden: Precio={price}, SL={sl_price}, TP={tp_price}")
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Error al enviar la orden: {result.retcode} - {result.comment}")
    
    return result

def log_trade_result(result):
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"Trade successful: Order {result.order}, Volume: {result.volume}, Price: {result.price}")
    else:
        logger.error(f"Trade failed: {result.retcode} - {result.comment}")

def main():
    lot = INITIAL_LOT

    if not initialize_mt5(ACCOUNT, PASSWORD, SERVER):
        logger.error("Failed to initialize MetaTrader5")
        return

    try:
        iteration = 0
        max_iterations = 10

        send_telegram_message("Bot de trading iniciado.")

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Iniciando ciclo de trading {iteration}/{max_iterations}")

            daily_profit = check_daily_profit()
            logger.info(f"Ganancia diaria actual: ${daily_profit:.2f}") 
            
            if daily_profit >= MAX_DAILY_PROFIT:
                logger.info(f"Límite diario alcanzado.")
                send_telegram_message(f"Límite diario alcanzado.")
                time.sleep(3600)
                continue

            market_conditions, recommended_timeframe, is_volatile = analyze_market_conditions(SYMBOL)
            logger.info(f"Condiciones del mercado: {market_conditions}")

            if recommended_timeframe is None:
                logger.info("No se recomienda operar.")
                send_telegram_message("No se recomienda operar.")
                time.sleep(3600)
                continue

            tf_map = {'Semanal': mt5.TIMEFRAME_W1, 'Diario': mt5.TIMEFRAME_D1, '4 Horas': mt5.TIMEFRAME_H4, '1 Hora': mt5.TIMEFRAME_H1}
            recommended_tf = tf_map[recommended_timeframe]

            real_time_data = {tf: get_real_time_data(SYMBOL, tf) for tf in TIMEFRAMES}
            processed_data = process_and_predict(real_time_data)

            if recommended_tf not in processed_data or 'Prediction' not in processed_data[recommended_tf].columns or processed_data[recommended_tf]['Prediction'].isnull().all():
                logger.warning(f"No hay predicción disponible para el timeframe {recommended_timeframe}")
                send_telegram_message(f"No hay predicción disponible para el timeframe {recommended_timeframe}.")
                continue
            
            support, resistance = calculate_dynamic_support_resistance(processed_data[recommended_tf])
            
            # Intentar obtener el precio actual con el nuevo método
            max_retries = 3
            current_price = None
            
            for attempt in range(max_retries):
                current_price = get_current_price(SYMBOL)
                if current_price is not None and current_price > 0:
                    break
                
                logger.warning("El precio actual es inválido o cero. Intentando obtener el precio nuevamente.")
                time.sleep(1)
            
            if current_price is None or current_price == 0:
                logger.warning("El precio actual sigue siendo inválido o cero. No se puede continuar.")
                continue
            
            logger.info(f"Precio actual obtenido: {current_price}")
            
            strength = calculate_retest_strength(current_price, resistance, support)

            account_info = get_account_info()
            if account_info:
                market_volatility = market_conditions[recommended_timeframe]['ATR']
                lot = adjust_lot_size(SYMBOL, INITIAL_LOT, account_info['balance'], market_volatility)
            else:
                logger.warning("No se pudo obtener información de la cuenta. Usando tamaño de lote inicial.")
                lot = INITIAL_LOT

            retest_results = analyze_high_low_retest(real_time_data, [recommended_tf])
            trend_results = analyze_trend(real_time_data, [recommended_tf])
            
            retest_direction, retest_price, retest_strength, support_level, resistance_level, liquidity_sweep_result = retest_results[recommended_tf]
            trend_direction, trend_strength, current_price_trend, trend_support_level, trend_resistance_level, trend_retest_result = trend_results[recommended_tf]
            
            signal = processed_data[recommended_tf]['Prediction'].iloc[-1]
            
            logger.info(f"Timeframe {recommended_timeframe}: retest_direction={retest_direction}, trend_direction={trend_direction}, current_price={current_price}, signal={signal}")
            
            symbol_info = mt5.symbol_info(SYMBOL)
            if symbol_info is None or symbol_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                logger.warning(f"Market is closed for {SYMBOL}.")
                continue

            if ((retest_direction == 'buy' or trend_direction == 'buy') and 
                (signal > current_price * (1 + MIN_PRICE_DIFFERENCE) or current_price > support * (1 + MIN_PRICE_DIFFERENCE))):
                logger.info(f"Condiciones de compra cumplidas.")
                sl_price, tp_price = adjust_sl_tp(market_conditions[recommended_timeframe]['ATR'], current_price, mt5.ORDER_TYPE_BUY)
                result = place_order_with_sl_tp(SYMBOL, mt5.ORDER_TYPE_BUY, lot, symbol_info.ask, sl_price, tp_price)
                log_trade_result(result)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    send_telegram_message(f"Orden de compra enviada ({recommended_timeframe})")
                else:
                    logger.error(f"Error al enviar orden de compra: {result.retcode} - {result.comment}")
                    
            elif ((retest_direction == 'sell' or trend_direction == 'sell') and 
                  (signal < current_price * (1 - MIN_PRICE_DIFFERENCE) or current_price < resistance * (1 - MIN_PRICE_DIFFERENCE))):
                logger.info(f"Condiciones de venta cumplidas.")
                sl_price, tp_price = adjust_sl_tp(market_conditions[recommended_timeframe]['ATR'], current_price, mt5.ORDER_TYPE_SELL)
                result = place_order_with_sl_tp(SYMBOL, mt5.ORDER_TYPE_SELL, lot, symbol_info.bid, sl_price, tp_price)
                log_trade_result(result)

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    send_telegram_message(f"Orden de venta enviada ({recommended_timeframe})")
                else:
                    logger.error(f"Error al enviar orden de venta: {result.retcode} - {result.comment}")

            manage_open_positions(SYMBOL)

            logger.info(f"Ciclo de trading {iteration} completado.")
            time.sleep(3600)

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        shutdown_mt5()

if __name__ == "__main__":
    main()