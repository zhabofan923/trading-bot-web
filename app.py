import streamlit as st
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from weex_api import WeexAPI
from email_notifier import EmailNotifier
from backtest import Backtester
from risk_manager import RiskManager
from auto_trader import AutoTrader
from data_exporter import DataExporter

# 页面配置
st.set_page_config(
    page_title="交易机器人控制台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 使用 JavaScript 实现自动刷新
st.markdown("""
<script>
    // 每3秒自动刷新页面
    setTimeout(function(){
        window.location.reload();
    }, 3000);
</script>
""", unsafe_allow_html=True)

# 初始化 session state
if 'selected_symbol' not in st.session_state:
    st.session_state.selected_symbol = "BTC-USDT"
if 'selected_timeframe' not in st.session_state:
    st.session_state.selected_timeframe = "1h"
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'risk_manager' not in st.session_state:
    st.session_state.risk_manager = RiskManager()
if 'account_data' not in st.session_state:
    st.session_state.account_data = None
if 'positions_data' not in st.session_state:
    st.session_state.positions_data = None
if 'auto_trader' not in st.session_state:
    st.session_state.auto_trader = None
if 'auto_trading_enabled' not in st.session_state:
    st.session_state.auto_trading_enabled = False
if 'alert_sent' not in st.session_state:
    st.session_state.alert_sent = {'price_support': False, 'price_resistance': False, 'signal': None, 'position_pnl': {}}

# 标题
st.title("🤖 交易机器人控制台")
st.markdown("---")

# 侧边栏 - 配置
with st.sidebar:
    st.header("⚙️ 配置")
    
    # 交易所选择
    exchange = st.selectbox(
        "选择交易所",
        ["WEEX", "Binance", "OKX"],
        index=0
    )
    
    # API配置（WEEX 需要）
    with st.expander("API 配置（实盘交易需要）"):
        api_key = st.text_input("API Key", value="weex_e3799867e7c2fb63f3efe3b342d40070", type="password")
        api_secret = st.text_input("API Secret", value="34e4e4ef45f39af114912f16ce6227de5ad0792f555b5650c77cb1911acfcf41", type="password")
        passphrase = st.text_input("Passphrase", value="zbf1996411", type="password")
    
    # 邮件通知配置
    with st.expander("📧 邮件通知配置"):
        st.markdown('''
        **使用163邮箱发送:**
        1. 登录163邮箱网页版
        2. 点击 [设置] → [POP3/SMTP/IMAP]
        3. 开启 SMTP 服务
        4. 获取授权码（不是登录密码）
        ''')
        
        # 初始化邮箱配置 - 从本地文件加载或创建默认
        import json
        import os
        
        config_file = 'email_config.json'
        
        # 尝试从文件加载配置
        if 'email_config' not in st.session_state:
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        st.session_state.email_config = json.load(f)
                except:
                    st.session_state.email_config = {
                        'provider': "163邮箱",
                        'sender': "",
                        'auth_code': "",
                        'receiver': "",
                        'enable_price': True,
                        'enable_signal': True,
                        'enable_position': True,
                        'profit_threshold': 100.0,
                        'loss_threshold': -50.0
                    }
            else:
                st.session_state.email_config = {
                    'provider': "163邮箱",
                    'sender': "",
                    'auth_code': "",
                    'receiver': "",
                    'enable_price': True,
                    'enable_signal': True,
                    'enable_position': True,
                    'profit_threshold': 100.0,
                    'loss_threshold': -50.0
                }
        
        email_provider = st.selectbox("邮箱服务商", ["163邮箱", "QQ邮箱", "其他"], 
                                     index=["163邮箱", "QQ邮箱", "其他"].index(st.session_state.email_config['provider']),
                                     key="email_provider")
        st.session_state.email_config['provider'] = email_provider
        
        email_sender = st.text_input("发件人邮箱", value=st.session_state.email_config['sender'], 
                                    help="如：yourname@163.com", key="email_sender")
        st.session_state.email_config['sender'] = email_sender
        
        email_auth_code = st.text_input("授权码", type="password", 
                                       value=st.session_state.email_config['auth_code'],
                                       help="163邮箱授权码", key="email_auth_code")
        st.session_state.email_config['auth_code'] = email_auth_code
        
        email_receiver = st.text_input("收件人邮箱", value=st.session_state.email_config['receiver'],
                                      help="可以填同一个邮箱", key="email_receiver")
        st.session_state.email_config['receiver'] = email_receiver
        
        enable_price_alert = st.checkbox("启用价格预警", value=st.session_state.email_config['enable_price'],
                                        key="enable_price_alert")
        st.session_state.email_config['enable_price'] = enable_price_alert
        
        enable_signal_alert = st.checkbox("启用信号预警", value=st.session_state.email_config['enable_signal'],
                                         key="enable_signal_alert")
        st.session_state.email_config['enable_signal'] = enable_signal_alert
        
        enable_position_alert = st.checkbox("启用持仓预警", value=st.session_state.email_config['enable_position'],
                                           key="enable_position_alert")
        st.session_state.email_config['enable_position'] = enable_position_alert
        
        if enable_position_alert:
            st.subheader("持仓预警阈值")
            profit_threshold = st.number_input("盈利提醒 (USDT)", 
                                              value=st.session_state.email_config['profit_threshold'], 
                                              step=10.0, key="profit_threshold")
            st.session_state.email_config['profit_threshold'] = profit_threshold
            
            loss_threshold = st.number_input("亏损提醒 (USDT)", 
                                            value=st.session_state.email_config['loss_threshold'], 
                                            step=10.0, key="loss_threshold")
            st.session_state.email_config['loss_threshold'] = loss_threshold
        
        # 保存配置按钮
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 保存配置", key="save_email_config"):
                try:
                    with open(config_file, 'w') as f:
                        json.dump(st.session_state.email_config, f)
                    st.success("✅ 配置已保存到本地")
                except Exception as e:
                    st.error(f"❌ 保存失败: {e}")
        
        with col2:
            # 测试邮件按钮
            if email_sender and email_auth_code and email_receiver:
                if st.button("📤 发送测试邮件", key="test_email_btn"):
                    with st.spinner("发送中..."):
                        # 根据邮箱服务商选择SMTP服务器
                        if email_provider == "163邮箱":
                            smtp_server = "smtp.163.com"
                            smtp_port = 25
                        elif email_provider == "QQ邮箱":
                            smtp_server = "smtp.qq.com"
                            smtp_port = 587
                        else:
                            smtp_server = "smtp.163.com"
                            smtp_port = 25
                        
                        test_notifier = EmailNotifier(
                            smtp_server=smtp_server,
                            smtp_port=smtp_port,
                            sender_email=email_sender,
                            sender_password=email_auth_code,
                            receiver_email=email_receiver
                        )
                        
                        if test_notifier.send_email(
                            "交易机器人测试邮件",
                            "这是一封测试邮件，如果收到说明配置成功！",
                            "<h2>✅ 交易机器人邮件配置成功</h2><p>您的邮件通知功能已正常工作。</p>"
                        ):
                            st.success("✅ 测试邮件发送成功！请查收")
                        else:
                            st.error("❌ 发送失败，请检查邮箱和授权码")
            else:
                st.info("请填写完整的邮箱配置信息后测试")
    
    # 模式选择
    mode = st.radio("运行模式", ["实盘交易", "策略回测"], index=0)
    
    # 初始化邮件通知器
    email_notifier = None
    if email_sender and email_auth_code and email_receiver:
        # 根据邮箱服务商选择SMTP服务器
        if email_provider == "163邮箱":
            smtp_server = "smtp.163.com"
            smtp_port = 25
        elif email_provider == "QQ邮箱":
            smtp_server = "smtp.qq.com"
            smtp_port = 587
        else:
            smtp_server = "smtp.163.com"
            smtp_port = 25
        
        email_notifier = EmailNotifier(
            smtp_server=smtp_server,
            smtp_port=smtp_port,
            sender_email=email_sender,
            sender_password=email_auth_code,
            receiver_email=email_receiver
        )
    
    # 获取交易对列表和杠杆信息（不缓存，确保实时）
    def get_symbols_info():
        try:
            weex = WeexAPI()
            return weex.get_all_symbols_with_leverage()
        except:
            return {}
    
    symbols_info = get_symbols_info()
    
    # 获取交易对列表（从交易所获取所有USDT交易对）
    @st.cache_data(ttl=300)
    def get_all_usdt_symbols():
        try:
            weex = WeexAPI()
            symbols = weex.get_all_symbols()
            if symbols and isinstance(symbols, list):
                # 过滤USDT交易对并排序
                usdt_symbols = [s.replace('USDT', '-USDT') for s in symbols if isinstance(s, str) and 'USDT' in s and s.endswith('USDT')]
                # 优先显示主流币种
                priority = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT', 'BCH-USDT', 'XRP-USDT', 'DOGE-USDT', 'LTC-USDT', 'ETC-USDT', 'LINK-USDT', 'ADA-USDT']
                sorted_symbols = sorted(usdt_symbols, key=lambda x: (0 if x in priority else 1, x))
                return sorted_symbols if sorted_symbols else ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT"]
            return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT"]
        except:
            return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT"]
    
    available_symbols = get_all_usdt_symbols()
    st.caption(f"📊 共 {len(available_symbols)} 个交易对")
    
    # 交易对选择 - 关键：使用 on_change 回调
    def on_symbol_change():
        st.session_state.selected_symbol = st.session_state.symbol_selector
    
    symbol = st.selectbox(
        "交易对",
        available_symbols,
        index=available_symbols.index(st.session_state.selected_symbol) if st.session_state.selected_symbol in available_symbols else 0,
        key="symbol_selector",
        on_change=on_symbol_change
    )
    
    # 时间周期选择
    def on_timeframe_change():
        st.session_state.selected_timeframe = st.session_state.timeframe_selector
    
    timeframe = st.selectbox(
        "时间周期",
        ["1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d"],
        index=["1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d"].index(st.session_state.selected_timeframe),
        key="timeframe_selector",
        on_change=on_timeframe_change
    )
    
    # 根据当前币种获取最大杠杆
    weex_symbol = st.session_state.selected_symbol.replace('-', '')
    max_leverage = 400  # WEEX 默认最高400倍
    
    # 调试信息
    st.caption(f"当前币种: {weex_symbol}")
    
    if weex_symbol in symbols_info:
        max_leverage = symbols_info[weex_symbol].get('max_leverage', 400)
        st.caption(f"{weex_symbol} 最大杠杆: {max_leverage}x")
    else:
        # 如果找不到，尝试从API实时获取
        try:
            weex_temp = WeexAPI()
            max_leverage = weex_temp.get_symbol_leverage(weex_symbol)
            st.caption(f"{weex_symbol} 实时杠杆: {max_leverage}x")
        except:
            max_leverage = 400
            st.caption(f"{weex_symbol} 默认杠杆: {max_leverage}x")
    
    # 生成杠杆选项（1到最大杠杆，支持最高400x）
    leverage_options = [1, 2, 3, 5, 10, 20, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400]
    available_leverages = [l for l in leverage_options if l <= max_leverage]
    default_leverage_index = min(2, len(available_leverages) - 1)
    
    # 杠杆风险提示
    if max_leverage >= 100:
        st.warning("⚠️ **高风险警告**: 该币种支持 100x 以上杠杆，爆仓风险极高！建议新手使用 10-20x")
    
    # 回测参数（仅在回测模式显示）
    if mode == "策略回测":
        st.subheader("📊 回测参数")
        initial_capital = st.number_input("初始资金 (USDT)", value=10000, step=1000)
        backtest_leverage = st.selectbox(
            f"回测杠杆 (最大{max_leverage}x)",
            available_leverages,
            index=default_leverage_index,
            key="backtest_leverage"
        )
        atr_sl = st.slider("止损倍数(ATR)", 0.5, 3.0, 1.5, 0.1, key="backtest_sl")
        atr_tp = st.slider("止盈倍数(ATR)", 0.5, 5.0, 2.0, 0.1, key="backtest_tp")
        
        if st.button("🚀 开始回测", type="primary"):
            st.session_state.run_backtest = True
            st.session_state.backtest_params = {
                'initial_capital': initial_capital,
                'leverage': backtest_leverage,
                'atr_multiplier_sl': atr_sl,
                'atr_multiplier_tp': atr_tp
            }
    
    # 策略参数
    st.subheader("策略参数")
    pivot_length = st.slider("枢轴点长度", 5, 50, 10)
    atr_length = st.slider("ATR周期", 5, 30, 14)
    sl_multiplier = st.slider("止损倍数(ATR)", 0.5, 3.0, 1.5, 0.1)
    tp_multiplier = st.slider("止盈倍数(ATR)", 0.5, 5.0, 2.0, 0.1)

# 使用 session state 中的值
current_symbol = st.session_state.selected_symbol
current_timeframe = st.session_state.selected_timeframe

st.write(f"**当前交易对**: {current_symbol} | **时间周期**: {current_timeframe}")

# 获取数据
def fetch_ohlcv(exchange_name, symbol, timeframe, limit=100):
    try:
        if exchange_name.lower() == 'weex':
            weex = WeexAPI()
            weex_symbol = symbol.replace('-', '')
            return weex.get_ohlcv(weex_symbol, timeframe, limit)
        return None
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return None

with st.spinner(f"正在获取 {current_symbol} 数据..."):
    df = fetch_ohlcv(exchange, current_symbol, current_timeframe)

# 如果获取失败，使用模拟数据
if df is None or df.empty:
    st.warning("无法获取交易所数据，使用模拟数据")
    np.random.seed(42)
    n = 100
    dates = pd.date_range(end=datetime.now(), periods=n, freq='1H')
    returns = np.random.normal(0.0001, 0.01, n)
    prices = 42000 * np.exp(np.cumsum(returns))
    df = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.normal(0, 0.001, n)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.005, n))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.005, n))),
        'close': prices,
        'volume': np.random.uniform(100, 1000, n)
    })

# 计算指标
current_price = df['close'].iloc[-1]
price_change = ((df['close'].iloc[-1] - df['close'].iloc[-24]) / df['close'].iloc[-24] * 100) if len(df) >= 24 else 0

# 计算支撑压力和技术指标
df['pivot_high'] = df['high'].rolling(window=10, center=True).max()
df['pivot_low'] = df['low'].rolling(window=10, center=True).min()
recent_high = df['pivot_high'].dropna().iloc[-3:].max() if not df['pivot_high'].dropna().empty else df['high'].max()
recent_low = df['pivot_low'].dropna().iloc[-3:].min() if not df['pivot_low'].dropna().empty else df['low'].min()

# MACD
df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
df['macd'] = df['ema12'] - df['ema26']
df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
df['macd_hist'] = df['macd'] - df['macd_signal']

# RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# 布林带
df['sma20'] = df['close'].rolling(window=20).mean()
df['std20'] = df['close'].rolling(window=20).std()
df['bb_upper'] = df['sma20'] + (df['std20'] * 2)
df['bb_lower'] = df['sma20'] - (df['std20'] * 2)

# 主界面 - 状态卡片
st.subheader("📊 实时状态")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="当前价格",
        value=f"${current_price:,.2f}",
        delta=f"{price_change:+.2f}%",
        delta_color="normal" if price_change >= 0 else "inverse"
    )

with col2:
    # 获取持仓信息
    position_value = "--"
    position_pnl = "--"
    
    if api_key and api_secret:
        try:
            weex = WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
            positions = weex.get_positions()
            if positions:
                # 查找当前币种的持仓
                current_pos = None
                for pos in positions:
                    if isinstance(pos, dict) and pos.get('symbol') == weex_symbol:
                        current_pos = pos
                        break
                
                if current_pos and isinstance(current_pos, dict):
                    # WEEX API 字段名: size, unrealizePnl
                    pos_size = float(current_pos.get('size', current_pos.get('positionAmt', current_pos.get('amount', 0))))
                    unrealized_pnl = float(current_pos.get('unrealizePnl', current_pos.get('unrealizedProfit', current_pos.get('pnl', 0))))
                    
                    position_value = f"{abs(pos_size):.4f} {current_symbol.replace('-USDT', '')}"
                    position_pnl = f"${unrealized_pnl:+.2f}"
                    pnl_color = "normal" if unrealized_pnl >= 0 else "inverse"
                else:
                    position_value = "无持仓"
                    position_pnl = "--"
            else:
                position_value = "无持仓"
                position_pnl = "--"
        except:
            position_value = "--"
            position_pnl = "--"
    
    st.metric(
        label="持仓",
        value=position_value,
        delta=position_pnl,
        delta_color="normal" if position_pnl != "--" and not position_pnl.startswith("-") else "inverse" if position_pnl.startswith("-") else "off"
    )

with col3:
    st.metric(
        label="24h涨跌",
        value=f"{price_change:+.2f}%",
        delta=f"${(current_price * price_change / 100):,.2f}",
        delta_color="normal" if price_change >= 0 else "inverse"
    )

with col4:
    auto_status = "🟢 运行中" if st.session_state.auto_trading_enabled else "⚪ 已停止"
    st.metric(
        label="自动交易",
        value=auto_status,
        delta=current_symbol,
        delta_color="off"
    )

# 账户信息面板（实盘模式）
if mode == "实盘交易" and api_key and api_secret:
    st.markdown("---")
    st.subheader("💰 账户信息")
    
    try:
        weex = WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
        account = weex.get_account()
        positions = weex.get_positions()
        
        if account:
            # 处理不同的数据结构
            balance = 0
            total_margin = 0
            unrealized_pnl = 0
            
            if isinstance(account, list):
                # 如果是列表，查找 USDT
                for asset in account:
                    if isinstance(asset, dict) and (asset.get('asset') == 'USDT' or asset.get('coin') == 'USDT'):
                        balance = float(asset.get('availableBalance', asset.get('balance', asset.get('free', 0))))
                        total_margin = float(asset.get('marginBalance', balance))
                        unrealized_pnl = float(asset.get('unrealizedProfit', 0))
                        break
            elif isinstance(account, dict):
                balance = float(account.get('balance', 0))
                total_margin = float(account.get('total_margin_balance', balance))
                unrealized_pnl = float(account.get('unrealized_pnl', 0))
            
            # 从持仓计算总未实现盈亏
            total_unrealized_pnl = 0
            if positions and isinstance(positions, list):
                for pos in positions:
                    if isinstance(pos, dict):
                        pnl = float(pos.get('unrealizePnl', pos.get('unrealizedProfit', pos.get('pnl', 0))))
                        total_unrealized_pnl += pnl
            
            # 计算总权益
            total_equity = balance + total_unrealized_pnl
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("可用余额", f"${balance:,.2f}")
            with col2:
                st.metric("保证金余额", f"${total_margin:,.2f}")
            with col3:
                color = "normal" if total_unrealized_pnl >= 0 else "inverse"
                st.metric("未实现盈亏", f"${total_unrealized_pnl:+.2f}", delta_color=color)
            with col4:
                st.metric("总权益", f"${total_equity:,.2f}")
            
            # 显示持仓详情
            if positions and len(positions) > 0:
                st.markdown("---")
                st.subheader("📊 持仓详情")
                
                positions_data = []
                for pos in positions:
                    if isinstance(pos, dict):
                        pos_size = float(pos.get('positionAmt', pos.get('amount', pos.get('size', 0))))
                        if pos_size != 0:
                            # WEEX API 字段名
                            side = pos.get('side', 'LONG')
                            avg_price = float(pos.get('avgPrice', pos.get('entryPrice', 0)))
                            pnl = float(pos.get('unrealizePnl', pos.get('unrealizedProfit', pos.get('pnl', 0))))
                            leverage = pos.get('leverage', 1)
                            
                            positions_data.append({
                                '币种': pos.get('symbol', '').replace('USDT', ''),
                                '方向': side,
                                '数量': abs(pos_size),
                                '开仓价': f"${avg_price:,.2f}",
                                '杠杆': f"{leverage}x",
                                '未实现盈亏': f"${pnl:+.2f}"
                            })
                
                if positions_data:
                    import pandas as pd
                    positions_df = pd.DataFrame(positions_data)
                    st.dataframe(positions_df, use_container_width=True)
                else:
                    st.info("当前无持仓")
            else:
                st.info("当前无持仓")
        else:
            st.warning("无法获取账户信息，请检查API配置")
    
    except Exception as e:
        st.error(f"获取账户信息失败: {e}")

# 回测结果显示
if mode == "策略回测" and st.session_state.get('run_backtest') and 'backtest_params' in st.session_state:
    st.markdown("---")
    st.subheader("📊 回测结果")
    
    with st.spinner("正在运行回测..."):
        # 运行回测
        backtest = Backtester(df, 
                             initial_capital=st.session_state.backtest_params['initial_capital'],
                             leverage=st.session_state.backtest_params['leverage'])
        
        results = backtest.run_backtest({
            'atr_multiplier_sl': st.session_state.backtest_params['atr_multiplier_sl'],
            'atr_multiplier_tp': st.session_state.backtest_params['atr_multiplier_tp'],
            'pivot_window': 10
        })
    
    # 显示统计结果
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总交易次数", results['total_trades'])
        st.metric("胜率", f"{results['win_rate']:.1f}%")
    with col2:
        st.metric("盈利次数", results['winning_trades'])
        st.metric("亏损次数", results['losing_trades'])
    with col3:
        return_color = "normal" if results['total_return'] >= 0 else "inverse"
        st.metric("总收益率", f"{results['total_return']:.2f}%", delta_color=return_color)
        st.metric("最大回撤", f"{results['max_drawdown']:.2f}%")
    with col4:
        st.metric("夏普比率", f"{results['sharpe_ratio']:.2f}")
        st.metric("盈亏比", f"{results['profit_factor']:.2f}")
    
    # 显示权益曲线
    if 'equity_curve' in results and not results['equity_curve'].empty:
        st.subheader("📈 权益曲线")
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=results['equity_curve']['time'],
            y=results['equity_curve']['equity'],
            mode='lines',
            name='权益曲线'
        ))
        fig_equity.update_layout(
            title="资金曲线",
            xaxis_title="时间",
            yaxis_title="资金 (USDT)",
            height=400
        )
        st.plotly_chart(fig_equity, use_container_width=True)
    
    # 显示交易记录
    if 'trades' in results and not results['trades'].empty:
        with st.expander("📋 查看交易明细"):
            st.dataframe(results['trades'], use_container_width=True)
    
    st.markdown("---")

# 图表和信号区域
col_chart, col_info = st.columns([3, 1])

with col_chart:
    st.subheader("📈 价格图表")
    
    # 创建图表
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.02, 
                       row_heights=[0.5, 0.2, 0.15, 0.15])
    
    # K线图
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线'
    ), row=1, col=1)
    
    # 支撑压力线
    fig.add_hline(y=recent_high, line_dash="dash", line_color="red", 
                  annotation_text=f"阻力: {recent_high:.2f}", row=1, col=1)
    fig.add_hline(y=recent_low, line_dash="dash", line_color="green",
                  annotation_text=f"支撑: {recent_low:.2f}", row=1, col=1)
    
    # 成交量
    fig.add_trace(go.Bar(
        x=df['timestamp'],
        y=df['volume'],
        name='成交量',
        marker_color='gray'
    ), row=2, col=1)
    
    # MACD
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd'], name='MACD', line=dict(color='blue')), row=3, col=1)
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['macd_signal'], name='Signal', line=dict(color='orange')), row=3, col=1)
    fig.add_trace(go.Bar(x=df['timestamp'], y=df['macd_hist'], name='Histogram', marker_color='gray'), row=3, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['rsi'], name='RSI', line=dict(color='purple')), row=4, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=4, col=1)
    
    fig.update_layout(
        title=f"{current_symbol} 价格走势 ({exchange} | {current_timeframe})",
        xaxis_title="时间",
        yaxis_title="价格 (USDT)",
        height=800,
        showlegend=False,
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col_info:
    st.subheader("📋 交易信号")
    
    # 杠杆选择（实盘交易）
    if mode == "实盘交易":
        st.subheader("⚙️ 交易设置")
        trade_leverage = st.selectbox(
            f"杠杆倍数 (最大{max_leverage}x)",
            available_leverages,
            index=default_leverage_index,
            key="trade_leverage"
        )
        trade_amount = st.number_input("交易数量", value=0.01, step=0.001, format="%.3f")
        st.markdown("---")
    
    # 计算ATR
    atr_value = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
    
    # 计算开单位置
    long_entry = recent_low + atr_value * 0.3 if recent_low < current_price else 0
    short_entry = recent_high - atr_value * 0.3 if recent_high > current_price else 0
    
    # 判断信号
    signal_type = None
    if current_price > recent_low and current_price < recent_high:
        if long_entry > 0 and current_price < long_entry * 1.02:
            signal_type = "LONG"
            signal_text = f'''
            **当前信号: 🟢 做多**
            
            入场价: ${long_entry:,.2f}
            止损: ${long_entry - atr_value * 1.5:,.2f}
            止盈: ${long_entry + atr_value * 2.0:,.2f}
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            '''
        elif short_entry > 0 and current_price > short_entry * 0.98:
            signal_type = "SHORT"
            signal_text = f'''
            **当前信号: 🔴 做空**
            
            入场价: ${short_entry:,.2f}
            止损: ${short_entry + atr_value * 1.5:,.2f}
            止盈: ${short_entry - atr_value * 2.0:,.2f}
            
            阻力: ${recent_high:,.2f}
            支撑: ${recent_low:,.2f}
            '''
        else:
            signal_type = "WAIT"
            signal_text = f'''
            **当前信号: 🟡 观望**
            
            价格处于支撑阻力之间
            等待明确信号...
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            '''
    else:
        signal_type = None
        signal_text = '''
        **当前信号: ⚪ 数据加载中...**
        
        请等待数据更新
        '''
    
    st.info(signal_text)
    
    # 技术指标
    st.markdown("---")
    st.subheader("📊 技术指标")
    
    latest_macd = df['macd'].iloc[-1]
    latest_signal = df['macd_signal'].iloc[-1]
    latest_rsi = df['rsi'].iloc[-1]
    
    macd_signal_text = "金叉" if latest_macd > latest_signal else "死叉" if latest_macd < latest_signal else "多头" if latest_macd > 0 else "空头"
    rsi_signal_text = "超买" if latest_rsi > 70 else "超卖" if latest_rsi < 30 else "中性"
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("MACD", f"{latest_macd:.2f}", macd_signal_text)
    with col2:
        st.metric("RSI", f"{latest_rsi:.1f}", rsi_signal_text)
    with col3:
        st.metric("布林带", "正常", f"上:{df['bb_upper'].iloc[-1]:.0f}")

# 自动交易逻辑（实盘）
if mode == "实盘交易" and api_key and api_secret:
    st.markdown("---")
    st.subheader("🤖 自动交易监控")
    
    # 初始化自动交易状态
    if 'auto_trade_state' not in st.session_state:
        st.session_state.auto_trade_state = {
            'enabled': False,
            'position': None,  # None, 'LONG', 'SHORT'
            'entry_price': 0,
            'entry_time': None,
            'sl_price': 0,
            'tp_price': 0,
            'highest_profit_pct': 0,
            'position_size': 0,
            'trade_history': []
        }
    
    auto_state = st.session_state.auto_trade_state
    
    # 自动交易开关 - 同步两个状态
    col1, col2 = st.columns([1, 3])
    with col1:
        auto_enabled = st.toggle("启用自动交易", value=st.session_state.auto_trading_enabled)
        auto_state['enabled'] = auto_enabled
        st.session_state.auto_trading_enabled = auto_enabled
    
    with col2:
        # 从API获取真实持仓状态
        try:
            weex = WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
            positions = weex.get_positions()
            current_pos = None
            if positions and isinstance(positions, list):
                for pos in positions:
                    if isinstance(pos, dict) and pos.get('symbol') == weex_symbol:
                        current_pos = pos
                        break
            
            if current_pos:
                # WEEX API 字段名: size, side, unrealizePnl
                pos_size = float(current_pos.get('size', current_pos.get('positionAmt', current_pos.get('amount', 0))))
                entry_price = float(current_pos.get('avgPrice', current_pos.get('entryPrice', 0)))
                
                # 获取未实现盈亏 (WEEX 用 unrealizePnl)
                unrealized_pnl = float(current_pos.get('unrealizePnl', 
                    current_pos.get('unrealizedPnl', 
                    current_pos.get('unrealizedProfit', 0))))
                
                # 获取持仓方向 (WEEX 用 side 字段)
                side = current_pos.get('side', 'LONG')
                
                # 计算盈亏百分比
                open_value = float(current_pos.get('openValue', abs(pos_size) * entry_price))
                if open_value > 0:
                    pnl_pct = (unrealized_pnl / open_value) * 100
                else:
                    pnl_pct = 0
                
                st.info(f"📊 当前持仓: {side} | 数量: {abs(pos_size):.4f} | 盈亏: ${unrealized_pnl:+.2f} ({pnl_pct:+.2f}%)")
                
                # 调试信息
                with st.expander("📋 持仓详情（调试）"):
                    st.json(current_pos)
                
                # 同步本地状态
                auto_state['position'] = side
                auto_state['entry_price'] = entry_price
            elif auto_state['position']:
                # API显示无持仓但本地有记录，可能已平仓
                st.warning(f"⚠️ 本地记录有持仓但API显示无持仓，可能已手动平仓")
                auto_state['position'] = None
            else:
                st.info("📊 当前无持仓")
        except Exception as e:
            # 如果API查询失败，使用本地状态
            if auto_state['position']:
                st.info(f"📊 当前持仓: {auto_state['position']} | 入场价: ${auto_state['entry_price']:,.2f} | 浮动盈亏: {auto_state.get('unrealized_pnl', 0):.2f}% (本地缓存)")
            else:
                st.info("📊 当前无持仓")
    
    if auto_enabled:
        # 获取账户信息
        try:
            weex = WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
            account = weex.get_account()
            # 处理不同的数据结构
            balance = 0
            if account:
                if isinstance(account, list):
                    # 如果是列表，查找 USDT
                    for asset in account:
                        if isinstance(asset, dict) and (asset.get('asset') == 'USDT' or asset.get('coin') == 'USDT'):
                            balance = float(asset.get('availableBalance', asset.get('balance', asset.get('free', 0))))
                            break
                elif isinstance(account, dict):
                    balance = float(account.get('balance', 0))
            
            # 仓位管理：只用10%资金
            position_size_pct = 0.1
            risk_amount = balance * position_size_pct
            
            st.write(f"💰 账户余额: {balance:.2f} USDT | 风险金额: {risk_amount:.2f} USDT (10%)")
            
            # 风险控制检查
            risk_manager = st.session_state.risk_manager
            # 计算实际仓位价值（用于风险检查）
            position_value = risk_amount * trade_leverage
            can_trade, risk_msg = risk_manager.check_trade_allowed(
                trade_size=position_value,
                total_capital=balance * trade_leverage  # 使用带杠杆的总资金
            )
            
            if not can_trade:
                st.error(f"🚫 风险控制阻止交易: {risk_msg}")
                st.info("请检查风险设置或等待明日重置")
            else:
                st.success(f"✅ 风险检查通过: {risk_msg}")
            
            # 检查当前持仓
            positions = weex.get_positions()
            current_position = None
            if positions and isinstance(positions, list):
                for pos in positions:
                    if isinstance(pos, dict) and pos.get('symbol') == weex_symbol:
                        current_position = pos
                        break
            
            # 如果有持仓，检查平仓条件
            if current_position and auto_state['position'] and isinstance(current_position, dict):
                pos_size = float(current_position.get('positionAmt', current_position.get('amount', current_position.get('size', 0))))
                entry_price = auto_state['entry_price']
                
                # 计算盈亏（避免除零）
                if entry_price and entry_price > 0:
                    if auto_state['position'] == 'LONG':
                        pnl_pct = (current_price - entry_price) / entry_price * trade_leverage
                    else:
                        pnl_pct = (entry_price - current_price) / entry_price * trade_leverage
                else:
                    pnl_pct = 0
                
                auto_state['unrealized_pnl'] = pnl_pct
                
                # 更新最高盈利
                if pnl_pct > auto_state['highest_profit_pct']:
                    auto_state['highest_profit_pct'] = pnl_pct
                
                # 检查平仓条件
                should_close = False
                close_reason = ""
                
                # 0. 爆仓保护（亏损超过 50% 立即平仓）
                if pnl_pct < -0.50:
                    should_close = True
                    close_reason = f"爆仓保护 (亏损 {pnl_pct:.1%})"
                
                # 1. 止损
                elif auto_state['position'] == 'LONG' and current_price <= auto_state['sl_price']:
                    should_close = True
                    close_reason = "止损"
                elif auto_state['position'] == 'SHORT' and current_price >= auto_state['sl_price']:
                    should_close = True
                    close_reason = "止损"
                
                # 2. 止盈
                elif auto_state['position'] == 'LONG' and current_price >= auto_state['tp_price']:
                    should_close = True
                    close_reason = "止盈"
                elif auto_state['position'] == 'SHORT' and current_price <= auto_state['tp_price']:
                    should_close = True
                    close_reason = "止盈"
                
                # 3. 移动止盈（盈利超过5%后，回撤0.5%）
                elif pnl_pct > 0 and auto_state['highest_profit_pct'] > 0.05:
                    drawdown = auto_state['highest_profit_pct'] - pnl_pct
                    if drawdown > 0.005:  # 回撤0.5%
                        should_close = True
                        close_reason = f"移动止盈 (最高盈利: {auto_state['highest_profit_pct']:.2f}%, 当前: {pnl_pct:.2f}%)"
                
                # 4. 信号反转
                elif (auto_state['position'] == 'LONG' and signal_type == 'SHORT') or \
                     (auto_state['position'] == 'SHORT' and signal_type == 'LONG'):
                    should_close = True
                    close_reason = "信号反转"
                
                if should_close:
                    st.warning(f"🚨 触发平仓: {close_reason}")
                    
                    # 执行平仓
                    # WEEX API: 平仓时使用 reduceOnly 参数
                    side = 'SELL' if auto_state['position'] == 'LONG' else 'BUY'
                    position_side = auto_state['position']  # LONG 或 SHORT
                    result = weex.place_order(
                        symbol=weex_symbol,
                        side=side,
                        position_side=position_side,
                        order_type='MARKET',
                        quantity=abs(pos_size),
                        reduce_only=True  # 标记为仅减仓（平仓）
                    )
                    
                    if result:
                        # 检查返回结果是否包含错误
                        if isinstance(result, dict) and (result.get('error') or result.get('success') == False):
                            st.error(f"❌ 平仓失败: {result.get('error') or result.get('message', '未知错误')}")
                        else:
                            # 记录交易
                            trade_record = {
                                'entry_time': auto_state['entry_time'],
                                'exit_time': datetime.now(),
                                'side': auto_state['position'],
                                'entry_price': entry_price,
                                'exit_price': current_price,
                                'pnl_pct': pnl_pct,
                                'exit_reason': close_reason
                            }
                            auto_state['trade_history'].append(trade_record)
                            
                            # 重置状态
                            auto_state['position'] = None
                            auto_state['entry_price'] = 0
                            auto_state['highest_profit_pct'] = 0
                            
                            # 显示订单详情
                            with st.expander("📋 平仓订单详情"):
                                st.json(result)
                            
                            st.success(f"✅ 平仓成功! 盈亏: {pnl_pct:.2f}%")
                            
                            # 发送邮件通知（只在成功时发送）
                            if email_notifier and enable_position_alert:
                                email_notifier.send_email(
                                    f"平仓通知 - {current_symbol}",
                                    f"{current_symbol} 平仓\n方向: {trade_record['side']}\n入场: {entry_price}\n出场: {current_price}\n盈亏: {pnl_pct:.2f}%\n原因: {close_reason}",
                                    f"<h2>平仓通知</h2><p>币种: {current_symbol}</p><p>方向: {trade_record['side']}</p><p>盈亏: {pnl_pct:.2f}%</p><p>原因: {close_reason}</p>"
                                )
            
            # 如果没有持仓，检查开仓信号
            elif not current_position and signal_type in ['LONG', 'SHORT'] and balance > 0:
                # 计算开仓数量（基于风险金额）
                # 仓位价值 = 风险金额 × 杠杆
                position_value = risk_amount * trade_leverage
                # 开仓数量 = 仓位价值 / 当前价格
                quantity = position_value / current_price
                
                # 根据币种精度调整数量
                if current_symbol in ['BTC-USDT']:
                    quantity = round(quantity, 3)
                elif current_symbol in ['ETH-USDT']:
                    quantity = round(quantity, 2)
                else:
                    quantity = round(quantity, 1)
                
                if quantity > 0:
                    st.info(f"🚀 触发开仓信号: {signal_type} | 数量: {quantity}")
                    
                    # 执行开仓
                    side = 'BUY' if signal_type == 'LONG' else 'SELL'
                    position_side = 'LONG' if signal_type == 'LONG' else 'SHORT'
                    result = weex.place_order(
                        symbol=weex_symbol,
                        side=side,
                        position_side=position_side,
                        order_type='MARKET',
                        quantity=quantity
                    )
                    
                    if result:
                        # 检查返回结果是否包含错误
                        if isinstance(result, dict) and result.get('error'):
                            st.error(f"❌ 开仓失败: {result.get('error')}")
                        elif isinstance(result, dict) and result.get('success') == False:
                            st.error(f"❌ 开仓失败: {result.get('message', '未知错误')}")
                        else:
                            # 设置止损止盈
                            if signal_type == 'LONG':
                                sl_price = long_entry - atr_value * 1.5
                                tp_price = long_entry + atr_value * 2.0
                            else:
                                sl_price = short_entry + atr_value * 1.5
                                tp_price = short_entry - atr_value * 2.0
                            
                            # 更新状态
                            auto_state['position'] = signal_type
                            auto_state['entry_price'] = current_price
                            auto_state['entry_time'] = datetime.now()
                            auto_state['sl_price'] = sl_price
                            auto_state['tp_price'] = tp_price
                            auto_state['highest_profit_pct'] = 0
                            auto_state['position_size'] = quantity
                            
                            st.success(f"✅ 开仓成功! {signal_type} | 数量: {quantity} | 止损: ${sl_price:.2f} | 止盈: ${tp_price:.2f}")
                            
                            # 显示订单详情
                            with st.expander("📋 订单详情"):
                                st.json(result)
                    else:
                        st.error("❌ 开仓失败: API 返回空结果")
                        
                        # 发送邮件通知
                        if email_notifier and enable_signal_alert:
                            email_notifier.send_email(
                                f"开仓通知 - {current_symbol}",
                                f"{current_symbol} 开仓\n方向: {signal_type}\n价格: {current_price}\n数量: {quantity}\n止损: {sl_price}\n止盈: {tp_price}",
                                f"<h2>开仓通知</h2><p>币种: {current_symbol}</p><p>方向: {signal_type}</p><p>价格: {current_price}</p><p>数量: {quantity}</p>"
                            )
            
            # 显示交易历史
            if auto_state['trade_history']:
                with st.expander("📋 自动交易历史"):
                    import pandas as pd
                    history_df = pd.DataFrame(auto_state['trade_history'])
                    st.dataframe(history_df, use_container_width=True)
                    
                    # 统计
                    total_trades = len(history_df)
                    winning_trades = len(history_df[history_df['pnl_pct'] > 0])
                    total_pnl = history_df['pnl_pct'].sum()
                    
                    col1, col2, col3 = st.columns(3)
                    col1.metric("总交易", total_trades)
                    col2.metric("胜率", f"{winning_trades/total_trades*100:.1f}%")
                    col3.metric("总盈亏", f"{total_pnl:.2f}%")
                    
                    # 数据导出
                    st.markdown("---")
                    st.subheader("📊 数据导出")
                    
                    # 导出为 CSV
                    csv = history_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 下载 CSV",
                        data=csv,
                        file_name=f'trading_history_{datetime.now().strftime("%Y%m%d")}.csv',
                        mime='text/csv'
                    )
                    
                    # 导出为 Excel
                    try:
                        import io
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            history_df.to_excel(writer, sheet_name='交易记录', index=False)
                            
                            # 添加统计摘要
                            summary_df = pd.DataFrame([{
                                '总交易次数': total_trades,
                                '盈利次数': winning_trades,
                                '亏损次数': total_trades - winning_trades,
                                '胜率': f"{winning_trades/total_trades*100:.1f}%",
                                '总盈亏': f"{total_pnl:.2f}%"
                            }])
                            summary_df.to_excel(writer, sheet_name='统计摘要', index=False)
                        
                        st.download_button(
                            label="📥 下载 Excel",
                            data=buffer.getvalue(),
                            file_name=f'trading_report_{datetime.now().strftime("%Y%m%d")}.xlsx',
                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        )
                    except ImportError:
                        st.info("安装 openpyxl 后可导出 Excel: pip install openpyxl")
        
        except Exception as e:
            st.error(f"自动交易错误: {e}")

# 页脚
st.markdown("---")
st.caption("🤖 交易机器人 v1.0 | 使用有风险，投资需谨慎")
