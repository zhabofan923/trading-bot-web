"""
数据导出模块
导出交易记录和报表
"""

import pandas as pd
from datetime import datetime, timedelta
import json

class DataExporter:
    def __init__(self, trade_history, account_data=None):
        """
        初始化数据导出器
        
        trade_history: 交易记录列表
        account_data: 账户数据
        """
        self.trade_history = trade_history
        self.account_data = account_data
    
    def export_to_excel(self, filename=None):
        """导出到 Excel"""
        if not filename:
            filename = f"trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 创建 Excel writer
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # 交易记录
            if self.trade_history:
                df_trades = pd.DataFrame(self.trade_history)
                df_trades.to_excel(writer, sheet_name='交易记录', index=False)
            
            # 统计摘要
            summary = self._generate_summary()
            df_summary = pd.DataFrame([summary])
            df_summary.to_excel(writer, sheet_name='统计摘要', index=False)
            
            # 月度统计
            monthly = self._generate_monthly_stats()
            if monthly:
                df_monthly = pd.DataFrame(monthly)
                df_monthly.to_excel(writer, sheet_name='月度统计', index=False)
        
        return filename
    
    def export_to_csv(self, filename=None):
        """导出到 CSV"""
        if not filename:
            filename = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        if self.trade_history:
            df = pd.DataFrame(self.trade_history)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            return filename
        return None
    
    def export_to_json(self, filename=None):
        """导出到 JSON"""
        if not filename:
            filename = f"trading_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = {
            'export_time': datetime.now().isoformat(),
            'trade_history': self.trade_history,
            'summary': self._generate_summary(),
            'monthly_stats': self._generate_monthly_stats()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filename
    
    def _generate_summary(self):
        """生成统计摘要"""
        if not self.trade_history:
            return {
                '总交易次数': 0,
                '盈利次数': 0,
                '亏损次数': 0,
                '胜率': 0,
                '总盈亏': 0,
                '平均盈利': 0,
                '平均亏损': 0,
                '盈亏比': 0
            }
        
        df = pd.DataFrame(self.trade_history)
        
        total_trades = len(df)
        winning_trades = len(df[df['pnl'] > 0])
        losing_trades = len(df[df['pnl'] <= 0])
        win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
        total_pnl = df['pnl'].sum()
        
        avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = abs(df[df['pnl'] <= 0]['pnl'].mean()) if losing_trades > 0 else 1
        profit_factor = avg_win / avg_loss if avg_loss != 0 else 0
        
        return {
            '总交易次数': total_trades,
            '盈利次数': winning_trades,
            '亏损次数': losing_trades,
            '胜率': f"{win_rate:.2f}%",
            '总盈亏': f"{total_pnl:.2f} USDT",
            '平均盈利': f"{avg_win:.2f} USDT",
            '平均亏损': f"-{avg_loss:.2f} USDT",
            '盈亏比': f"{profit_factor:.2f}"
        }
    
    def _generate_monthly_stats(self):
        """生成月度统计"""
        if not self.trade_history:
            return []
        
        df = pd.DataFrame(self.trade_history)
        df['时间'] = pd.to_datetime(df['时间'])
        df['月份'] = df['时间'].dt.to_period('M')
        
        monthly = []
        for month, group in df.groupby('月份'):
            winning = len(group[group['pnl'] > 0])
            losing = len(group[group['pnl'] <= 0])
            total_pnl = group['pnl'].sum()
            
            monthly.append({
                '月份': str(month),
                '交易次数': len(group),
                '盈利次数': winning,
                '亏损次数': losing,
                '月度盈亏': f"{total_pnl:.2f} USDT",
                '胜率': f"{winning/len(group)*100:.1f}%" if len(group) > 0 else "0%"
            })
        
        return monthly
    
    def generate_tax_report(self, year=None):
        """生成税务报表"""
        if not year:
            year = datetime.now().year
        
        if not self.trade_history:
            return None
        
        df = pd.DataFrame(self.trade_history)
        df['时间'] = pd.to_datetime(df['时间'])
        df['年份'] = df['时间'].dt.year
        
        # 筛选指定年份
        df_year = df[df['年份'] == year]
        
        if df_year.empty:
            return None
        
        # 计算年度统计
        total_pnl = df_year['pnl'].sum()
        total_trades = len(df_year)
        
        report = {
            '年份': year,
            '总交易次数': total_trades,
            '年度总盈亏': total_pnl,
            '已实现盈亏': df_year[df_year['类型'] == '平仓']['pnl'].sum(),
            '交易明细': df_year.to_dict('records')
        }
        
        return report

# 测试
if __name__ == '__main__':
    print("数据导出模块")
