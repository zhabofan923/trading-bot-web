"""
风险控制模块
高级风险管理功能
"""

import pandas as pd
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self, daily_loss_limit=1000, max_trades_per_day=10, 
                 consecutive_loss_limit=3, max_position_size=0.1):
        """
        初始化风险管理器
        
        daily_loss_limit: 每日最大亏损（USDT）
        max_trades_per_day: 每日最大交易次数
        consecutive_loss_limit: 连续亏损次数限制
        max_position_size: 最大仓位比例（相对于总资金）
        """
        self.daily_loss_limit = daily_loss_limit
        self.max_trades_per_day = max_trades_per_day
        self.consecutive_loss_limit = consecutive_loss_limit
        self.max_position_size = max_position_size
        
        # 状态记录
        self.daily_stats = {
            'date': datetime.now().date(),
            'trades_count': 0,
            'daily_pnl': 0,
            'consecutive_losses': 0
        }
        
        self.risk_events = []
    
    def check_trade_allowed(self, trade_size, total_capital, current_positions=None):
        """
        检查是否允许交易
        
        返回: (是否允许, 原因)
        """
        # 检查每日交易次数
        if self.daily_stats['trades_count'] >= self.max_trades_per_day:
            return False, f"今日交易次数已达上限 ({self.max_trades_per_day}次)"
        
        # 检查每日亏损限制
        if self.daily_stats['daily_pnl'] <= -self.daily_loss_limit:
            return False, f"今日亏损已达上限 (-{self.daily_loss_limit} USDT)，暂停交易"
        
        # 检查连续亏损
        if self.daily_stats['consecutive_losses'] >= self.consecutive_loss_limit:
            return False, f"连续亏损{self.consecutive_losses}次，暂停交易保护"
        
        # 检查仓位大小
        position_ratio = trade_size / total_capital if total_capital > 0 else 1
        if position_ratio > self.max_position_size:
            return False, f"仓位过大 ({position_ratio:.1%})，最大允许 {self.max_position_size:.1%}"
        
        return True, "风险检查通过"
    
    def record_trade(self, pnl, trade_size):
        """记录交易结果"""
        # 重置每日统计（如果是新的一天）
        current_date = datetime.now().date()
        if current_date != self.daily_stats['date']:
            self.daily_stats = {
                'date': current_date,
                'trades_count': 0,
                'daily_pnl': 0,
                'consecutive_losses': 0
            }
        
        # 更新统计
        self.daily_stats['trades_count'] += 1
        self.daily_stats['daily_pnl'] += pnl
        
        # 更新连续亏损
        if pnl < 0:
            self.daily_stats['consecutive_losses'] += 1
        else:
            self.daily_stats['consecutive_losses'] = 0
        
        # 记录风险事件
        if pnl <= -self.daily_loss_limit * 0.5:  # 单笔大亏损
            self.risk_events.append({
                'time': datetime.now(),
                'type': '大额亏损',
                'message': f'单笔亏损 {pnl:.2f} USDT',
                'severity': 'high'
            })
    
    def calculate_position_size(self, capital, risk_per_trade=0.02, stop_loss_pct=0.02):
        """
        计算建议仓位大小（凯利公式简化版）
        
        capital: 总资金
        risk_per_trade: 每笔交易风险比例
        stop_loss_pct: 止损比例
        """
        # 基础仓位 = 资金 * 单笔风险 / 止损比例
        position_size = capital * risk_per_trade / stop_loss_pct
        
        # 限制最大仓位
        max_position = capital * self.max_position_size
        position_size = min(position_size, max_position)
        
        return position_size
    
    def get_risk_report(self):
        """获取风险报告"""
        return {
            'daily_trades': self.daily_stats['trades_count'],
            'daily_pnl': self.daily_stats['daily_pnl'],
            'consecutive_losses': self.daily_stats['consecutive_losses'],
            'daily_loss_remaining': self.daily_loss_limit + self.daily_stats['daily_pnl'],
            'trades_remaining': self.max_trades_per_day - self.daily_stats['trades_count'],
            'risk_events': self.risk_events[-10:]  # 最近10条
        }
    
    def should_close_all_positions(self, total_unrealized_pnl, total_capital):
        """
        判断是否应该全部平仓（熔断机制）
        
        total_unrealized_pnl: 总浮动盈亏
        total_capital: 总资金
        """
        # 检查总亏损是否超过限制
        if total_unrealized_pnl <= -self.daily_loss_limit * 1.5:
            return True, f"总亏损超过熔断阈值 ({-self.daily_loss_limit * 1.5} USDT)，强制平仓"
        
        # 检查资金回撤是否过大（超过20%）
        drawdown_pct = abs(total_unrealized_pnl) / total_capital if total_capital > 0 else 0
        if drawdown_pct > 0.20:
            return True, f"资金回撤过大 ({drawdown_pct:.1%})，强制平仓保护"
        
        return False, ""

# 测试
if __name__ == '__main__':
    print("风险控制模块")
