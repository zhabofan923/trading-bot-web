"""
飞书通知模块
用于发送交易预警和通知
"""

import requests
import json
from datetime import datetime

class FeishuNotifier:
    def __init__(self, webhook_url=None):
        """
        初始化飞书通知器
        webhook_url: 飞书机器人的 webhook 地址
        """
        self.webhook_url = webhook_url
    
    def send_message(self, title, content, msg_type="text"):
        """
        发送飞书消息
        
        title: 消息标题
        content: 消息内容
        msg_type: 消息类型 (text, markdown, interactive)
        """
        if not self.webhook_url:
            print("飞书 webhook 未配置")
            return False
        
        try:
            if msg_type == "text":
                payload = {
                    "msg_type": "text",
                    "content": {
                        "text": f"{title}\n\n{content}"
                    }
                }
            elif msg_type == "markdown":
                payload = {
                    "msg_type": "post",
                    "content": {
                        "post": {
                            "zh_cn": {
                                "title": title,
                                "content": [
                                    [{
                                        "tag": "text",
                                        "text": content
                                    }]
                                ]
                            }
                        }
                    }
                }
            else:
                payload = {
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {
                                "tag": "plain_text",
                                "content": title
                            },
                            "template": "blue"
                        },
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "tag": "lark_md",
                                    "content": content
                                }
                            }
                        ]
                    }
                }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    return True
                else:
                    print(f"飞书发送失败: {result}")
                    return False
            else:
                print(f"飞书请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"发送飞书消息失败: {e}")
            return False
    
    def send_price_alert(self, symbol, current_price, target_price, alert_type):
        """发送价格预警"""
        title = f"🚨 {symbol} 价格预警"
        content = f"""
**交易对**: {symbol}
**当前价格**: ${current_price:,.2f}
**预警价格**: ${target_price:,.2f}
**预警类型**: {alert_type}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(title, content, "interactive")
    
    def send_signal_alert(self, symbol, signal_type, entry_price, sl_price, tp_price):
        """发送交易信号预警"""
        emoji = "🟢" if signal_type == "LONG" else "🔴"
        title = f"{emoji} {symbol} 交易信号"
        content = f"""
**交易对**: {symbol}
**信号类型**: {'做多' if signal_type == 'LONG' else '做空'}
**建议入场**: ${entry_price:,.2f}
**止损价格**: ${sl_price:,.2f}
**止盈价格**: ${tp_price:,.2f}
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(title, content, "interactive")
    
    def send_position_alert(self, symbol, side, size, pnl, pnl_percent):
        """发送持仓盈亏预警"""
        emoji = "📈" if pnl >= 0 else "📉"
        title = f"{emoji} {symbol} 持仓提醒"
        content = f"""
**交易对**: {symbol}
**持仓方向**: {side}
**持仓数量**: {size}
**当前盈亏**: {pnl:+.2f} USDT ({pnl_percent:+.2f}%)
**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        return self.send_message(title, content, "interactive")

# 测试
if __name__ == '__main__':
    # 测试代码
    notifier = FeishuNotifier()
    print("飞书通知模块测试")
    print("请配置 webhook_url 后使用")
