
import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Triad Investment Engine", page_icon="📈", layout="wide")
st.title("📈 Triad Investment Engine")
st.caption("Portfolio Builder + Single Investment Analyzer | Buffett + Chris Hohn + Druckenmiller")

with st.sidebar:
    st.header("⚙️ Data")
    api_key = st.text_input("Twelve Data API key", type="password")
    st.caption("Keep your API key private. This app uses the free/basic market-data endpoints.")
    st.divider()
    st.markdown("**Buffett** — quality & long-term economics")
    st.markdown("**Hohn** — cash generation & capital allocation")
    st.markdown("**Druckenmiller** — trend, momentum & risk")
    st.caption("These are transparent educational proxies, not the investors' proprietary methods.")

@st.cache_data(ttl=1800, show_spinner=False)
def get_quote(sym, key):
    try:
        return requests.get("https://api.twelvedata.com/quote",
            params={"symbol":sym,"apikey":key},timeout=15).json()
    except: return {}

@st.cache_data(ttl=1800, show_spinner=False)
def get_history(sym, key):
    try:
        return requests.get("https://api.twelvedata.com/time_series",
            params={"symbol":sym,"interval":"1day","outputsize":260,"apikey":key},timeout=15).json()
    except: return {}

def make_df(x):
    vals=x.get("values",[]) if isinstance(x,dict) else []
    if not vals: return pd.DataFrame()
    d=pd.DataFrame(vals)
    d["datetime"]=pd.to_datetime(d["datetime"])
    d=d.sort_values("datetime")
    d["close"]=pd.to_numeric(d["close"],errors="coerce")
    return d.dropna(subset=["close"])

def num(x):
    try:return float(x)
    except:return np.nan

def momentum(d, days):
    if len(d)<=days:return np.nan
    return (d.close.iloc[-1]/d.close.iloc[-days-1]-1)*100

def score(sym):
    q=get_quote(sym,api_key)
    d=make_df(get_history(sym,api_key))
    m3=momentum(d,63)
    m1=momentum(d,252)
    ret=d.close.pct_change().dropna()
    vol=ret.std()*np.sqrt(252)*100 if len(ret)>30 else np.nan

    # Free-plan-safe model:
    # fundamental quality is deliberately neutral when the free endpoint does not provide it.
    # This prevents fabricated fundamentals.
    quality=50.0
    buff=0.70*quality + 0.30*(50 if not np.isfinite(m1) else np.clip(50+m1*.70,0,100))
    hohn=0.65*quality + 0.35*(50 if not np.isfinite(m1) else np.clip(50+m1*.60,0,100))
    druck=(
        0.45*(50 if not np.isfinite(m3) else np.clip(50+m3,0,100))
        +0.35*(50 if not np.isfinite(m1) else np.clip(50+m1*.50,0,100))
        +0.20*(50 if not np.isfinite(vol) else np.clip(100-vol*3,0,100))
    )
    triad=.38*buff+.34*hohn+.28*druck

    name=q.get("name") or sym
    return {
        "Symbol":sym, "Name":name, "Price":num(q.get("close")),
        "Buffett":round(buff,1), "Hohn":round(hohn,1),
        "Druckenmiller":round(druck,1), "Triad":round(triad,1),
        "Momentum 1Y":m1, "Volatility":vol
    }

# Deliberately manageable for the free API.
UNIVERSE=[
"AAPL","MSFT","GOOGL","AMZN","META","NVDA","AVGO","BRK.B","V","MA",
"JPM","JNJ","PG","KO","PEP","COST","WMT","HD","UNH","LLY",
"XOM","CVX","CAT","GE","ORCL","ADBE","CRM","NFLX","TSLA","AMD"
]

tabs=st.tabs(["🏆 Build My Portfolio","🔎 Analyse One Investment","📚 Learn"])

with tabs[0]:
    st.header("🏆 Build My Portfolio")
    st.write("Enter your money, date, horizon and risk. The app ranks the available universe and produces **three portfolio options: Top 3, Top 5 and Top 10**.")

    c1,c2,c3,c4=st.columns(4)
    with c1: capital=st.number_input("💰 Capital",min_value=100.0,value=10000.0,step=500.0)
    with c2: start=st.date_input("📅 Investment date")
    with c3: years=st.selectbox("⏳ Horizon",[1,3,5,10,15],index=2,format_func=lambda x:f"{x} year{'s' if x!=1 else ''}")
    with c4: risk=st.selectbox("⚖️ Risk",["Low","Medium","High"],index=1)

    st.markdown("### What you will receive")
    st.write("**Top 3:** concentrated portfolio • **Top 5:** balanced concentration • **Top 10:** broader diversification")

    if st.button("🚀 Find my Top 3 / 5 / 10",type="primary"):
        if not api_key:
            st.warning("Enter your Twelve Data API key in the sidebar.")
        else:
            rows=[]
            bar=st.progress(0)
            for i,sym in enumerate(UNIVERSE):
                try:
                    rows.append(score(sym))
                except Exception:
                    pass
                bar.progress((i+1)/len(UNIVERSE))
            bar.empty()

            df=pd.DataFrame(rows)
            if df.empty:
                st.error("No usable market data was returned. Check the API key or free-plan limits.")
            else:
                df=df.sort_values("Triad",ascending=False).reset_index(drop=True)
                st.success(f"Ranking completed for {len(df)} instruments.")
                st.subheader("🏅 Current model ranking")
                ranking=df.copy()
                ranking.insert(0,"Rank",range(1,len(ranking)+1))
                st.dataframe(ranking[["Rank","Symbol","Name","Triad","Buffett","Hohn","Druckenmiller","Momentum 1Y","Volatility"]],
                             hide_index=True,use_container_width=True)

                st.subheader("💼 Portfolio options")
                tabs2=st.tabs(["🥇 Top 3","🥈 Top 5","🥉 Top 10"])

                for tab,names in zip(tabs2,[3,5,10]):
                    with tab:
                        top=df.head(names).copy()

                        # Risk controls the maximum concentration and a small stabilising reserve.
                        if risk=="Low":
                            reserve=0.20; max_weight={3:.40,5:.30,10:.20}[names]
                        elif risk=="Medium":
                            reserve=0.10; max_weight={3:.50,5:.35,10:.18}[names]
                        else:
                            reserve=0.05; max_weight={3:.65,5:.45,10:.15}[names]

                        raw=np.maximum(top["Triad"].to_numpy(),1)
                        weights=raw/raw.sum()*(1-reserve)
                        weights=np.minimum(weights,max_weight)
                        weights=weights/weights.sum()*(1-reserve)

                        top["Weight %"]=(weights*100).round(1)
                        top["Amount"]=(weights*capital).round(2)
                        top.insert(0,"Rank",range(1,len(top)+1))

                        st.markdown(f"### Top {names} — suggested diversification")
                        st.caption(f"Risk: {risk} | Capital: {capital:,.2f} | Horizon: {years} years | Date: {start}")
                        st.dataframe(
                            top[["Rank","Symbol","Name","Weight %","Amount","Triad","Buffett","Hohn","Druckenmiller"]],
                            hide_index=True,use_container_width=True
                        )

                        total_invested=top["Amount"].sum()
                        reserve_amount=capital-total_invested
                        st.write(f"**Invested:** {total_invested:,.2f}  |  **Reserve/cash sleeve:** {reserve_amount:,.2f}")

                        st.markdown("#### 🧠 How to read this")
                        if names==3:
                            st.write("Three names: more concentrated. The model is expressing its strongest-ranked ideas with less diversification.")
                        elif names==5:
                            st.write("Five names: a middle ground between concentration and diversification.")
                        else:
                            st.write("Ten names: more diversification and less dependence on any one company.")

                        st.markdown("#### ⚠️ What this model does not know")
                        st.write("The free data tier does not provide every fundamental field needed for a full Buffett/Hohn analysis. Missing fundamentals are treated as neutral rather than invented. The Druckenmiller lens is currently a transparent price/trend proxy.")

                        st.download_button(
                            f"⬇️ Download Top {names} CSV",
                            top.to_csv(index=False).encode(),
                            f"triad_top{names}_allocation.csv",
                            "text/csv",
                            key=f"download_{names}"
                        )

with tabs[1]:
    st.header("🔎 Analyse One Investment")
    st.write("Enter a company, ETF or supported instrument. You receive the same three lenses plus a two-sided assessment.")
    sym=st.text_input("Ticker / investment","AAPL",key="single").upper().strip()
    horizon_single=st.selectbox("Horizon",["1 year","3 years","5 years","10+ years"],index=2,key="single_horizon")
    risk_single=st.selectbox("Risk",["Low","Medium","High"],index=1,key="single_risk")

    if st.button("🔍 Analyse",type="primary",key="analyse_single"):
        if not api_key:
            st.warning("Enter your Twelve Data API key in the sidebar.")
        else:
            r=score(sym)
            st.metric("Triad Score",f"{r['Triad']}/100")
            a,b,c=st.columns(3)
            a.metric("Buffett",r["Buffett"])
            b.metric("Hohn",r["Hohn"])
            c.metric("Druckenmiller",r["Druckenmiller"])

            left,right=st.columns(2)
            with left:
                st.subheader("🟢 Case in favour")
                st.write("The model sees alignment across the three lenses. Check business quality, cash generation, valuation and trend before acting.")
                st.write("1Y momentum: "+("n/a" if not np.isfinite(r["Momentum 1Y"]) else f"{r['Momentum 1Y']:+.1f}%"))
            with right:
                st.subheader("🔴 Case against / risks")
                st.write("The thesis can fail if valuation is excessive, fundamentals deteriorate, trend reverses or important data is missing.")
                st.write("Annualised volatility: "+("n/a" if not np.isfinite(r["Volatility"]) else f"{r['Volatility']:.1f}%"))

with tabs[2]:
    st.header("📚 How the engine works")
    st.markdown("""
**Portfolio mode**

Capital + date + horizon + risk → rank universe → Top 3 / Top 5 / Top 10 → percentage + amount.

**Single investment mode**

Ticker → Buffett lens + Hohn lens + Druckenmiller lens → score + case in favour + risks.

The three lenses are simplified educational proxies based on publicly documented aspects of the investors' approaches. The app does not reproduce private/proprietary methods or imply that these investors would make the same investment today.
""")
