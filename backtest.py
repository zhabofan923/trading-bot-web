"""
策略回测模块
测试交易策略在历史数据上的表现
"""

import pandas as pd
import numpy as np
from datetime import datetime

class Backtester:
    def __init__(self, df, initial_capital=10000, leverage=1):
        """
        初始化回测器
        
        df: DataFrame 包含 OHLCV 数据
        initial_capital: 初始资金
        leverage: 杠杆倍数
        """
        self.df = df.copy()
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.trades = []
        self.equity_curve = []
        
    def run_backtest(self, strategy_params=None):
        """
        运行回测
        
        strategy_params: 策略参数字典
        """
        if strategy_params is None:
            strategy_params = {
                'atr_multiplier_sl': 1.5,
                'atr_multiplier_tp': 2.0,
                'pivot_window': 10
            }
        
        # 计算指标
        self._calculate_indicators(strategy_params)
        
        # 生成信号
        self._generate_signals()
        
        # 模拟交易
        self._simulate_trades()
        
        # 计算统计
        return self._calculate_statistics()
    
    def _calculate_indicators(self, params):
        """计算技术指标"""
        df = self.df
        
        # ATR
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        # 支撑压力
        df['pivot_high'] = df['high'].rolling(window=params['pivot_window'], center=True).max()
        df['pivot_low'] = df['low'].rolling(window=params['pivot_window'], center=True).min()
        
        # MACD
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        self.df = df
    
    def _generate_signals(self):
        """生成交易信号"""
        df = self.df
        df['signal'] = 0  # 0: 无信号, 1: 做多, -1: 做空
        
        for i in range(20, len(df)):
            current_price = df['close'].iloc[i]
            recent_high = df['pivot_high'].iloc[i-5:i].max()
            recent_low = df['pivot_low'].iloc[i-5:i].min()
            atr = df['atr'].iloc[i]
            macd = df['macd'].iloc[i]
            macd_signal = df['macd_signal'].iloc[i]
            rsi = df['rsi'].iloc[i]
            
            # 做多条件：价格接近支撑 + MACD金叉 + RSI不超买
            if (current_price <= recent_low * 1.01 and 
                macd > macd_signal and 
                rsi < 70):
                df.loc[df.index[i], 'signal'] = 1
            
            # 做空条件：价格接近阻力 + MACD死叉 + RSI不超卖
            elif (current_price >= recent_high * 0.99 and 
                  macd < macd_signal and 
                  rsi > 30):
                df.loc[df.index[i], 'signal'] = -1
        
        self.df = df
    
    def _simulate_trades(self):
        """模拟交易"""
        df = self.df
        position = 0  # 0: 无持仓, 1: 多头, -1: 空头
        entry_price = 0
        entry_time = None
        capital = self.initial_capital
        
        self.equity_curve = [{'time': df['timestamp'].iloc[0], 'equity': capital}]
        
        for i in range(len(df)):
            current_time = df['timestamp'].iloc[i]
            current_price = df['close'].iloc[i]
            signal = df['signal'].iloc[i]
            atr = df['atr'].iloc[i]
            
            # 开仓
            if position == 0 and signal != 0:
                position = signal
                entry_price = current_price
                entry_time = current_time
                
                trade = {
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'side': 'LONG' if position == 1 else 'SHORT',
                    'sl': entry_price - atr * 1.5 * position,
                    'tp': entry_price + atr * 2.0 * position
                }
            
            # 平仓逻辑（简化版：固定止盈止损）
            elif position != 0:
                # 计算盈亏
                if position == 1:  # 多头
                    pnl = (current_price - entry_price) / entry_price * self.leverage
                    # 止损或止盈
                    if current_price <= trade['sl'] or current_price >= trade['tp'] or signal == -1:
                        trade['exit_time'] = current_time
                        trade['exit_price'] = current_price
                        trade['pnl'] = pnl
                        trade['pnl_amount'] = capital * pnl
                        self.trades.append(trade)
                        capital += trade['pnl_amount']
                        position = 0
                
                else:  # 空头
                    pnl = (entry_price - current_price) / entry_price * self.leverage
                    if current_price >= trade['sl'] or current_price <= trade['tp'] or signal == 1:
                        trade['exit_time'] = current_time
                        trade['exit_price'] = current_price
                        trade['pnl'] = pnl
                        trade['pnl_amount'] = capital * pnl
                        self.trades.append(trade)
                        capital += trade['pnl_amount']
                        position = 0
            
            # 记录权益曲线
            if position == 0:
                self.equity_curve.append({'time': current_time, 'equity': capital})
            else:
                # 计算浮动盈亏
                if position == 1:
                    unrealized_pnl = (current_price - entry_price) / entry_price * self.leverage
                else:
                    unrealized_pnl = (entry_price - current_price) / entry_price * self.leverage
                self.equity_curve.append({'time': current_time, 'equity': capital * (1 + unrealized_pnl)})
        
        self.final_capital = capital
    
    def _calculate_statistics(self):
        """计算回测统计"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_return': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'profit_factor': 0
            }
        
        trades_df = pd.DataFrame(self.trades)
        
        # 基本统计
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] <= 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        
        # 收益
        total_return = (self.final_capital - self.initial_capital) / self.initial_capital * 100
        
        # 最大回撤
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['peak'] = equity_df['equity'].cummax()
        equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
        max_drawdown = equity_df['drawdown'].min()
        
        # 夏普比率（简化版）
        returns = equity_df['equity'].pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() != 0 else 0
        
        # 盈亏比
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(trades_df[trades_df['pnl'] <= 0]['pnl'].mean()) if losing_trades > 0 else 1
        profit_factor = avg_win / avg_loss if avg_loss != 0 else 0
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor,
            'trades': trades_df,
            'equity_curve': equity_df
        }

# 测试
if __name__ == '__main__':
    print("回测模块")
