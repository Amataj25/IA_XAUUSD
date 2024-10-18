# parameter_optimization.py

import itertools
from backtesting import backtest_strategy, analyze_backtest_results

def optimize_parameters(symbol, timeframe, start_date, end_date, initial_balance, parameter_ranges):
    """
    Realiza una optimización de cuadrícula sobre los parámetros dados.
    """
    best_result = None
    best_params = None
    
    # Genera todas las combinaciones posibles de parámetros
    param_combinations = list(itertools.product(*parameter_ranges.values()))
    
    for params in param_combinations:
        # Crea un diccionario con los parámetros actuales
        current_params = dict(zip(parameter_ranges.keys(), params))
        
        # Ejecuta el backtesting con los parámetros actuales
        trades, final_balance = backtest_strategy(symbol, timeframe, start_date, end_date, initial_balance, **current_params)
        results = analyze_backtest_results(trades, initial_balance, final_balance)
        
        # Compara los resultados (puedes ajustar el criterio de "mejor" según tus necesidades)
        if best_result is None or results['total_profit'] > best_result['total_profit']:
            best_result = results
            best_params = current_params
    
    return best_params, best_result

def run_optimization():
    symbol = "XAUUSD"
    timeframe = mt5.TIMEFRAME_H4
    start_date = '2023-01-01'
    end_date = '2023-12-31'
    initial_balance = 10000
    
    # Define los rangos de parámetros a probar
    parameter_ranges = {
        'sl_factor': [1.5, 2.0, 2.5],
        'tp_factor': [3.0, 4.0, 5.0],
        'risk_percentage': [0.5, 1.0, 1.5],
        'min_price_difference': [0.00003, 0.00005, 0.00007]
    }
    
    best_params, best_result = optimize_parameters(symbol, timeframe, start_date, end_date, initial_balance, parameter_ranges)
    
    print("Mejores parámetros encontrados:")
    for param, value in best_params.items():
        print(f"{param}: {value}")
    
    print("\nResultados con los mejores parámetros:")
    for key, value in best_result.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    run_optimization()