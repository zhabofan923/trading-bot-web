"""
邮件通知模块
用于发送交易预警和通知
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class EmailNotifier:
    def __init__(self, smtp_server="smtp.qq.com", smtp_port=587, 
                 sender_email=None, sender_password=None, receiver_email=None):
        """
        初始化邮件通知器
        
        smtp_server: SMTP服务器地址
        smtp_port: SMTP端口
        sender_email: 发件人邮箱
        sender_password: 发件人邮箱授权码/密码
        receiver_email: 收件人邮箱
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.receiver_email = receiver_email
    
    def send_email(self, subject, content, html_content=None):
        """
        发送邮件
        
        subject: 邮件主题
        content: 邮件正文（纯文本）
        html_content: HTML格式正文（可选）
        """
        if not all([self.sender_email, self.sender_password, self.receiver_email]):
            print("邮件配置不完整")
            return False
        
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.receiver_email
            
            # 添加纯文本内容
            msg.attach(MIMEText(content, 'plain', 'utf-8'))
            
            # 添加HTML内容（如果提供）
            if html_content:
                msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            # 连接SMTP服务器并发送
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.receiver_email, msg.as_string())
            
            return True
            
        except Exception as e:
            print(f"发送邮件失败: {e}")
            return False
    
    def send_price_alert(self, symbol, current_price, target_price, alert_type):
        """发送价格预警邮件"""
        subject = f"🚨 {symbol} 价格预警"
        content = f"""
交易对: {symbol}
当前价格: ${current_price:,.2f}
预警价格: ${target_price:,.2f}
预警类型: {alert_type}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #ff6b6b;">🚨 {symbol} 价格预警</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>交易对</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{symbol}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>当前价格</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${current_price:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>预警价格</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${target_price:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>预警类型</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert_type}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>时间</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
        </body>
        </html>
        """
        return self.send_email(subject, content, html_content)
    
    def send_signal_alert(self, symbol, signal_type, entry_price, sl_price, tp_price):
        """发送交易信号预警邮件"""
        emoji = "🟢 做多" if signal_type == "LONG" else "🔴 做空"
        subject = f"{emoji} {symbol} 交易信号"
        content = f"""
交易对: {symbol}
信号类型: {'做多' if signal_type == 'LONG' else '做空'}
建议入场: ${entry_price:,.2f}
止损价格: ${sl_price:,.2f}
止盈价格: ${tp_price:,.2f}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        color = "#51cf66" if signal_type == "LONG" else "#ff6b6b"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: {color};">{emoji} {symbol} 交易信号</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>交易对</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{symbol}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>信号类型</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{'做多' if signal_type == 'LONG' else '做空'}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>建议入场</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${entry_price:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>止损价格</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${sl_price:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>止盈价格</strong></td><td style="padding: 8px; border: 1px solid #ddd;">${tp_price:,.2f}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>时间</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
        </body>
        </html>
        """
        return self.send_email(subject, content, html_content)
    
    def send_position_alert(self, symbol, side, size, pnl, pnl_percent):
        """发送持仓盈亏预警邮件"""
        emoji = "📈 盈利" if pnl >= 0 else "📉 亏损"
        subject = f"{emoji} {symbol} 持仓提醒"
        content = f"""
交易对: {symbol}
持仓方向: {side}
持仓数量: {size}
当前盈亏: {pnl:+.2f} USDT ({pnl_percent:+.2f}%)
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        color = "#51cf66" if pnl >= 0 else "#ff6b6b"
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: {color};">{emoji} {symbol} 持仓提醒</h2>
            <table style="border-collapse: collapse; width: 100%;">
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>交易对</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{symbol}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>持仓方向</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{side}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>持仓数量</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{size}</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>当前盈亏</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: {color}; font-weight: bold;">{pnl:+.2f} USDT ({pnl_percent:+.2f}%)</td></tr>
                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>时间</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
            </table>
        </body>
        </html>
        """
        return self.send_email(subject, content, html_content)

# 测试
if __name__ == '__main__':
    print("邮件通知模块")
    print("请配置邮箱信息后使用")
