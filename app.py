
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date

st.set_page_config(
    page_title="Triad Investment Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1100px;}
h1 {font-size: 2rem !important;}
h2 {font-size: 1.35rem !important;}
div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22); padding: .6rem; border-radius: 12px;}
.small {font-size: .88rem; opacity: .78;}
.card {padding: 1rem; border: 1px solid rgba(128,128,128,.2); border-radius: 14px; margin-bottom: .8rem;}
</style>
""", unsafe_allow_html=True)

st.title("📈 Triad Investment Engine")
st.caption("Buffett + Chris Hohn + Druckenmiller — educational decision support, not personalised financial advice.")

with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Twelve Data API key", type="password",
                            help="Free Basic plan: currently 800 API credits/day. Your key is used only for this session.")
    st.markdown("Get a free key from Twelve Data. No payment is required for the Basic plan.")
    st.divider()
    st.caption("Data is fetched from Twelve Data. Availability of fundamentals depends on the symbol/plan.")

col1, col2, col3 = st.columns(3)
with col1:
    capital = st.number_input("💰 Investment amount", min_value=100.0, value=10000.0, step=500.0)
with col2:
    horizon = st.selectbox("🗓️ Horizon", ["1 year", "3 years", "5 years", "10+ years"], index=2)
with col3:
    risk = st.selectbox("⚖️ Risk", ["Low", "Medium", "High"], index=1)

symbol = st.text_input("🔎 Stock / ETF symbol", value="AAPL").upper().strip()
explain = st.selectbox("🧠 Explanation", ["Beginner", "Financial"], index=0)

def td(endpoint, params):
    if not api_key:
        return {"status": "error", "message": "Enter your Twelve Data API key in Settings."}
    params = dict(params)
    params["apikey"] = api_key
    try:
        r = requests.get(f"https://api.twelvedata.com/{endpoint}", params=params, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(ttl=900, show_spinner=False)
def cached_series(symbol, interval, outputsize, api_key_value):
    p = {"symbol": symbol, "interval": interval, "outputsize": outputsize}
    p["apikey"] = api_key_value
    try:
        r = requests.get("https://api.twelvedata.com/time_series", params=p, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(ttl=900, show_spinner=False)
def cached_quote(symbol, api_key_value):
    try:
        r = requests.get("https://api.twelvedata.com/quote",
                         params={"symbol": symbol, "apikey": api_key_value}, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

@st.cache_data(ttl=3600, show_spinner=False)
def cached_profile(symbol, api_key_value):
    try:
        r = requests.get("https://api.twelvedata.com/profile",
                         params={"symbol": symbol, "apikey": api_key_value}, timeout=15)
        return r.json()
    except Exception as e:
        return {"status": "error", "message": str(e)}

def parse_series(data):
    values = data.get("values", []) if isinstance(data, dict) else []
    if not values:
        return pd.DataFrame()
    df = pd.DataFrame(values)
    if "datetime" in df:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.sort_values("datetime")
    for c in ["open","high","low","close","volume"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"])

def pct_change(df, days):
    if len(df) <= days:
        return np.nan
    return (df["close"].iloc[-1] / df["close"].iloc[-days-1] - 1) * 100

def score_quality(profile):
    # Fundamentals are intentionally treated as optional. If unavailable, quality stays neutral.
    vals = []
    def num(k):
        v = profile.get(k)
        try: return float(v)
        except: return np.nan
    # These fields vary by provider/symbol. Only use fields that are actually returned.
    roe = num("return_on_equity")
    margin = num("profit_margin")
    if np.isfinite(roe):
        vals.append(np.clip(roe / 25 * 100, 0, 100))
    if np.isfinite(margin):
        vals.append(np.clip(margin / 20 * 100, 0, 100))
    return float(np.mean(vals)) if vals else 50.0

def score_buffett(profile, momentum_1y):
    q = score_quality(profile)
    m = 50 if not np.isfinite(momentum_1y) else np.clip(50 + momentum_1y*0.7, 0, 100)
    return round(0.7*q + 0.3*m, 1)

def score_hohn(profile, momentum_1y):
    q = score_quality(profile)
    m = 50 if not np.isfinite(momentum_1y) else np.clip(50 + momentum_1y*0.6, 0, 100)
    return round(0.65*q + 0.35*m, 1)

def score_druckenmiller(momentum_3m, momentum_1y, vol):
    mom3 = 50 if not np.isfinite(momentum_3m) else np.clip(50 + momentum_3m*1.0, 0, 100)
    mom1 = 50 if not np.isfinite(momentum_1y) else np.clip(50 + momentum_1y*0.5, 0, 100)
    v = 50 if not np.isfinite(vol) else np.clip(100 - vol*3, 0, 100)
    return round(0.45*mom3 + 0.35*mom1 + 0.20*v, 1)

def risk_alloc(risk):
    if risk == "Low":
        return {"Buffett / quality": 40, "Hohn / concentrated quality": 25,
                "Druckenmiller / trend": 10, "Diversification / cash": 25}
    if risk == "High":
        return {"Buffett / quality": 25, "Hohn / concentrated quality": 35,
                "Druckenmiller / trend": 30, "Diversification / cash": 10}
    return {"Buffett / quality": 35, "Hohn / concentrated quality": 30,
            "Druckenmiller / trend": 20, "Diversification / cash": 15}

if not api_key:
    st.info("👈 Enter your free Twelve Data API key in Settings, then analyse a symbol.")
    st.markdown("""
    ### How the engine thinks
    **1. Buffett:** Is this a good business at a sensible price?

    **2. Hohn:** Is there durable cash generation and a reason for management/capital allocation to improve value?

    **3. Druckenmiller:** Is the market trend/momentum supportive, and is risk under control?

    The app combines these lenses. It does **not** claim to reproduce the investors' private methods or portfolios.
    """)
    st.stop()

with st.spinner(f"Analysing {symbol}..."):
    quote = cached_quote(symbol, api_key)
    series_data = cached_series(symbol, "1day", 500, api_key)
    profile = cached_profile(symbol, api_key)

if quote.get("status") == "error" or "close" not in quote:
    st.error(f"Could not retrieve {symbol}. {quote.get('message', 'Check the symbol and API key.')}")
    st.stop()

df = parse_series(series_data)
if df.empty:
    st.warning("Price history was not returned. The current quote may still be available, but the scoring will be limited.")

price = float(quote.get("close", df["close"].iloc[-1] if not df.empty else np.nan))
mom3 = pct_change(df, 63)
mom1 = pct_change(df, 252)
returns = df["close"].pct_change().dropna() if not df.empty else pd.Series(dtype=float)
vol = float(returns.std() * np.sqrt(252) * 100) if len(returns) > 30 else np.nan

b = score_buffett(profile, mom1)
h = score_hohn(profile, mom1)
d = score_druckenmiller(mom3, mom1, vol)
combined = round(0.38*b + 0.34*h + 0.28*d, 1)

# Educational interpretation, deliberately not framed as a buy/sell recommendation.
if combined >= 70:
    regime = "Strong alignment"
elif combined >= 55:
    regime = "Mixed-to-positive"
elif combined >= 40:
    regime = "Mixed / needs checking"
else:
    regime = "Weak alignment"

st.subheader(f"{symbol} — Triad analysis")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Price", f"{price:,.2f}")
m2.metric("Combined score", f"{combined}/100")
m3.metric("1Y momentum", "n/a" if not np.isfinite(mom1) else f"{mom1:+.1f}%")
m4.metric("Risk regime", regime)

st.caption("Score = an educational model using available data, not a forecast and not a personal recommendation.")

tabs = st.tabs(["🧭 Decision", "📊 Data", "📈 History", "🎓 Learn"])

with tabs[0]:
    c1, c2, c3 = st.columns(3)
    c1.metric("Buffett lens", f"{b}/100")
    c2.metric("Hohn lens", f"{h}/100")
    c3.metric("Druckenmiller lens", f"{d}/100")

    if explain == "Beginner":
        st.markdown("### What does this mean?")
        st.write(
            f"**Buffett:** focuses mainly on business quality and long-term economics. "
            f"This model gives it **{b}/100** based on the data available."
        )
        st.write(
            f"**Hohn:** looks for strong cash generation, durable advantages and disciplined capital allocation. "
            f"This model gives it **{h}/100**."
        )
        st.write(
            f"**Druckenmiller:** puts more weight on trend, momentum and risk. "
            f"Recent 3-month momentum is {'not available' if not np.isfinite(mom3) else f'{mom3:+.1f}%'} "
            f"and the model gives **{d}/100**."
        )
    else:
        st.markdown("### Model interpretation")
        st.write("The combined score is a weighted composite: 38% Buffett, 34% Hohn, 28% Druckenmiller.")
        st.write("Momentum is used as a proxy for trend; it is not the same as a full macro/liquidity regime model.")

    st.markdown("### Example risk framework")
    alloc = risk_alloc(risk)
    st.dataframe(pd.DataFrame({"Lens": list(alloc.keys()), "Illustrative weight %": list(alloc.values())}),
                 hide_index=True, use_container_width=True)

    st.markdown("### Why you should still check it")
    checks = [
        "Valuation: a great company can still be expensive.",
        "Debt and cash flow: verify the latest filings rather than relying only on ratios.",
        "Concentration: Hohn-style investing can create large single-name exposure.",
        "Macro regime: the current model only approximates this with price momentum.",
        "Data coverage: free API plans can omit or limit some fundamentals."
    ]
    for x in checks:
        st.write("• " + x)

with tabs[1]:
    st.markdown("### Quote")
    qshow = {k: quote.get(k) for k in ["symbol","name","exchange","currency","datetime","open","high","low","close","previous_close","change","percent_change","volume"]}
    st.dataframe(pd.DataFrame([qshow]), hide_index=True, use_container_width=True)

    st.markdown("### Company information returned by the API")
    if profile.get("status") == "error" or not profile:
        st.info("No profile/fundamental data was returned for this symbol on the current API access.")
    else:
        pkeys = ["name","exchange","country","sector","industry","description","employees",
                 "return_on_equity","profit_margin","market_capitalization"]
        prow = {k: profile.get(k) for k in pkeys if profile.get(k) not in [None, ""]}
        if prow:
            st.json(prow)
        else:
            st.info("The provider returned no usable fundamental fields for this symbol.")

with tabs[2]:
    if df.empty:
        st.info("No historical data available.")
    else:
        chart_df = df.set_index("datetime")[["close"]]
        st.line_chart(chart_df)
        st.markdown("### Historical indicators")
        hdf = pd.DataFrame({
            "Indicator": ["3-month momentum", "1-year momentum", "Annualised volatility"],
            "Value": [
                "n/a" if not np.isfinite(mom3) else f"{mom3:+.1f}%",
                "n/a" if not np.isfinite(mom1) else f"{mom1:+.1f}%",
                "n/a" if not np.isfinite(vol) else f"{vol:.1f}%"
            ]
        })
        st.dataframe(hdf, hide_index=True, use_container_width=True)
        st.caption("This tab is intentionally a market-history view. It is not a backtest of the Triad strategy.")

with tabs[3]:
    st.markdown("### 📚 Simple glossary")
    glossary = {
        "ROE": "Return on Equity — roughly, how efficiently a company generates profit from shareholders' capital.",
        "Free cash flow": "Cash left after operating needs and necessary investment. It is useful for understanding how much cash a business can actually generate.",
        "Momentum": "How strongly a price has been moving in a direction over a period.",
        "Volatility": "How much returns fluctuate. Higher volatility usually means a bumpier ride.",
        "Drawdown": "The fall from a previous peak. A 30% drawdown means the investment is 30% below its previous high.",
        "Moat": "A durable competitive advantage that can make it difficult for competitors to take market share."
    }
    for k, v in glossary.items():
        st.markdown(f"**{k}** — {v}")

    st.markdown("### The three questions")
    st.write("1. **Good business?**")
    st.write("2. **Good price?**")
    st.write("3. **Good moment?**")
    st.caption("The first two lean more toward Buffett/Hohn; the third is where the Druckenmiller lens becomes more important.")

st.divider()
st.caption("Educational prototype. The three investor lenses are simplified proxies created for this app and are not their actual proprietary strategies. Nothing here is a promise of performance or personalised financial advice.")
