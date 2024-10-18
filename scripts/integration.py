import MetaTrader5 as mt5
import requests
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def initialize_mt5(account, password, server):
    if not mt5.initialize():
        logger.error("Failed to initialize MetaTrader5")
        return False
    
    authorized = mt5.login(account, password=password, server=server)
    if not authorized:
        logger.error(f"Failed to login to account {account}")
        mt5.shutdown()
        return False
    
    logger.info("Successfully logged in to MT5.")
    return True

def shutdown_mt5():
    mt5.shutdown()
    logger.info("MT5 connection closed.")

def send_telegram_message(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        logger.info("Mensaje de Telegram enviado exitosamente")
    except requests.RequestException as e:
        logger.error(f"Error al enviar mensaje de Telegram: {e}")

def get_account_info():
    try:
        account_info = mt5.account_info()
        if account_info is None:
            raise ValueError("Failed to get account info")
        return {
            "balance": account_info.balance,
            "equity": account_info.equity,
            "profit": account_info.profit,
            "margin": account_info.margin,
            "free_margin": account_info.margin_free
        }
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        return None

def place_market_order(symbol, volume, order_type, sl=None, tp=None, deviation=20):
    try:
        if order_type.lower() == "buy":
            order_type_mt5 = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        elif order_type.lower() == "sell":
            order_type_mt5 = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            raise ValueError("Invalid order type. Use 'buy' or 'sell'.")

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            raise ValueError(f"Failed to get symbol info for {symbol}")

        logger.info(f"Attempting to place {order_type} order for {symbol}, volume: {volume}")
        logger.info(f"Symbol info: {symbol_info}")

        if symbol_info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
            logger.warning(f"Market is closed for {symbol}. Current trade mode: {symbol_info.trade_mode}")
            return {'retcode': -1, 'comment': "Market is closed"}

        filling_type = mt5.ORDER_FILLING_IOC
        if symbol_info.filling_mode & mt5.SYMBOL_FILLING_FOK:
            filling_type = mt5.ORDER_FILLING_FOK

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type_mt5,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": deviation,
            "magic": 234000,
            "comment": "python script open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }

        logger.info(f"Sending order request: {request}")
        result = mt5.order_send(request)
        logger.info(f"Order result: {result}")

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Order placed successfully: {order_type}, Volume: {volume}, Price: {price}, Filling: {filling_type}")
            return {'retcode': result.retcode, 'comment': result.comment, 'order': result.order}
        else:
            logger.error(f"Order failed, retcode={result.retcode}")
            return {'retcode': result.retcode, 'comment': result.comment}

    except Exception as e:
        logger.error(f"Error placing order: {e}")
        return {'retcode': -1, 'comment': str(e)}

def get_open_positions(symbol=None):
    try:
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            logger.info("No open positions")
            return []

        position_list = []
        for position in positions:
            position_list.append({
                "ticket": position.ticket,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell",
                "price_open": position.price_open,
                "price_current": position.price_current,
                "profit": position.profit,
                "sl": position.sl,
                "tp": position.tp
            })
        return position_list
    except Exception as e:
        logger.error(f"Error getting open positions: {e}")
        return []

def close_position(ticket):
    try:
        position = mt5.positions_get(ticket=ticket)
        if not position:
            logger.error(f"Position with ticket {ticket} not found")
            return False

        position = position[0]
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
            "deviation": 20,
            "magic": 234000,
            "comment": "python script close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Position {ticket} closed successfully")
            return True
        else:
            logger.error(f"Failed to close position {ticket}, retcode={result.retcode}")
            return False
    except Exception as e:
        logger.error(f"Error closing position {ticket}: {e}")
        return False

def get_historical_data(symbol, timeframe, start_date, end_date=None):
    try:
        if end_date is None:
            end_date = datetime.now()

        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1
        }

        if timeframe not in timeframe_map:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        rates = mt5.copy_rates_range(symbol, timeframe_map[timeframe], start_date, end_date)
        if rates is None or len(rates) == 0:
            logger.warning(f"No historical data found for {symbol} from {start_date} to {end_date}")
            return None

        return rates
    except Exception as e:
        logger.error(f"Error getting historical data: {e}")
        return None

# Puedes agregar más funciones según sea necesario para tu estrategia de trading