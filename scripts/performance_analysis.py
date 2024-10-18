# performance_analysis.py

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def calculate_performance_metrics(trades):
    """
    Calcula métricas de rendimiento adicionales.
    """
    total_trades = len(trades)
    winning_trades = trades[trades['profit'] > 0]
    losing_trades = trades[trades['profit'] < 0]
    
    win_rate = len(winning_trades) / total_trades if total_trades > 0 else 0
    average_win = winning_trades['profit'].mean() if len(winning_trades) > 0 else 0
    average_loss = losing_trades['profit'].mean() if len(losing_trades) > 0 else 0
    profit_factor = abs(winning_trades['profit'].sum() / losing_trades['profit'].sum()) if losing_trades['profit'].sum() != 0 else float('inf')
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'average_win': average_win,
        'average_loss': average_loss,
        'profit_factor': profit_factor
    }

def plot_equity_curve(trades):
    """
    Genera una curva de equidad.
    """
    cumulative_profit = trades['profit'].cumsum()
    plt.figure(figsize=(12, 6))
    plt.plot(trades['date'], cumulative_profit)
    plt.title('Curva de Equidad')
    plt.xlabel('Fecha')
    plt.ylabel('Beneficio Acumulado')
    plt.grid(True)
    plt.show()

def plot_monthly_returns(trades):
    """
    Genera un gráfico de barras de rendimientos mensuales.
    """
    monthly_returns = trades.set_index('date').resample('M')['profit'].sum()
    plt.figure(figsize=(12, 6))
    monthly_returns.plot(kind='bar')
    plt.title('Rendimientos Mensuales')
    plt.xlabel('Mes')
    plt.ylabel('Beneficio')
    plt.grid(True)
    plt.show()

def plot_trade_distribution(trades):
    """
    Genera un histograma de la distribución de ganancias/pérdidas.
    """
    plt.figure(figsize=(12, 6))
    sns.histplot(trades['profit'], kde=True)
    plt.title('Distribución de Ganancias/Pérdidas')
    plt.xlabel('Beneficio')
    plt.ylabel('Frecuencia')
    plt.grid(True)
    plt.show()

def analyze_performance(trades):
    """
    Realiza un análisis completo del rendimiento.
    """
    metrics = calculate_performance_metrics(trades)
    
    print("Métricas de Rendimiento:")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    
    plot_equity_curve(trades)
    plot_monthly_returns(trades)
    plot_trade_distribution(trades)

if __name__ == "__main__":
    # Aquí puedes cargar tus datos de trades (por ejemplo, desde un CSV)
    # trades = pd.read_csv('trades.csv')
    # analyze_performance(trades)
    pass