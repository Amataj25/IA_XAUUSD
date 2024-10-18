import logging
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime
import csv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_trade_result(result):
    if isinstance(result, dict):
        if result['retcode'] == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Trade executed: {result}")
        else:
            logger.error(f"Trade failed: {result['retcode']} - {result['comment']}")
    else:
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Trade executed: {result}")
        else:
            logger.error(f"Trade failed: {result.retcode} - {result.comment}")

    # Registro detallado en CSV
    try:
        with open('trade_log.csv', 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                datetime.now(),
                result['symbol'] if isinstance(result, dict) else result.symbol,
                result['volume'] if isinstance(result, dict) else result.volume,
                result['price'] if isinstance(result, dict) else result.price,
                result['sl'] if isinstance(result, dict) else result.sl,
                result['tp'] if isinstance(result, dict) else result.tp,
                result['retcode'] if isinstance(result, dict) else result.retcode,
                result['comment'] if isinstance(result, dict) else result.comment
            ])
    except Exception as e:
        logger.error(f"Error al registrar resultado de trading: {e}")

def generate_report(trade_data):
    # Generar reportes con base en las operaciones registradas
    try:
        df = pd.DataFrame(trade_data)
        report_file = "trade_report.csv"
        df.to_csv(report_file, index=False)
        logger.info(f"Report generated: {report_file}")
    except Exception as e:
        logger.error(f"Error generating report: {e}")

# Ejemplo de uso
if __name__ == "__main__":
    # Simulación de un resultado de operación para prueba
    example_trade_result = {
        "symbol": "XAUUSD",
        "volume": 0.02,
        "price": 2673.8,
        "sl": 2671.8,
        "tp": 2680.0,
        "retcode": mt5.TRADE_RETCODE_DONE,
        "comment": "Trade executed successfully"
    }
    
    log_trade_result(example_trade_result)