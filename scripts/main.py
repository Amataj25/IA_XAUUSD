import time
import logging
import MetaTrader5 as mt5
import pandas as pd
from sklearn.impute import SimpleImputer
from utils import get_real_time_data, process_and_predict
from volatility_filter import analyze_market_conditions
from risk_management import manage_risk
from monitoring import log_trade_result
from high_low_retest import analyze_high_low_retest
from trend_lines import analyze_trend
from telegram_notifications import send_telegram_message
from trend_analysis import confirm_trend_multiple_timeframes
from dynamic_position_sizing import calculate_dynamic_lot_size, calculate_dynamic_sl_tp
from liquidity_analysis import analyze_liquidity
from backtesting import backtest_strategy, analyze_backtest_results
from parameter_optimization import run_optimization
from performance_analysis import analyze_performance

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración de MetaTrader 5
ACCOUNT = 31302194
PASSWORD = "L1m1c0y_198o"
SERVER = "Deriv-Demo"

# Parámetros de trading
SYMBOL = "XAUUSD"
INITIAL_LOT = 0.01
SL_PIPS = 100
TP_PIPS = 200
MAX_DAILY_PROFIT = 10
MIN_PRICE_DIFFERENCE = 0.00005
THRESHOLD = 30
TIMEFRAMES = [mt5.TIMEFRAME_W1, mt5.TIMEFRAME_D1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_H1]

def check_daily_profit():
    today = pd.Timestamp.now().floor('D')
    deals = mt5.history_deals_get(date_from=today.to_pydatetime())
    if deals is None:
        logger.debug("No se encontraron operaciones.")
        return 0
    
    profit = sum(deal.profit for deal in deals)
    return profit

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
    tick = mt5.symbol_info_tick(symbol)
    if tick is not None and tick.last > 0:
        return tick.last

    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
    if rates is not None and len(rates) > 0:
        return rates[0]['close']

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

def manage_open_positions(symbol):
    positions = mt5.positions_get(symbol=symbol)
    if positions:
        for position in positions:
            logger.info(f"Posición abierta: {position.ticket}, Profit: {position.profit}")

def run_backtest():
    if not mt5.initialize():
        print("initialize() failed, error code =", mt5.last_error())
        return

    start_date = '2023-01-01'
    end_date = '2023-12-31'
    initial_balance = 10000

    trades, final_balance = backtest_strategy(SYMBOL, mt5.TIMEFRAME_H4, start_date, end_date, initial_balance)
    results = analyze_backtest_results(trades, initial_balance, final_balance)

    logger.info("Resultados del Backtesting:")
    for key, value in results.items():
        logger.info(f"{key}: {value}")

    mt5.shutdown()

def main():
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
            
            current_price = get_current_price(SYMBOL)
            if current_price is None or current_price == 0:
                logger.warning("El precio actual es inválido. No se puede continuar.")
                continue
            
            logger.info(f"Precio actual obtenido: {current_price}")
            
            strength = calculate_retest_strength(current_price, resistance, support)

            account_info = get_account_info()
            if account_info:
                market_volatility = market_conditions[recommended_timeframe]['ATR']
                lot = calculate_dynamic_lot_size(SYMBOL, account_info['balance'], 1, SL_PIPS, 5)
                if lot is None:
                    logger.warning("No se pudo calcular el tamaño del lote. Usando tamaño de lote inicial.")
                    lot = INITIAL_LOT
            else:
                logger.warning("No se pudo obtener información de la cuenta. Usando tamaño de lote inicial.")
                lot = INITIAL_LOT

            # Análisis de liquidez
            liquidity_levels, sweep_detected, swept_level = analyze_liquidity(processed_data[recommended_tf], current_price)

            if sweep_detected:
                logger.info(f"Barrido de liquidez detectado en nivel: {swept_level}")
            
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

            trend = confirm_trend_multiple_timeframes(real_time_data[mt5.TIMEFRAME_H1], real_time_data[mt5.TIMEFRAME_H4])
            if trend is None:
                logger.info("No hay concordancia en las tendencias de 1H y 4H. Omitiendo entrada.")
                continue

            if ((retest_direction == 'buy' or trend_direction == 'buy') and 
                (signal > current_price * (1 + MIN_PRICE_DIFFERENCE) or current_price > support * (1 + MIN_PRICE_DIFFERENCE)) and 
                (sweep_detected and swept_level in ['recent_low', 'previous_day_low'])):
                
                logger.info(f"Condiciones de compra cumplidas con barrido de liquidez en {swept_level}.")
                
                sl, tp = calculate_dynamic_sl_tp(SYMBOL, current_price, market_conditions[recommended_timeframe]['ATR'], 'buy')
                
                if sl is None or tp is None:
                    logger.warning("No se pudieron calcular SL y TP. Omitiendo entrada.")
                    continue
                
                result = place_order_with_sl_tp(SYMBOL, mt5.ORDER_TYPE_BUY, lot, symbol_info.ask, sl, tp)
                log_trade_result(result)

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    send_telegram_message(f"Orden de compra enviada ({recommended_timeframe})")
                else:
                    logger.error(f"Error al enviar orden de compra: {result.retcode} - {result.comment}")
                    
            elif ((retest_direction == 'sell' or trend_direction == 'sell') and 
                  (signal < current_price * (1 - MIN_PRICE_DIFFERENCE) or current_price < resistance * (1 - MIN_PRICE_DIFFERENCE)) and 
                  (sweep_detected and swept_level in ['recent_high', 'previous_day_high'])):

                logger.info(f"Condiciones de venta cumplidas con barrido de liquidez en {swept_level}.")
                
                sl, tp = calculate_dynamic_sl_tp(SYMBOL, current_price, market_conditions[recommended_timeframe]['ATR'], 'sell')
                
                if sl is None or tp is None:
                    logger.warning("No se pudieron calcular SL y TP. Omitiendo entrada.")
                    continue
                
                result = place_order_with_sl_tp(SYMBOL, mt5.ORDER_TYPE_SELL, lot, symbol_info.bid, sl, tp)
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
    mode = input("Seleccione el modo (1: Trading en vivo, 2: Backtesting, 3: Optimización de parámetros): ")
    if mode == '1':
        main()
    elif mode == '2':
        run_backtest()
    elif mode == '3':
        run_optimization()
    else:
        print("Modo no válido seleccionado.")