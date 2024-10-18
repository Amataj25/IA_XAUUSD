import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import joblib
import logging
import time
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
model_dir = os.path.join(os.path.dirname(current_dir), 'models')

if not os.path.exists(model_dir):
    os.makedirs(model_dir)
    logger.info(f"Directorio de modelos creado: {model_dir}")

primary_model_file = 'best_random_forest_model_combined.pkl'
secondary_model_file = 'linear_regression_model.pkl'

models = {}
scalers = {}

def load_models():
    for model_file in [primary_model_file, secondary_model_file]:
        model_path = os.path.join(model_dir, model_file)
        scaler_path = os.path.join(model_dir, f'scaler_{model_file}')
        try:
            if os.path.exists(model_path) and os.path.exists(scaler_path):
                models[model_file] = joblib.load(model_path)
                scalers[model_file] = joblib.load(scaler_path)
                logger.info(f"Modelo y scaler cargados exitosamente: {model_file}")
            else:
                logger.warning(f"Archivo no encontrado: {model_path} o {scaler_path}")
                raise FileNotFoundError(f"Archivo no encontrado: {model_path} o {scaler_path}")
        except Exception as e:
            logger.error(f"Error al cargar el modelo {model_file}: {e}")
            models[model_file] = None
            scalers[model_file] = None

    if all(model is None for model in models.values()):
        logger.warning("No se pudo cargar ningún modelo. Se crearán modelos básicos.")
        create_basic_models()
        load_models()

def select_best_model(data):
    if len(data) < 100:
        logger.warning("Datos insuficientes para seleccionar el mejor modelo")
        return None, None, None

    scores = {}
    for model_name, model in models.items():
        if model is None:
            continue
        scaler = scalers[model_name]
        X = data[['open', 'high', 'low', 'close', 'volume']]
        y = data['close'].shift(-1)
        
        if not hasattr(scaler, 'n_features_in_'):
            scaler.fit(X)
        
        X_scaled = scaler.transform(X)
        
        if not hasattr(model, 'n_features_in_'):
            model.fit(X_scaled[:-1], y[:-1].dropna())
        
        y_pred = model.predict(X_scaled)
        mse = mean_squared_error(y[:-1].dropna(), y_pred[:-1])
        r2 = r2_score(y[:-1].dropna(), y_pred[:-1])
        scores[model_name] = {'mse': mse, 'r2': r2}
    
    if not scores:
        logger.warning("No se pudo evaluar ningún modelo")
        return None, None, None

    best_model = min(scores, key=lambda x: scores[x]['mse'])
    logger.info(f"Modelo seleccionado: {best_model}, MSE: {scores[best_model]['mse']}, R2: {scores[best_model]['r2']}")
    return best_model, models[best_model], scalers[best_model]

def update_model(model_name, data):
    if len(data) < 100:
        logger.warning(f"Datos insuficientes para actualizar el modelo {model_name}")
        return

    model = models[model_name]
    scaler = scalers[model_name]
    X = data[['open', 'high', 'low', 'close', 'volume']]
    y = data['close'].shift(-1)
    X = scaler.fit_transform(X)
    y = y[:-1].dropna()
    X = X[:-1]
    model.fit(X, y)
    joblib.dump(model, os.path.join(model_dir, model_name))
    joblib.dump(scaler, os.path.join(model_dir, f'scaler_{model_name}'))
    logger.info(f"Modelo {model_name} actualizado y guardado")

def get_real_time_data(symbol, timeframe=mt5.TIMEFRAME_H1, num_candles=1000):
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        if rates is None or len(rates) == 0:
            logger.warning(f"No se obtuvieron datos para {symbol} en timeframe {timeframe}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        df['timeframe'] = timeframe
        
        required_columns = ['open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0
        
        if 'tick_volume' in df.columns and 'volume' not in df.columns:
            df['volume'] = df['tick_volume']
        
        logger.info(f"Datos obtenidos para {symbol} en timeframe {timeframe}: {len(df)} velas")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos en tiempo real para {symbol} en timeframe {timeframe}: {e}")
        return pd.DataFrame()

def process_and_predict(data):
    try:
        if not models:
            logger.warning("No hay modelos disponibles. Usando una estrategia alternativa.")
            for tf, df in data.items():
                df['Prediction'] = df['close'].rolling(window=20).mean()
                logger.info(f"Predicción para {tf}: último cierre = {df['close'].iloc[-1]}, predicción = {df['Prediction'].iloc[-1]}")
            return data

        if mt5.TIMEFRAME_H1 not in data:
            logger.error("Datos de timeframe de 1 hora no disponibles para seleccionar el mejor modelo")
            return data

        best_model_name, model, scaler = select_best_model(data[mt5.TIMEFRAME_H1])
        
        if model is None or scaler is None:
            logger.error("No se pudo seleccionar un modelo válido")
            return data

        for tf, df in data.items():
            try:
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in required_columns:
                    if col not in df.columns:
                        logger.warning(f"Columna {col} no encontrada en el timeframe {tf}. Usando valores predeterminados.")
                        df[col] = df['close'] if col != 'volume' else 0

                X = df[required_columns]
                
                if not hasattr(scaler, 'n_features_in_'):
                    scaler.fit(X)
                
                X_scaled = scaler.transform(X)
                
                if not hasattr(model, 'n_features_in_'):
                    y = df['close'].shift(-1)
                    model.fit(X_scaled[:-1], y[:-1].dropna())
                
                df['Prediction'] = model.predict(X_scaled)
                logger.info(f"Predicción para {tf}: último cierre = {df['close'].iloc[-1]}, predicción = {df['Prediction'].iloc[-1]}")
            except Exception as e:
                logger.error(f"Error al procesar y predecir para timeframe {tf}: {e}")
                df['Prediction'] = np.nan
        
        if int(time.time()) % 86400 < 3600:  # En la primera hora de cada día
            if mt5.TIMEFRAME_D1 in data:
                for model_name in models.keys():
                    update_model(model_name, data[mt5.TIMEFRAME_D1])
            else:
                logger.warning("Datos diarios no disponibles para actualizar los modelos")
        
        return data
    except Exception as e:
        logger.error(f"Error general al procesar y predecir: {e}")
        for tf, df in data.items():
            df['Prediction'] = np.nan
        return data

def create_basic_models():
    try:
        example_data = pd.DataFrame({
            'open': np.random.rand(100),
            'high': np.random.rand(100),
            'low': np.random.rand(100),
            'close': np.random.rand(100),
            'volume': np.random.rand(100)
        })
        X = example_data[['open', 'high', 'low', 'close', 'volume']]
        y = example_data['close'].shift(-1)

        rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
        lr_model = LinearRegression()

        rf_scaler = StandardScaler()
        lr_scaler = StandardScaler()

        rf_scaler.fit(X)
        lr_scaler.fit(X)

        X_scaled = rf_scaler.transform(X)
        rf_model.fit(X_scaled[:-1], y[:-1].dropna())
        
        X_scaled = lr_scaler.transform(X)
        lr_model.fit(X_scaled[:-1], y[:-1].dropna())

        joblib.dump(rf_model, os.path.join(model_dir, primary_model_file))
        joblib.dump(lr_model, os.path.join(model_dir, secondary_model_file))
        joblib.dump(rf_scaler, os.path.join(model_dir, f'scaler_{primary_model_file}'))
        joblib.dump(lr_scaler, os.path.join(model_dir, f'scaler_{secondary_model_file}'))

        logger.info(f"Modelos básicos creados y guardados en {model_dir}")
    except Exception as e:
        logger.error(f"Error al crear modelos básicos: {e}")

load_models()

def place_order(symbol, lot, order_type):
    try:
        if order_type.lower() == 'buy':
            logger.info(f"Orden de compra simulada: {symbol}, {lot} lotes")
            return {'status': 'success', 'order_type': 'buy', 'symbol': symbol, 'lot': lot}
        elif order_type.lower() == 'sell':
            logger.info(f"Orden de venta simulada: {symbol}, {lot} lotes")
            return {'status': 'success', 'order_type': 'sell', 'symbol': symbol, 'lot': lot}
        else:
            logger.error(f"Tipo de orden no válido: {order_type}")
            return {'status': 'error', 'message': 'Tipo de orden no válido'}
    except Exception as e:
        logger.error(f"Error al colocar la orden: {e}")
        return {'status': 'error', 'message': str(e)}