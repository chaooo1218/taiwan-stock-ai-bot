import pandas as pd

class BacktestEngine:
    def __init__(self, df_price=None, df_fund=None, news_list=None, strategy_func=None):
        if df_price is None or len(df_price) == 0:
            raise ValueError("❌ df_price 不可為空，請提供歷史價格資料")

        self.df_price = df_price.reset_index(drop=True)
        self.df_price['date'] = pd.to_datetime(self.df_price['date'])

        if df_fund is not None and len(df_fund) > 0:
            self.df_fund = df_fund.copy()
            self.df_fund['date'] = pd.to_datetime(self.df_fund['date'])
        else:
            self.df_fund = pd.DataFrame()

        self.news_list = news_list if news_list else []
        self.strategy_func = strategy_func

        self.trades = []
        self.position = None

    def run_backtest(self):
        for i in range(len(self.df_price)):
            today = self.df_price.iloc[i]
            date = today['date']

            # 取得法人資料
            fund_today = None
            if not self.df_fund.empty:
                fund_today = self.df_fund[self.df_fund['date'] == date]

            # 取得新聞
            news_today = []
            for n in self.news_list:
                try:
                    pub_time = pd.to_datetime(n.get('publish_time', '')).date()
                    if pub_time == date.date():
                        news_today.append(n)
                except Exception:
                    continue

            if self.strategy_func is None:
                raise ValueError("❌ 請提供策略函式 strategy_func")

            signal = self.strategy_func(today, fund_today, news_today)

            if self.position is None:
                if signal.get('action') == 'buy':
                    self.position = {
                        'entry_date': date,
                        'entry_price': today['close'],
                        'reason': signal.get('reason', '')
                    }
            else:
                if signal.get('action') == 'sell':
                    exit_price = today['close']
                    profit = (exit_price - self.position['entry_price']) / self.position['entry_price']
                    trade_record = {
                        'entry_date': self.position['entry_date'],
                        'entry_price': self.position['entry_price'],
                        'exit_date': date,
                        'exit_price': exit_price,
                        'profit': profit,
                        'reason_entry': self.position['reason'],
                        'reason_exit': signal.get('reason', '')
                    }
                    self.trades.append(trade_record)
                    self.position = None

        # 最後強制平倉
        if self.position is not None:
            last_close = self.df_price.iloc[-1]['close']
            profit = (last_close - self.position['entry_price']) / self.position['entry_price']
            trade_record = {
                'entry_date': self.position['entry_date'],
                'entry_price': self.position['entry_price'],
                'exit_date': self.df_price.iloc[-1]['date'],
                'exit_price': last_close,
                'profit': profit,
                'reason_entry': self.position['reason'],
                'reason_exit': '強制平倉'
            }
            self.trades.append(trade_record)
            self.position = None

    def calculate_performance(self):
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'total_return': 0.0,
                'max_drawdown': 0.0
            }

        wins = sum(1 for t in self.trades if t['profit'] > 0)
        total = len(self.trades)
        avg_profit = sum(t['profit'] for t in self.trades) / total

        # 計算資產曲線
        equity_curve = [1.0]
        for t in self.trades:
            equity_curve.append(equity_curve[-1] * (1 + t['profit']))

        total_return = equity_curve[-1] - 1

        # 計算最大回撤 MDD
        peak = equity_curve[0]
        max_dd = 0.0
        for value in equity_curve:
            peak = max(peak, value)
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        win_rate = wins / total
        return {
            'total_trades': total,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_return': total_return,
            'max_drawdown': max_dd
        }

    def get_trade_log(self):
        return self.trades


# === 範例策略 ===
def sample_strategy(today, fund_today, news_today):
    if 'MA20' not in today:
        return {'action': 'hold', 'reason': '無MA20資料'}

    close = today['close']
    if close > today['MA20']:
        return {'action': 'buy', 'reason': '價格突破MA20'}
    elif close < today['MA20']:
        return {'action': 'sell', 'reason': '價格跌破MA20'}
    return {'action': 'hold', 'reason': '無操作'}


# === 測試 ===
if __name__ == "__main__":
    data = {
        'date': pd.date_range("2025-01-01", periods=10, freq='D'),
        'close': [100, 102, 105, 103, 108, 110, 107, 111, 115, 112],
        'MA20': [100]*10,
        'volume': [1000]*10
    }
    df_price = pd.DataFrame(data)

    backtester = BacktestEngine(df_price=df_price, df_fund=None, news_list=[], strategy_func=sample_strategy)
    backtester.run_backtest()
    perf = backtester.calculate_performance()
    print(f"交易次數: {perf['total_trades']}, 勝率: {perf['win_rate']:.2%}, 平均報酬率: {perf['avg_profit']:.2%}, 總報酬率: {perf['total_return']:.2%}, 最大回撤: {perf['max_drawdown']:.2%}")
    for trade in backtester.get_trade_log():
        print(trade)
