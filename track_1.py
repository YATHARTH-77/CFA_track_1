import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from backtesting import Backtest, Strategy

#getting the past years data
stock_symbol = 'RELIANCE.NS'
index_symbol = '^NSEI'

start_date = '2020-01-01'
end_date = '2025-01-01'

stock_data = yf.download(stock_symbol, start=start_date, end=end_date, auto_adjust=False)
index_data = yf.download(index_symbol, start=start_date, end=end_date, auto_adjust=False)

#use only that column that is useful
if isinstance(stock_data.columns, pd.MultiIndex):
    stock_data.columns = stock_data.columns.get_level_values(0)

stock_data = stock_data[['Open', 'High', 'Low', 'Close', 'Volume']]

#defining the strategy
class BollingerBandsStrategy(Strategy):
    sma_window = 20
    std_dev = 2
    stop_loss_pct = 0.03
    position_size = 0.01 

    def init(self):
        close = self.data.Close        
        self.sma = self.I(lambda x: pd.Series(x).rolling(self.sma_window).mean(), close)
        self.std = self.I(lambda x: pd.Series(x).rolling(self.sma_window).std(), close)
        self.upper_band = self.sma + self.std_dev * self.std
        self.lower_band = self.sma - self.std_dev * self.std
        self.volatility = self.std  

    def next(self):
        price = self.data.Close[-1]
        sma = self.sma[-1]
        upper = self.upper_band[-1]
        lower = self.lower_band[-1]
        vol = self.volatility[-1]

#skipping the trade when the volatility is low 
        if vol < np.percentile(self.volatility, 25):
            return

        if price < lower and not self.position:
            self.buy(size=self.position_size, sl=price * (1 - self.stop_loss_pct))

        
        if self.position and (price > upper or abs(price - sma) < 0.01 * sma):
            self.position.close()

#running the backtest below 
bt = Backtest(
    stock_data,
    BollingerBandsStrategy,
    cash=1_000_000,
    commission=0.001,
    exclusive_orders=True
)

stats = bt.run()

#optional printing of the debug 
print("Available Stats:", stats.keys())
print("Trade Columns:", stats['_trades'].columns)

#metrics
trades = stats['_trades']

if not trades.empty:
    wins = trades[trades['PnL'] > 0]
    losses = trades[trades['PnL'] < 0]

    avg_profit = wins['PnL'].mean() if not wins.empty else 0
    avg_loss = abs(losses['PnL'].mean()) if not losses.empty else 0
    max_profit = trades['PnL'].max()
    max_loss = abs(trades['PnL'].min())
    profit_factor = abs(wins['PnL'].sum() / losses['PnL'].sum()) if losses['PnL'].sum() != 0 else np.inf
else:
    avg_profit = avg_loss = max_profit = max_loss = profit_factor = 0

#nefty50 performance 
index_data = index_data[['Open', 'High', 'Low', 'Close', 'Volume']]
nifty_returns = index_data['Close'].pct_change().dropna()

cumulative_return_nifty = (1 + nifty_returns).prod() - 1
annualized_return_nifty = ((1 + cumulative_return_nifty) ** (252 / len(index_data))) - 1
#metrics table 
metrics = {
    'Cumulative Return (%)': stats.get('Return [%]', 0),
    'Annualized Return (%)': stats.get('Return (Ann.) [%]', 0),
    'Sharpe Ratio': stats.get('Sharpe Ratio', 0),
    'Sortino Ratio': stats.get('Sortino Ratio', 0),
    'Maximum Drawdown (%)': abs(stats.get('Max. Drawdown [%]', 0)),
    'Win Rate (%)': stats.get('Win Rate [%]', 0),
    'Profit Factor': profit_factor,
    'Avg Profit': avg_profit,
    'Avg Loss': avg_loss,
    'Max Profit': max_profit,
    'Max Loss': max_loss,
    'Nifty 50 Cumulative Return (%)': cumulative_return_nifty * 100,
    'Nifty 50 Annualized Return (%)': annualized_return_nifty * 100
}
metrics_df = pd.DataFrame(metrics.items(), columns=['Metric', 'Value']).round(2)
metrics_df.to_csv('metrics_table.csv', index=False)

#equity graph
plt.figure(figsize=(10, 6))
plt.plot(stats['_equity_curve']['Equity'], label='Equity Curve')
plt.title('Equity Curve')
plt.xlabel('Date')
plt.ylabel('Equity (INR)')
plt.legend()
plt.grid()
plt.savefig('equity_curve.png')
plt.close()

#drawdown graph
plt.figure(figsize=(10, 6))
plt.plot(stats['_equity_curve']['DrawdownPct'] * 100, label='Drawdown (%)')
plt.title('Drawdown')
plt.xlabel('Date')
plt.ylabel('Drawdown (%)')
plt.legend()
plt.grid()
plt.savefig('drawdown.png')
plt.close()

# Price Chart with Trades + Bollinger Bands
sma = stock_data['Close'].rolling(window=20).mean()
std = stock_data['Close'].rolling(window=20).std()
upper_band = sma + 2 * std
lower_band = sma - 2 * std

plt.figure(figsize=(10, 6))
plt.plot(stock_data['Close'], label='Close Price')
plt.plot(stock_data.index, sma, label='20-day SMA')
plt.plot(stock_data.index, upper_band, label='Upper Band')
plt.plot(stock_data.index, lower_band, label='Lower Band')

#marking of the trade enteries and the exits 
if not trades.empty:
    for _, trade in trades.iterrows():
        entry_time = trade.get('EntryTime')
        exit_time = trade.get('ExitTime')

        if entry_time in stock_data.index:
            plt.axvline(entry_time, color='g', linestyle='--', alpha=0.5)
        if exit_time in stock_data.index:
            plt.axvline(exit_time, color='r', linestyle='--', alpha=0.5)

plt.title('Price with Bollinger Bands and Trades')
plt.xlabel('Date')
plt.ylabel('Price (INR)')
plt.legend()
plt.grid()
plt.savefig('price_with_trades.png')
plt.close()

bt.plot(filename='backtest_results.html', open_browser=False)