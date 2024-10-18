import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import logging
from strategy import process_and_predict, get_real_time_data
from volatility_filter import analyze_market_conditions
from trend_analysis import confirm_trend_multiple_timeframes
from dynamic_position_sizing import calculate_dynamic_lot_size, calculate_dynamic_sl_tp
from liquidity_analysis import analyze_liquidity
import time
from tqdm import tqdm
import signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_historical_data(symbol, timeframe, start_date, end_date):
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)
    
    rates = mt5.copy_rates_range(symbol, timeframe, start_date.to_pydatetime(), end_date.to_pydatetime())
    if rates is None or len(rates) == 0:
        logger.warning(f"No se pudieron obtener datos para {symbol} en el período especificado.")
        return pd.DataFrame()
    
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    df['MA8'] = df['close'].rolling(window=8).mean()
    if 'volume' not in df.columns:
        df['volume'] = 0  # Añadir una columna de volumen con valores 0 si no existe
    
    # Imputar valores NaN en el DataFrame
    df_imputed = df.interpolate(method='linear', limit_direction='forward')
    
    return df_imputed

def calculate_atr(data, period=14):
    high_low = data['high'] - data['low']
    high_close = abs(data['high'] - data['close'].shift(1))
    low_close = abs(data['low'] - data['close'].shift(1))
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    return true_range.rolling(window=period).mean()

def simulate_market_conditions(data, period=14):
    if len(data) < period:
        logger.warning("Datos insuficientes para calcular ATR")
        return {"ATR": None, "Volatilidad": "Desconocida"}

    atr = calculate_atr(data, period)
    if atr.empty or atr.isnull().all():
        return {"ATR": None, "Volatilidad": "Desconocida"}

    atr_value = atr.iloc[-1]
    if pd.isna(atr_value):
        return {"ATR": None, "Volatilidad": "Desconocida"}

    volatility = "Alta" if atr_value > np.percentile(atr.dropna(), 75) else "Normal"
    return {"ATR": atr_value, "Volatilidad": volatility}

def simulate_trade(entry_price, sl, tp, direction, future_data, position_size):
    for _, row in future_data.iterrows():
        if direction == 'buy':
            if row['low'] <= sl:
                return {'entry': entry_price, 'exit': sl, 'profit': (sl - entry_price) * position_size, 'result': 'loss'}
            elif row['high'] >= tp:
                return {'entry': entry_price, 'exit': tp, 'profit': (tp - entry_price) * position_size, 'result': 'win'}
        else:  # 'sell'
            if row['high'] >= sl:
                return {'entry': entry_price, 'exit': sl, 'profit': (entry_price - sl) * position_size, 'result': 'loss'}
            elif row['low'] <= tp:
                return {'entry': entry_price, 'exit': tp, 'profit': (entry_price - tp) * position_size, 'result': 'win'}
    
    return {'entry': entry_price, 'exit': future_data.iloc[-1]['close'], 'profit': 0, 'result': 'open'}

def calculate_position_size(balance, risk_percent, entry_price, stop_loss):
    risk_amount = balance * (risk_percent / 100)
    position_size = risk_amount / abs(entry_price - stop_loss)
    return position_size

def fallback_strategy(current_data):
    ma8 = current_data['MA8'].iloc[-1]
    current_price = current_data['close'].iloc[-1]
    
    if current_price > ma8:
        return current_price * 1.01, current_price * 0.99, 'buy'  # TP, SL, direction para compra
    elif current_price < ma8:
        return current_price * 0.99, current_price * 1.01, 'sell'  # TP, SL, direction para venta
    else:
        return None, None, None  # No trade

def backtest_strategy(symbol, timeframe, start_date, end_date, initial_balance=10000, max_iterations=1000, max_runtime=300):
    logger.info(f"Iniciando backtesting para {symbol} desde {start_date} hasta {end_date}")
    data = get_historical_data(symbol, timeframe, start_date, end_date)
    if data.empty:
        logger.error("No se pudo realizar el backtesting debido a la falta de datos históricos.")
        return pd.DataFrame(), initial_balance

    balance = initial_balance
    trades = []
    start_time = time.time()

    def signal_handler(signum, frame):
        raise KeyboardInterrupt("Backtesting interrupted by user")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        for i in tqdm(range(min(len(data) - 1, max_iterations)), desc="Backtesting Progress"):
            if time.time() - start_time > max_runtime:
                logger.warning(f"Tiempo máximo de ejecución alcanzado ({max_runtime} segundos). Deteniendo el backtesting.")
                break

            current_data = data.iloc[:i+1].copy()
            future_data = data.iloc[i+1:]
            
            try:
                market_conditions = simulate_market_conditions(current_data)
                if market_conditions["ATR"] is None:
                    logger.warning(f"No se pudo calcular ATR para el día {i+1}. Saltando esta iteración.")
                    continue
                
                processed_data = process_and_predict({timeframe: current_data})
                
                current_price = current_data.iloc[-1]['close']
                
                if timeframe not in processed_data or 'Prediction' not in processed_data[timeframe].columns or processed_data[timeframe]['Prediction'].isnull().all():
                    logger.warning(f"No se pudo hacer una predicción para el día {i+1}. Usando estrategia de fallback.")
                    tp, sl, direction = fallback_strategy(current_data)
                    if tp is None or sl is None:
                        continue
                else:
                    predicted_price = processed_data[timeframe]['Prediction'].iloc[-1]
                    
                    if predicted_price > current_price * 1.01:
                        tp = current_price * 1.02
                        sl = current_price * 0.99
                        direction = 'buy'
                    elif predicted_price < current_price * 0.99:
                        tp = current_price * 0.98
                        sl = current_price * 1.01
                        direction = 'sell'
                    else:
                        continue

                position_size = calculate_position_size(balance, 1, current_price, sl)
                trade_result = simulate_trade(current_price, sl, tp, direction, future_data, position_size)
                trades.append(trade_result)
                balance += trade_result['profit']
                
                if i % 100 == 0:
                    logger.info(f"Progreso: {i}/{min(len(data) - 1, max_iterations)} días procesados. Balance actual: {balance}")
            
            except Exception as e:
                logger.error(f"Error en la iteración {i+1}: {str(e)}")
                continue

    except KeyboardInterrupt:
        logger.info("Backtesting interrupted by user. Saving current progress...")
    except Exception as e:
        logger.error(f"Error durante backtesting: {e}")
    finally:
        logger.info(f"Backtesting completed or interrupted. Total trades: {len(trades)}")
        return pd.DataFrame(trades), balance

def analyze_backtest_results(trades, initial_balance, final_balance):
    if len(trades) == 0:
        logger.warning("No hay trades para analizar.")
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_profit': 0,
            'max_drawdown': 0,
            'final_balance': final_balance,
            'return_percentage': (final_balance - initial_balance) / initial_balance * 100
        }

    df_trades = pd.DataFrame(trades)
    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades['result'] == 'win'])
    losing_trades = len(df_trades[df_trades['result'] == 'loss'])
    
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    total_profit = df_trades['profit'].sum()
    max_drawdown = (df_trades['profit'].cumsum().cummin() - df_trades['profit'].cumsum()).min()
    
    return {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'total_profit': total_profit,
        'max_drawdown': max_drawdown,
        'final_balance': final_balance,
        'return_percentage': (final_balance - initial_balance) / initial_balance * 100
    }

def run_backtest(symbol, timeframe, start_date, end_date, initial_balance=10000):
    trades, final_balance = backtest_strategy(symbol, timeframe, start_date, end_date, initial_balance)
    results = analyze_backtest_results(trades, initial_balance, final_balance)
    return results

if __name__ == "__main__":
    symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_H4
    start_date = "2023-01-01"
    end_date = "2023-12-31"
    initial_balance = 10000

    results = run_backtest(symbol, timeframe, start_date, end_date, initial_balance)
    print("Resultados del backtesting:")
    for key, value in results.items():
        print(f"{key}: {value}")