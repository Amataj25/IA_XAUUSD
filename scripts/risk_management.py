import MetaTrader5 as mt5
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def manage_risk(symbol, lot, capital, risk_percentage=1, stop_loss_pips=50):
    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Failed to get account info")
        return False

    balance = account_info.balance
    risk_amount = (risk_percentage / 100) * balance
    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        logger.error("Failed to get symbol info")
        return False

    tick_size = symbol_info.trade_tick_size
    stop_loss_value = tick_size * stop_loss_pips
    max_lot = risk_amount / stop_loss_value

    # Ajustar tamaño del lote si es necesario
    if lot > max_lot:
        logger.warning(f"Lot size adjusted from {lot} to {max_lot:.2f} to manage risk")
        lot = max_lot

    logger.info(f"Adjusted lot size: {lot:.2f} based on risk management")
    return lot

def check_daily_loss(daily_loss_limit):
    today = pd.Timestamp.now().floor('D')
    deals = mt5.history_deals_get(date_from=today.to_pydatetime())
    
    if deals is None:
        logger.debug("No deals found for today.")
        return 0
    
    current_daily_loss = sum(deal.profit for deal in deals)
    
    if current_daily_loss < -daily_loss_limit:
        logger.warning(f"Daily loss limit reached. Current loss: ${current_daily_loss:.2f}.")
        return True
    
    return False

def manage_drawdown(account_info, max_drawdown_percentage):
    current_drawdown = (account_info.balance - account_info.equity) / account_info.balance * 100
    
    if current_drawdown > max_drawdown_percentage:
        logger.warning(f"Drawdown limit exceeded: {current_drawdown:.2f}% > {max_drawdown_percentage:.2f}%. Consider reducing position sizes.")
        return True
    
    return False

# Ejemplo de uso
if __name__ == "__main__":
    symbol = "XAUUSD"
    lot = 0.02
    capital = 10000  # Ejemplo de capital inicial
    risk_percentage = 1  # Riesgo del 1%
    
    adjusted_lot = manage_risk(symbol, lot, capital)
    
    daily_loss_limit = 50  # Límite de pérdida diaria en dólares
    if check_daily_loss(daily_loss_limit):
        logger.info("Stop trading for the day due to daily loss limit.")
    
    account_info = mt5.account_info()
    if account_info:
        max_drawdown_percentage = 10  # Límite de drawdown del 10%
        manage_drawdown(account_info, max_drawdown_percentage)