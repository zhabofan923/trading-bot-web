"""
自动化交易模块
实现信号触发自动下单
"""

import time
import threading
from datetime import datetime, timedelta

class AutoTrader:
    def __init__(self, weex_api, risk_manager, email_notifier=None):
        """
        初始化自动交易器
        
        weex_api: WEEX API 实例
        risk_manager: 风险管理器实例
        email_notifier: 邮件通知器实例
        """
        self.weex_api = weex_api
        self.risk_manager = risk_manager
        self.email_notifier = email_notifier
        self.is_running = False
        self.trading_thread = None
        self.trading_symbol = None
        self.trading_params = {}
        self.last_signal = None
        self.trade_log = []
    
    def start(self, symbol, trade_amount, leverage, check_interval=60):
        """
        启动自动交易
        
        symbol: 交易对
        trade_amount: 交易数量
        leverage: 杠杆倍数
        check_interval: 检查信号间隔（秒）
        """
        if self.is_running:
            return False, "自动交易已在运行"
        
        self.trading_symbol = symbol
        self.trading_params = {
            'amount': trade_amount,
            'leverage': leverage,
            'interval': check_interval
        }
        self.is_running = True
        
        # 启动交易线程
        self.trading_thread = threading.Thread(target=self._trading_loop)
        self.trading_thread.daemon = True
        self.trading_thread.start()
        
        # 发送启动通知
        if self.email_notifier:
            self.email_notifier.send_email(
                "自动交易已启动",
                f"交易对: {symbol}\n数量: {trade_amount}\n杠杆: {leverage}x\n时间: {datetime.now()}",
                f"<h2>🚀 自动交易已启动</h2><p>交易对: {symbol}<br>数量: {trade_amount}<br>杠杆: {leverage}x</p>"
            )
        
        return True, "自动交易已启动"
    
    def stop(self):
        """停止自动交易"""
        if not self.is_running:
            return False, "自动交易未运行"
        
        self.is_running = False
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        
        # 发送停止通知
        if self.email_notifier:
            self.email_notifier.send_email(
                "自动交易已停止",
                f"交易对: {self.trading_symbol}\n时间: {datetime.now()}",
                f"<h2>⏹️ 自动交易已停止</h2><p>交易对: {self.trading_symbol}</p>"
            )
        
        return True, "自动交易已停止"
    
    def _trading_loop(self):
        """交易主循环"""
        while self.is_running:
            try:
                # 获取最新数据
                df = self.weex_api.get_ohlcv(self.trading_symbol, '15m', 100)
                if df is None or df.empty:
                    time.sleep(self.trading_params['interval'])
                    continue
                
                # 计算信号（简化版）
                signal = self._calculate_signal(df)
                
                # 检查是否有新信号
                if signal != self.last_signal and signal in ['LONG', 'SHORT']:
                    # 风险检查
                    total_capital = 10000  # 简化，实际应从账户获取
                    trade_value = self.trading_params['amount'] * df['close'].iloc[-1]
                    
                    allowed, reason = self.risk_manager.check_trade_allowed(
                        trade_value, total_capital
                    )
                    
                    if allowed:
                        # 执行交易
                        self._execute_trade(signal, df['close'].iloc[-1])
                    else:
                        # 记录风险阻止
                        self.trade_log.append({
                            'time': datetime.now(),
                            'action': 'BLOCKED',
                            'reason': reason,
                            'signal': signal
                        })
                
                self.last_signal = signal
                
                # 检查持仓盈亏（自动止盈止损）
                self._check_positions()
                
            except Exception as e:
                print(f"自动交易循环错误: {e}")
            
            time.sleep(self.trading_params['interval'])
    
    def _calculate_signal(self, df):
        """计算交易信号"""
        # 简化版：基于支撑压力和MACD
        current_price = df['close'].iloc[-1]
        
        # 计算支撑压力
        pivot_high = df['high'].rolling(window=10, center=True).max().iloc[-1]
        pivot_low = df['low'].rolling(window=10, center=True).min().iloc[-1]
        
        # 计算MACD
        ema12 = df['close'].ewm(span=12, adjust=False).mean().iloc[-1]
        ema26 = df['close'].ewm(span=26, adjust=False).mean().iloc[-1]
        macd = ema12 - ema26
        
        # 信号判断
        if current_price <= pivot_low * 1.01 and macd > 0:
            return 'LONG'
        elif current_price >= pivot_high * 0.99 and macd < 0:
            return 'SHORT'
        
        return 'WAIT'
    
    def _execute_trade(self, signal, price):
        """执行交易"""
        side = 'BUY' if signal == 'LONG' else 'SELL'
        position_side = 'LONG' if signal == 'LONG' else 'SHORT'
        
        # 下单
        result = self.weex_api.place_order(
            symbol=self.trading_symbol,
            side=side,
            position_side=position_side,
            order_type='MARKET',
            quantity=self.trading_params['amount']
        )
        
        # 记录交易
        trade_record = {
            'time': datetime.now(),
            'signal': signal,
            'price': price,
            'amount': self.trading_params['amount'],
            'result': result
        }
        self.trade_log.append(trade_record)
        
        # 发送通知
        if self.email_notifier and result.get('success'):
            self.email_notifier.send_email(
                f"自动交易执行 - {signal}",
                f"信号: {signal}\n价格: {price}\n数量: {self.trading_params['amount']}",
                f"<h2>🚀 自动交易执行</h2><p>信号: {signal}<br>价格: {price}<br>数量: {self.trading_params['amount']}</p>"
            )
    
    def _check_positions(self):
        """检查持仓（自动止盈止损）"""
        positions = self.weex_api.get_positions(self.trading_symbol)
        if not positions:
            return
        
        for pos in positions:
            unrealized_pnl = float(pos.get('unrealizePnl', 0))
            
            # 如果盈亏达到阈值，自动平仓
            if abs(unrealized_pnl) > 100:  # 简化阈值
                # 执行平仓
                self.weex_api.place_order(
                    symbol=pos['symbol'],
                    side='SELL' if pos['side'] == 'LONG' else 'BUY',
                    position_side=pos['side'],
                    order_type='MARKET',
                    quantity=pos['size']
                )
    
    def get_status(self):
        """获取运行状态"""
        return {
            'is_running': self.is_running,
            'symbol': self.trading_symbol,
            'params': self.trading_params,
            'last_signal': self.last_signal,
            'recent_trades': self.trade_log[-10:]  # 最近10条记录
        }

# 测试
if __name__ == '__main__':
    print("自动交易模块")
