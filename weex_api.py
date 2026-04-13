"""
WEEX API 接口 - 合约交易
直接调用 WEEX REST API，不依赖 CCXT
文档: https://www.weex.com/api-doc/zh-CN/contract/Market_API/GetKlines
"""

import requests
import pandas as pd
from datetime import datetime
import hmac
import hashlib
import base64
import json
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class WeexAPI:
    def __init__(self, api_key=None, api_secret=None, passphrase=None, testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet
        
        # WEEX 合约 API 基础URL
        if testnet:
            self.base_url = "https://api-testnet.weex.com"
        else:
            self.base_url = "https://api-contract.weex.com"
    
    def _generate_signature(self, timestamp, method, request_path, body=''):
        """生成签名"""
        if self.api_secret is None:
            return None
        
        message = timestamp + method.upper() + request_path + body
        mac = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        )
        signature = base64.b64encode(mac.digest()).decode('utf-8')
        return signature
    
    def _get_headers(self, method, request_path, body=''):
        """获取请求头（用于需要认证的接口）"""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.api_key:
            timestamp = str(int(datetime.now().timestamp() * 1000))
            signature = self._generate_signature(timestamp, method, request_path, body)
            
            headers['ACCESS-KEY'] = self.api_key
            headers['ACCESS-SIGN'] = signature
            headers['ACCESS-TIMESTAMP'] = timestamp
            headers['ACCESS-PASSPHRASE'] = self.passphrase or ''
        
        return headers
    
    def get_ohlcv(self, symbol, timeframe='1h', limit=100):
        """
        获取K线数据
        
        symbol: 交易对，如 BTCUSDT
        timeframe: 时间周期，如 1h, 15m
        limit: 获取条数，1-1000
        """
        try:
            # 构建请求 - WEEX 合约 API V3 格式
            url = f"{self.base_url}/capi/v3/market/klines"
            params = {
                'symbol': symbol.upper(),
                'interval': timeframe,
                'limit': limit
            }
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    # 解析数据
                    df = pd.DataFrame(data, columns=[
                        'timestamp', 'open', 'high', 'low', 'close', 'volume',
                        'close_time', 'quote_volume', 'trades', 'taker_buy_volume', 'taker_buy_quote'
                    ])
                    
                    # 转换数据类型
                    df['timestamp'] = pd.to_datetime(df['timestamp'].astype(float), unit='ms')
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['close'] = df['close'].astype(float)
                    df['volume'] = df['volume'].astype(float)
                    
                    # 按时间排序
                    df = df.sort_values('timestamp').reset_index(drop=True)
                    
                    return df
                else:
                    print(f"WEEX API 返回空数据: {data}")
                    return None
            else:
                print(f"请求失败: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return None
    
    def get_ticker(self, symbol):
        """获取24小时行情统计"""
        try:
            url = f"{self.base_url}/capi/v3/market/ticker/24hr"
            params = {'symbol': symbol.upper()}
            
            response = requests.get(url, params=params, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    return float(data[0]['lastPrice'])
                elif isinstance(data, dict):
                    return float(data.get('lastPrice', 0))
            return None
        except Exception as e:
            print(f"获取价格失败: {e}")
            return None
    
    def get_server_time(self):
        """获取服务器时间"""
        try:
            url = f"{self.base_url}/capi/v3/market/time"
            response = requests.get(url, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('serverTime')
            return None
        except Exception as e:
            print(f"获取服务器时间失败: {e}")
            return None
    
    def get_all_symbols(self):
        """获取所有交易对"""
        try:
            url = f"{self.base_url}/capi/v3/market/apiTradingSymbols"
            response = requests.get(url, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return data
            return None
        except Exception as e:
            print(f"获取交易对失败: {e}")
            return None
    
    def get_exchange_info(self):
        """获取交易所信息（包含所有交易对详情）"""
        try:
            url = f"{self.base_url}/capi/v3/market/exchangeInfo"
            response = requests.get(url, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                return data
            return None
        except Exception as e:
            print(f"获取交易所信息失败: {e}")
            return None
    
    def get_symbol_leverage(self, symbol):
        """
        获取指定交易对的最大杠杆倍数
        """
        try:
            exchange_info = self.get_exchange_info()
            if exchange_info and 'symbols' in exchange_info:
                for s in exchange_info['symbols']:
                    if s.get('symbol') == symbol:
                        # 获取杠杆倍数
                        leverage = s.get('leverage', 20)  # 默认20倍
                        return int(leverage) if leverage else 20
            return 20  # 默认20倍
        except Exception as e:
            print(f"获取杠杆倍数失败: {e}")
            return 20
    
    def get_all_symbols_with_leverage(self):
        """
        获取所有交易对及其最大杠杆倍数
        """
        try:
            exchange_info = self.get_exchange_info()
            symbols_info = {}
            if exchange_info and 'symbols' in exchange_info:
                for s in exchange_info['symbols']:
                    symbol = s.get('symbol')
                    leverage = s.get('leverage', 20)
                    if symbol:
                        symbols_info[symbol] = {
                            'max_leverage': int(leverage) if leverage else 20,
                            'price_precision': s.get('pricePrecision', 2),
                            'quantity_precision': s.get('quantityPrecision', 3)
                        }
            return symbols_info
        except Exception as e:
            print(f"获取交易对信息失败: {e}")
            return {}
    
    def get_favorite_symbols(self):
        """
        获取用户自选交易对（需要API Key）
        从用户的持仓和账户配置中获取常用交易对
        """
        if not self.api_key:
            return None
        
        try:
            symbols = set()
            
            # 1. 从持仓中获取交易对
            positions = self.get_positions()
            if positions and isinstance(positions, list):
                for pos in positions:
                    symbol = pos.get('symbol')
                    if symbol:
                        symbols.add(symbol)
            
            # 2. 从账户配置中获取交易对
            request_path = '/capi/v3/account/symbolConfig'
            url = f"{self.base_url}{request_path}"
            headers = self._get_headers('GET', request_path)
            
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for item in data:
                        symbol = item.get('symbol')
                        if symbol:
                            symbols.add(symbol)
            
            return list(symbols) if symbols else None
        except Exception as e:
            print(f"获取自选交易对失败: {e}")
            return None
    
    def place_order(self, symbol, side, position_side, order_type, quantity, price=None, 
                   time_in_force='GTC', tp_trigger_price=None, sl_trigger_price=None):
        """
        下单
        
        symbol: 交易对，如 BTCUSDT
        side: BUY 或 SELL
        position_side: LONG 或 SHORT
        order_type: LIMIT 或 MARKET
        quantity: 数量
        price: 价格（限价单必填）
        time_in_force: GTC/IOC/FOK/POST_ONLY
        tp_trigger_price: 止盈触发价
        sl_trigger_price: 止损触发价
        """
        if not self.api_key:
            return {'success': False, 'error': 'API Key not configured'}
        
        try:
            request_path = '/capi/v3/order'
            url = f"{self.base_url}{request_path}"
            
            # 构建请求体
            body = {
                'symbol': symbol.upper(),
                'side': side.upper(),
                'positionSide': position_side.upper(),
                'type': order_type.upper(),
                'quantity': str(quantity),
                'timeInForce': time_in_force
            }
            
            if price and order_type.upper() == 'LIMIT':
                body['price'] = str(price)
            
            if tp_trigger_price:
                body['tpTriggerPrice'] = str(tp_trigger_price)
            
            if sl_trigger_price:
                body['slTriggerPrice'] = str(sl_trigger_price)
            
            body_json = json.dumps(body)
            headers = self._get_headers('POST', request_path, body_json)
            
            response = requests.post(url, headers=headers, data=body_json, timeout=10, verify=False)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {'success': False, 'error': f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_balance(self):
        """查询账户余额"""
        if not self.api_key:
            return None
        
        try:
            request_path = '/capi/v3/account/balance'
            url = f"{self.base_url}{request_path}"
            headers = self._get_headers('GET', request_path)
            
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"获取余额失败: {e}")
            return None
    
    def get_positions(self, symbol=None):
        """查询持仓"""
        if not self.api_key:
            return None
        
        try:
            if symbol:
                request_path = f'/capi/v3/account/position/singlePosition?symbol={symbol.upper()}'
            else:
                request_path = '/capi/v3/account/position/allPosition'
            
            url = f"{self.base_url}{request_path}"
            headers = self._get_headers('GET', request_path)
            
            response = requests.get(url, headers=headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"获取持仓失败: {e}")
            return None

# 测试
if __name__ == '__main__':
    weex = WeexAPI()
    
    # 测试获取服务器时间
    print("获取服务器时间...")
    server_time = weex.get_server_time()
    if server_time:
        print(f"服务器时间: {server_time}")
    else:
        print("获取失败")
    
    # 测试获取K线
    print("\n获取 BTCUSDT 1小时K线数据...")
    df = weex.get_ohlcv('BTCUSDT', '1h', 10)
    
    if df is not None:
        print(f"成功获取 {len(df)} 条数据")
        print(df.head())
    else:
        print("获取失败")
    
    # 测试获取价格
    print("\n获取最新价格...")
    price = weex.get_ticker('BTCUSDT')
    if price:
        print(f"BTCUSDT 最新价格: ${price:,.2f}")
    else:
        print("获取失败")
