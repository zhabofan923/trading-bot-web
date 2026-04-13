#!/usr/bin/env python3
"""测试 WEEX API 连接"""

import requests
import pandas as pd
from datetime import datetime

# 测试不同的 API 端点
test_urls = [
    "https://api.weex.com/api/spot/v1/market/candles?symbol=btcusdt_spbl&period=1h&limit=10",
    "https://api.weex.com/api/spot/v1/market/ticker?symbol=btcusdt_spbl",
    "https://www.weex.com/api/spot/v1/market/candles?symbol=btcusdt_spbl&period=1h&limit=10",
]

print("测试 WEEX API 连接...\n")

for url in test_urls:
    print(f"测试: {url}")
    try:
        # 尝试不使用 SSL 验证
        response = requests.get(url, timeout=10, verify=False)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"响应: {response.text[:200]}...")
            print("✅ 成功!\n")
        else:
            print(f"❌ 失败: {response.text[:100]}\n")
    except Exception as e:
        print(f"❌ 错误: {e}\n")

# 测试 OKX 作为对比
print("\n测试 OKX API 作为对比...")
okx_url = "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT"
try:
    response = requests.get(okx_url, timeout=10)
    print(f"OKX 状态码: {response.status_code}")
    if response.status_code == 200:
        print("✅ OKX 连接成功!\n")
    else:
        print(f"❌ OKX 失败\n")
except Exception as e:
    print(f"❌ OKX 错误: {e}\n")
