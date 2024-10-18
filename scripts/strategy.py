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
from sklearn.impute import SimpleImputer

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

def get_real_time_data(symbol, timeframe, num_candles):
    try:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        if rates is None or len(rates) == 0:
            logger.warning(f"No se pudieron obtener datos para {symbol} en el período especificado.")
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
        
        df['MA8'] = df['close'].rolling(window=8).mean()
        
        logger.info(f"Datos obtenidos para {symbol} en timeframe {timeframe}: {len(df)} velas")
        return df
    except Exception as e:
        logger.error(f"Error al obtener datos en tiempo real para {symbol} en timeframe {timeframe}: {e}")
        return pd.DataFrame()

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
        logger.warning(f"Datos insuficientes para seleccionar el mejor modelo")
        return None, None, None

    scores = {}
    features = ['open', 'high', 'low', 'close', 'volume']
    if 'MA8' in data.columns:
        features.append('MA8')

    for model_name, model in models.items():
        if model is None:
            continue
        scaler = scalers[model_name]
        X = data[features]
        X = X.interpolate(method='linear', limit_direction='forward')
        
        scaler.fit(X)
        X_scaled = scaler.transform(X)
        
        model.fit(X_scaled[:-1], data['close'].shift(-1).dropna())
        
        y_pred = model.predict(X_scaled)
        mse = mean_squared_error(data['close'].shift(-1).dropna(), y_pred[:-1])
        r2 = r2_score(data['close'].shift(-1).dropna(), y_pred[:-1])
        scores[model_name] = {'mse': mse, 'r2': r2}
    
    if not scores:
        logger.warning("No se pudo evaluar ningún modelo")
        return None, None, None

    best_model = min(scores, key=lambda x: scores[x]['mse'])
    logger.info(f"Modelo seleccionado: {best_model}, MSE: {scores[best_model]['mse']}, R2: {scores[best_model]['r2']}")
    return best_model, models[best_model], scalers[best_model]

def process_and_predict(data):
    processed_data = {}
    for timeframe, df in data.items():
        if df.empty:
            logger.warning(f"No hay datos disponibles para el timeframe {timeframe}")
            processed_data[timeframe] = df
            continue

        try:
            features = ['open', 'high', 'low', 'close', 'volume']
            if 'MA8' in df.columns:
                features.append('MA8')

            X = df[features]
            X = X.interpolate(method='linear', limit_direction='forward')
            X = X.interpolate(method='linear', limit_direction='forward')
            X = SimpleImputer(strategy='mean').fit_transform(X)

            best_model_name, model, scaler = select_best_model(df)
            
            if model is None or scaler is None:
                logger.warning(f"No se pudo seleccionar un modelo para el timeframe {timeframe}")
                processed_data[timeframe] = df
                continue

            df['Prediction'] = model.predict(X)
            
            processed_data[timeframe] = df
            
            logger.info(f"Predicción realizada para el timeframe {timeframe}")
        except Exception as e:
            logger.error(f"Error al procesar y predecir para timeframe {timeframe}: {e}")
            processed_data[timeframe] = df

    return processed_data

def update_model(model_name, data):
    if len(data) < 100:
        logger.warning(f"Datos insuficientes para actualizar el modelo {model_name}")
        return

    model = models[model_name]
    scaler = scalers[model_name]
    X = data[['open', 'high', 'low', 'close', 'volume', 'MA8']]
    y = data['close'].shift(-1)
    X = X.interpolate(method='linear', limit_direction='forward')
    y = y[:-1].dropna()
    X = X[:-1]
    
    model.fit(X, y)
    joblib.dump(model, os.path.join(model_dir, model_name))
    joblib.dump(scaler, os.path.join(model_dir, f'scaler_{model_name}'))
    logger.info(f"Modelo {model_name} actualizado y guardado")

def create_basic_models():
    try:
        example_data = pd.DataFrame({
            'open': np.random.rand(100),
            'high': np.random.rand(100),
            'low': np.random.rand(100),
            'close': np.random.rand(100),
            'volume': np.random.rand(100),
            'MA8': np.random.rand(100)
        })
        X = example_data[['open', 'high', 'low', 'close', 'volume', 'MA8']]
        X = X.interpolate(method='linear', limit_direction='forward')
        
        rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
        lr_model = LinearRegression()

        rf_scaler = StandardScaler()
        lr_scaler = StandardScaler()

        rf_scaler.fit(X)
        lr_scaler.fit(X)

        X_scaled = rf_scaler.transform(X)
        rf_model.fit(X_scaled[:-1], example_data['close'].shift(-1).dropna())
        
        X_scaled = lr_scaler.transform(X)
        lr_model.fit(X_scaled[:-1], example_data['close'].shift(-1).dropna())

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