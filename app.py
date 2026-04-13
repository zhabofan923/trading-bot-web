import streamlit as st
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
        st.markdown("""
        **使用163邮箱发送：**
        1. 登录163邮箱网页版
        2. 点击 [设置] → [POP3/SMTP/IMAP]
        3. 开启 SMTP 服务
        4. 获取授权码（不是登录密码）
        """)
        
        email_provider = st.selectbox("邮箱服务商", ["163邮箱", "QQ邮箱", "其他"], index=0)
        email_sender = st.text_input("发件人邮箱", value="", help="如：yourname@163.com")
        email_auth_code = st.text_input("授权码", type="password", help="163邮箱授权码")
        email_receiver = st.text_input("收件人邮箱", value="", help="可以填同一个邮箱")
        
        enable_price_alert = st.checkbox("启用价格预警", value=True)
        enable_signal_alert = st.checkbox("启用信号预警", value=True)
        enable_position_alert = st.checkbox("启用持仓预警", value=True)
        
        if enable_position_alert:
            st.subheader("持仓预警阈值")
            profit_threshold = st.number_input("盈利提醒 (USDT)", value=100.0, step=10.0)
            loss_threshold = st.number_input("亏损提醒 (USDT)", value=-50.0, step=10.0)
    
    # 模式选择
    mode = st.radio("运行模式", ["实盘交易", "策略回测"], index=0)
    
    # 获取交易对列表和杠杆信息
    @st.cache_data(ttl=300)
    def get_symbols_info():
        try:
            weex = WeexAPI()
            return weex.get_all_symbols_with_leverage()
        except:
            return {}
    
    symbols_info = get_symbols_info()
    
    # 获取交易对列表（优先自选）
    def get_available_symbols(api_key, api_secret, passphrase):
        try:
            # 先尝试获取用户的自选列表
            if api_key and api_secret:
                weex_auth = WeexAPI(api_key=api_key, api_secret=api_secret, passphrase=passphrase)
                favorite_symbols = weex_auth.get_favorite_symbols()
                if favorite_symbols and isinstance(favorite_symbols, list) and len(favorite_symbols) > 0:
                    # 转换为标准格式
                    formatted = [s.replace('USDT', '-USDT') for s in favorite_symbols if 'USDT' in s]
                    if formatted:
                        st.caption(f"📋 显示: 自选交易对 ({len(formatted)}个)")
                        return formatted
            
            # 如果没有自选，获取常用交易对（不是全部）
            common_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT", "XRP-USDT", "DOGE-USDT", "LTC-USDT"]
            st.caption(f"📋 显示: 常用交易对")
            return common_symbols
        except Exception as e:
            st.caption(f"📋 显示: 默认交易对")
            return ["BTC-USDT", "ETH-USDT", "SOL-USDT", "BCH-USDT"]
    
    available_symbols = get_available_symbols(api_key, api_secret, passphrase)
    
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
    auto_status = "🟢 运行中" if st.session_state.auto_trading_enabled else "⚪ 已停止"
    st.metric(
        label="自动交易",
        value=auto_status,
        delta=current_symbol,
        delta_color="off"
    )

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
            signal_text = f"""
            **当前信号: 🟢 做多**
            
            入场价: ${long_entry:,.2f}
            止损: ${long_entry - atr_value * 1.5:,.2f}
            止盈: ${long_entry + atr_value * 2.0:,.2f}
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            """
        elif short_entry > 0 and current_price > short_entry * 0.98:
            signal_type = "SHORT"
            signal_text = f"""
            **当前信号: 🔴 做空**
            
            入场价: ${short_entry:,.2f}
            止损: ${short_entry + atr_value * 1.5:,.2f}
            止盈: ${short_entry - atr_value * 2.0:,.2f}
            
            阻力: ${recent_high:,.2f}
            支撑: ${recent_low:,.2f}
            """
        else:
            signal_type = "WAIT"
            signal_text = f"""
            **当前信号: 🟡 观望**
            
            价格处于支撑阻力之间
            等待明确信号...
            
            支撑: ${recent_low:,.2f}
            阻力: ${recent_high:,.2f}
            """
    else:
        signal_type = None
        signal_text = """
        **当前信号: ⚪ 数据加载中...**
        
        请等待数据更新
        """
    
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

# 页脚
st.markdown("---")
st.caption("🤖 交易机器人 v1.0 | 使用有风险，投资需谨慎")
