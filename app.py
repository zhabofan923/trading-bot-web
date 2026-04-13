import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from weex_api import WeexAPI
from email_notifier import EmailNotifier

# 页面配置
st.set_page_config(
    page_title="交易机器人控制台",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自动刷新配置
import time

# 使用 session state 记录上次刷新时间
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

# 检查是否需要刷新（每5秒）
current_time = time.time()
if current_time - st.session_state.last_refresh > 5:
    st.session_state.last_refresh = current_time
    st.rerun()

# 标题
st.title("🤖 交易机器人控制台")

# 显示刷新倒计时
elapsed = current_time - st.session_state.last_refresh
remaining = max(0, 5 - elapsed)
st.caption(f"⏱️ 下次刷新: {remaining:.0f}秒 | 最后更新: {datetime.now().strftime('%H:%M:%S')}")

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
        st.markdown("""
        **使用163邮箱发送：**
        1. 登录163邮箱网页版
        2. 点击 [设置] → [POP3/SMTP/IMAP]
        3. 开启 SMTP 服务
        4. 获取授权码（不是登录密码）
        """)
        
        # 选择邮箱服务商
        email_provider = st.selectbox("邮箱服务商", ["163邮箱", "QQ邮箱", "其他"], index=0)
        
        email_sender = st.text_input("发件人邮箱", value="", help="如：yourname@163.com")
        email_auth_code = st.text_input("授权码", type="password", help="163邮箱授权码")
        email_receiver = st.text_input("收件人邮箱", value="", help="可以填同一个邮箱")
        
        enable_price_alert = st.checkbox("启用价格预警", value=True)
        enable_signal_alert = st.checkbox("启用信号预警", value=True)
        enable_position_alert = st.checkbox("启用持仓预警", value=True)
        
        # 预警阈值设置
        if enable_position_alert:
            st.subheader("持仓预警阈值")
            profit_threshold = st.number_input("盈利提醒 (USDT)", value=100.0, step=10.0)
            loss_threshold = st.number_input("亏损提醒 (USDT)", value=-50.0, step=10.0)
        
        # 测试邮件按钮
        if email_sender and email_auth_code and email_receiver:
            if st.button("📤 发送测试邮件"):
                # 使用相同的SMTP配置
                if email_provider == "163邮箱":
                    test_smtp_server = "smtp.163.com"
                    test_smtp_port = 25
                elif email_provider == "QQ邮箱":
                    test_smtp_server = "smtp.qq.com"
                    test_smtp_port = 587
                else:
                    test_smtp_server = "smtp.163.com"
                    test_smtp_port = 25
                
                test_notifier = EmailNotifier(
                    smtp_server=test_smtp_server,
                    smtp_port=test_smtp_port,
                    sender_email=email_sender,
                    sender_password=email_auth_code,
                    receiver_email=email_receiver
                )
                with st.spinner("发送中..."):
                    if test_notifier.send_email(
                        "交易机器人测试邮件",
                        "这是一封测试邮件，如果收到说明配置成功！",
                        "<h2>✅ 交易机器人邮件配置成功</h2><p>您的邮件通知功能已正常工作。</p>"
                    ):
                        st.success("✅ 测试邮件发送成功！请查收")
                    else:
                        st.error("❌ 发送失败，请检查邮箱和授权码")
    
    # 交易对 - WEEX 合约格式
    symbol = st.selectbox(
        "交易对",
        ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT"],
        index=0
    )
    
    # 时间周期 - WEEX 支持：1m, 5m, 15m, 30m, 1h, 4h, 12h, 1d, 1w
    timeframe = st.selectbox(
        "时间周期",
        ["1m", "5m", "15m", "30m", "1h", "4h", "12h", "1d"],
        index=4
    )
    
    # 策略参数
    st.subheader("策略参数")
    pivot_length = st.slider("枢轴点长度", 5, 50, 10)
    atr_length = st.slider("ATR周期", 5, 30, 14)
    sl_multiplier = st.slider("止损倍数(ATR)", 0.5, 3.0, 1.5, 0.1)
    tp_multiplier = st.slider("止盈倍数(ATR)", 0.5, 5.0, 2.0, 0.1)
    
    # 操作按钮
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        start_btn = st.button("🚀 启动机器人", type="primary", use_container_width=True)
    with col2:
        stop_btn = st.button("⏹️ 停止机器人", type="secondary", use_container_width=True)

# 获取数据函数
@st.cache_data(ttl=60)
def fetch_ohlcv(exchange_name, symbol, timeframe, limit=100):
    try:
        if exchange_name.lower() == 'weex':
            weex = WeexAPI()
            # WEEX 合约使用 BTCUSDT 格式
            weex_symbol = symbol.replace('-', '')
            return weex.get_ohlcv(weex_symbol, timeframe, limit)
        else:
            # 其他交易所使用 ccxt
            import ccxt
            exchange_class = getattr(ccxt, exchange_name.lower())
            exchange = exchange_class({'enableRateLimit': True})
            ohlcv = exchange.fetch_ohlcv(symbol.replace('-', '/'), timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
    except Exception as e:
        st.error(f"获取数据失败: {e}")
        return None

# 初始化 WEEX API（带认证）
@st.cache_resource
def get_weex_api(api_key, api_secret, passphrase):
    """获取带认证的 WEEX API 实例"""
    if api_key and api_secret:
        return WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
    return None

# 获取数据
with st.spinner("正在获取数据..."):
    df = fetch_ohlcv(exchange, symbol, timeframe)

# 如果获取失败，使用模拟数据
if df is None or df.empty:
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
    st.warning("无法获取交易所数据，使用模拟数据")

# 计算指标
current_price = df['close'].iloc[-1]
price_change = ((df['close'].iloc[-1] - df['close'].iloc[-24]) / df['close'].iloc[-24] * 100) if len(df) >= 24 else 0

# 初始化邮件通知器
if email_sender and email_auth_code and email_receiver:
    # 根据邮箱服务商选择SMTP服务器
    if email_provider == "163邮箱":
        smtp_server = "smtp.163.com"
        smtp_port = 25  # 163邮箱使用25端口或465(SSL)
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
else:
    email_notifier = None

# 初始化预警状态
if 'alert_sent' not in st.session_state:
    st.session_state.alert_sent = {
        'price_support': False,
        'price_resistance': False,
        'signal': None,
        'position_pnl': {}
    }

# 计算支撑压力
df['pivot_high'] = df['high'].rolling(window=10, center=True).max()
df['pivot_low'] = df['low'].rolling(window=10, center=True).min()
recent_high = df['pivot_high'].dropna().iloc[-3:].max() if not df['pivot_high'].dropna().empty else df['high'].max()
recent_low = df['pivot_low'].dropna().iloc[-3:].min() if not df['pivot_low'].dropna().empty else df['low'].min()

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
    st.metric(
        label="持仓",
        value="--",
        delta="--",
        delta_color="off"
    )

with col3:
    st.metric(
        label="24h涨跌",
        value=f"{price_change:+.2f}%",
        delta=f"${(current_price * price_change / 100):,.2f}",
        delta_color="normal" if price_change >= 0 else "inverse"
    )

with col4:
    st.metric(
        label="数据源",
        value=f"🟢 {exchange}",
        delta=symbol,
        delta_color="off"
    )

st.markdown("---")

# 图表区域
col_chart, col_info = st.columns([3, 1])

with col_chart:
    st.subheader("📈 价格图表")
    
    # 创建图表
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                       vertical_spacing=0.03, row_heights=[0.7, 0.3])
    
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
        y=df['volume'] if 'volume' in df.columns else np.random.uniform(100, 1000, len(df)),
        name='成交量',
        marker_color='gray'
    ), row=2, col=1)
    
    fig.update_layout(
        title=f"{symbol} 价格走势 ({exchange} | {timeframe})",
        xaxis_title="时间",
        yaxis_title="价格 (USDT)",
        height=600,
        showlegend=False,
        xaxis_rangeslider_visible=False
    )
    
    st.plotly_chart(fig, use_container_width=True)

with col_info:
    st.subheader("📋 交易信号")
    
    # 计算ATR
    atr_value = (df['high'] - df['low']).rolling(window=14).mean().iloc[-1]
    
    # 计算开单位置
    long_entry = recent_low + atr_value * 0.3 if recent_low < current_price else 0
    short_entry = recent_high - atr_value * 0.3 if recent_high > current_price else 0
    
    # 价格预警检查
    if email_notifier and enable_price_alert:
        # 支撑线预警（价格接近支撑）
        if current_price <= recent_low * 1.005 and not st.session_state.alert_sent['price_support']:
            email_notifier.send_price_alert(symbol, current_price, recent_low, "接近支撑位")
            st.session_state.alert_sent['price_support'] = True
        elif current_price > recent_low * 1.01:
            st.session_state.alert_sent['price_support'] = False
        
        # 阻力线预警（价格接近阻力）
        if current_price >= recent_high * 0.995 and not st.session_state.alert_sent['price_resistance']:
            email_notifier.send_price_alert(symbol, current_price, recent_high, "接近阻力位")
            st.session_state.alert_sent['price_resistance'] = True
        elif current_price < recent_high * 0.99:
            st.session_state.alert_sent['price_resistance'] = False
    
    # 判断信号
    signal_type = None
    if current_price > recent_low and current_price < recent_high:
        if long_entry > 0 and current_price < long_entry * 1.02:
            signal_type = "LONG"
            signal_text = f"""
            **当前信号: 🟢 做多**
            
            入场价: ${long_entry:,.2f}
            止损: ${long_entry - atr_value * 1.5:,.2f}
            止盈1: ${long_entry + atr_value * 1.0:,.2f}
            止盈2: ${long_entry + atr_value * 2.0:,.2f}
            止盈3: ${long_entry + atr_value * 3.0:,.2f}
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            """
            
            # 信号预警
            if email_notifier and enable_signal_alert and st.session_state.alert_sent.get('signal') != 'LONG':
                email_notifier.send_signal_alert(
                    symbol, 'LONG', long_entry, 
                    long_entry - atr_value * 1.5,
                    long_entry + atr_value * 2.0
                )
                st.session_state.alert_sent['signal'] = 'LONG'
                
        elif short_entry > 0 and current_price > short_entry * 0.98:
            signal_type = "SHORT"
            signal_text = f"""
            **当前信号: 🔴 做空**
            
            入场价: ${short_entry:,.2f}
            止损: ${short_entry + atr_value * 1.5:,.2f}
            止盈1: ${short_entry - atr_value * 1.0:,.2f}
            止盈2: ${short_entry - atr_value * 2.0:,.2f}
            止盈3: ${short_entry - atr_value * 3.0:,.2f}
            
            阻力: ${recent_high:,.2f}
            支撑: ${recent_low:,.2f}
            """
            
            # 信号预警
            if email_notifier and enable_signal_alert and st.session_state.alert_sent.get('signal') != 'SHORT':
                email_notifier.send_signal_alert(
                    symbol, 'SHORT', short_entry,
                    short_entry + atr_value * 1.5,
                    short_entry - atr_value * 2.0
                )
                st.session_state.alert_sent['signal'] = 'SHORT'
        else:
            signal_type = "WAIT"
            signal_text = f"""
            **当前信号: 🟡 观望**
            
            价格处于支撑阻力之间
            等待明确信号...
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            """
            # 清除信号状态
            st.session_state.alert_sent['signal'] = None
    else:
        signal_type = None
        signal_text = """
        **当前信号: ⚪ 数据加载中...**
        
        请等待数据更新
        """
    
    st.info(signal_text)
    
    # 实盘交易区域
    st.markdown("---")
    st.subheader("🚀 实盘交易")
    
    # 交易参数
    trade_col1, trade_col2 = st.columns(2)
    with trade_col1:
        trade_amount = st.number_input("数量 (BTC)", min_value=0.001, max_value=10.0, value=0.01, step=0.001)
    with trade_col2:
        leverage = st.selectbox("杠杆", [1, 5, 10, 20, 50, 100], index=2)
    
    # 初始化带认证的 WEEX API
    weex_trading = get_weex_api(api_key, api_secret, passphrase)
    
    # 下单按钮
    if signal_type == "LONG":
        if st.button("🟢 开多", type="primary", use_container_width=True):
            if weex_trading:
                with st.spinner("正在下单..."):
                    result = weex_trading.place_order(
                        symbol=symbol.replace('-', ''),
                        side='BUY',
                        position_side='LONG',
                        order_type='MARKET',
                        quantity=trade_amount,
                        tp_trigger_price=long_entry + atr_value * 2.0 if long_entry > 0 else None,
                        sl_trigger_price=long_entry - atr_value * 1.5 if long_entry > 0 else None
                    )
                    if result.get('success'):
                        st.success(f"✅ 下单成功! 订单ID: {result.get('orderId')}")
                        # 记录交易
                        st.session_state.trade_history.append({
                            '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            '交易对': symbol,
                            '方向': 'LONG',
                            '类型': '开多',
                            '数量': trade_amount,
                            '价格': current_price,
                            '杠杆': leverage,
                            '订单ID': result.get('orderId', ''),
                            'pnl': 0
                        })
                    else:
                        st.error(f"❌ 下单失败: {result.get('error')}")
            else:
                st.warning("⚠️ 请先配置 API Key")
    elif signal_type == "SHORT":
        if st.button("🔴 开空", type="primary", use_container_width=True):
            if weex_trading:
                with st.spinner("正在下单..."):
                    result = weex_trading.place_order(
                        symbol=symbol.replace('-', ''),
                        side='SELL',
                        position_side='SHORT',
                        order_type='MARKET',
                        quantity=trade_amount,
                        tp_trigger_price=short_entry - atr_value * 2.0 if short_entry > 0 else None,
                        sl_trigger_price=short_entry + atr_value * 1.5 if short_entry > 0 else None
                    )
                    if result.get('success'):
                        st.success(f"✅ 下单成功! 订单ID: {result.get('orderId')}")
                        # 记录交易
                        st.session_state.trade_history.append({
                            '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            '交易对': symbol,
                            '方向': 'SHORT',
                            '类型': '开空',
                            '数量': trade_amount,
                            '价格': current_price,
                            '杠杆': leverage,
                            '订单ID': result.get('orderId', ''),
                            'pnl': 0
                        })
                    else:
                        st.error(f"❌ 下单失败: {result.get('error')}")
            else:
                st.warning("⚠️ 请先配置 API Key")
    else:
        st.button("⏸️ 等待信号", disabled=True, use_container_width=True)
    
    st.markdown("---")
    
    # 账户信息
    st.subheader("💰 账户信息")
    if weex_trading:
        # 自动刷新账户信息
        if 'account_data' not in st.session_state:
            st.session_state.account_data = None
            st.session_state.positions_data = None
        
        # 每5秒刷新一次
        if st.button("🔄 刷新账户", key="refresh_account") or st.session_state.account_data is None:
            with st.spinner("获取账户信息..."):
                st.session_state.account_data = weex_trading.get_balance()
                st.session_state.positions_data = weex_trading.get_positions()
        
        # 显示资金
        if st.session_state.account_data and isinstance(st.session_state.account_data, list):
            total_balance = 0
            for asset_info in st.session_state.account_data:
                asset = asset_info.get('asset', '')
                available = float(asset_info.get('availableBalance', 0))
                total = float(asset_info.get('balance', 0))
                frozen = float(asset_info.get('frozen', 0))
                unrealized = float(asset_info.get('unrealizePnl', 0))
                total_balance += total
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(f"{asset} 总资产", f"{total:,.2f}")
                with col2:
                    st.metric(f"{asset} 可用", f"{available:,.2f}")
                with col3:
                    color = "normal" if unrealized >= 0 else "inverse"
                    st.metric(f"{asset} 未实现盈亏", f"{unrealized:+.2f}", delta_color=color)
        
        # 显示持仓
        st.markdown("---")
        st.subheader("📊 当前持仓")
        
        if st.session_state.positions_data and isinstance(st.session_state.positions_data, list) and len(st.session_state.positions_data) > 0:
            for pos in st.session_state.positions_data:
                pos_symbol = pos.get('symbol', '')
                side = pos.get('side', '')
                size = float(pos.get('size', 0))
                leverage = pos.get('leverage', '1')
                unrealized_pnl = float(pos.get('unrealizePnl', 0))
                liquidate_price = pos.get('liquidatePrice', '0')
                
                # 计算收益率
                open_value = float(pos.get('openValue', 1))
                pnl_percent = (unrealized_pnl / open_value * 100) if open_value > 0 else 0
                
                # 持仓盈亏预警检查
                if email_notifier and enable_position_alert:
                    pos_key = f"{pos_symbol}_{side}"
                    last_alert = st.session_state.alert_sent['position_pnl'].get(pos_key, 0)
                    
                    # 大额盈利预警
                    if unrealized_pnl >= profit_threshold and last_alert < profit_threshold:
                        email_notifier.send_position_alert(pos_symbol, side, size, unrealized_pnl, pnl_percent)
                        st.session_state.alert_sent['position_pnl'][pos_key] = unrealized_pnl
                    
                    # 大额亏损预警
                    elif unrealized_pnl <= loss_threshold and last_alert > loss_threshold:
                        email_notifier.send_position_alert(pos_symbol, side, size, unrealized_pnl, pnl_percent)
                        st.session_state.alert_sent['position_pnl'][pos_key] = unrealized_pnl
                
                # 持仓卡片
                with st.container():
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        side_emoji = "🟢" if side == "LONG" else "🔴"
                        st.write(f"**{side_emoji} {pos_symbol} {side}**")
                        st.write(f"数量: {size} | 杠杆: {leverage}x")
                    with col2:
                        color = "normal" if unrealized_pnl >= 0 else "inverse"
                        st.metric("盈亏", f"{unrealized_pnl:+.2f} USDT", f"{pnl_percent:+.2f}%", delta_color=color)
                    with col3:
                        if st.button("平仓", key=f"close_{pos_symbol}_{side}"):
                            with st.spinner("正在平仓..."):
                                result = weex_trading.place_order(
                                    symbol=pos_symbol,
                                    side='SELL' if side == 'LONG' else 'BUY',
                                    position_side=side,
                                    order_type='MARKET',
                                    quantity=size
                                )
                                if result.get('success'):
                                    st.success(f"✅ 平仓成功! 订单ID: {result.get('orderId')}")
                                    # 记录平仓到交易历史
                                    st.session_state.trade_history.append({
                                        '时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        '交易对': pos_symbol,
                                        '方向': side,
                                        '类型': '平仓',
                                        '数量': size,
                                        '价格': current_price,
                                        '杠杆': leverage,
                                        '订单ID': result.get('orderId', ''),
                                        'pnl': unrealized_pnl
                                    })
                                    st.session_state.positions_data = None  # 刷新持仓
                                else:
                                    st.error(f"❌ 平仓失败: {result.get('error')}")
                    
                    if liquidate_price != '0':
                        st.caption(f"预估强平价: {liquidate_price}")
                    st.markdown("---")
        else:
            st.info("暂无持仓")
    
    st.markdown("---")
    
    # 交易记录
    st.subheader("📝 交易记录")
    
    # 初始化交易记录
    if 'trade_history' not in st.session_state:
        st.session_state.trade_history = []
    
    # 显示交易记录表格
    if len(st.session_state.trade_history) > 0:
        import pandas as pd
        history_df = pd.DataFrame(st.session_state.trade_history)
        st.dataframe(history_df, use_container_width=True)
        
        # 统计信息
        total_trades = len(st.session_state.trade_history)
        winning_trades = len([t for t in st.session_state.trade_history if t.get('pnl', 0) > 0])
        losing_trades = len([t for t in st.session_state.trade_history if t.get('pnl', 0) < 0])
        total_pnl = sum([t.get('pnl', 0) for t in st.session_state.trade_history])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("总交易次数", total_trades)
        with col2:
            st.metric("盈利次数", winning_trades)
        with col3:
            st.metric("亏损次数", losing_trades)
        with col4:
            color = "normal" if total_pnl >= 0 else "inverse"
            st.metric("总盈亏", f"{total_pnl:+.2f} USDT", delta_color=color)
        
        # 清空记录按钮
        if st.button("🗑️ 清空记录"):
            st.session_state.trade_history = []
            st.rerun()
    else:
        st.info("暂无交易记录")
    
    st.markdown("---")
    
    # 多周期趋势
    st.subheader("📊 多周期趋势")
    
    trends = {
        "15分钟": "🟢 多头",
        "1小时": "🟢 多头",
        "4小时": "🟡 震荡",
        "日线": "🟢 多头"
    }
    
    for tf, trend in trends.items():
        st.write(f"**{tf}:** {trend}")

# 页脚
st.markdown("---")
st.caption("🤖 交易机器人 v1.0 | 使用有风险，投资需谨慎")
