"""
app.py
------
Streamlit dashboard for the GTA VI Economy Map project.

Sections:
1. Overview metrics
2. Price history — nominal vs real over time
3. Inflation impact by console generation
4. Publisher pricing comparison
5. Premium edition markup analysis
6. GTA VI price prediction
7. Take-Two financial context

Run locally:
    streamlit run app.py

Deploy:
    Push to GitHub, connect to share.streamlit.io
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import LeaveOneOut

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GTA VI Economy Map",
    page_icon="🎮",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        color: #1A3A5C;
        margin-bottom: 0;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #5D6D7E;
        margin-top: 0.2rem;
        margin-bottom: 1.5rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #5D6D7E;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #1A3A5C;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1A3A5C;
        border-bottom: 2px solid #2E86C1;
        padding-bottom: 0.3rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .insight-box {
        background-color: #EBF5FB;
        border-left: 4px solid #2E86C1;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin: 1rem 0;
        font-size: 0.95rem;
        color: #1A3A5C;
    }
    .limitation-box {
        background-color: #FEF9E7;
        border-left: 4px solid #F39C12;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        margin: 1rem 0;
        font-size: 0.95rem;
        color: #7D6608;
    }
</style>
""", unsafe_allow_html=True)


# ── Database ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_engine():
    """
    Cache the database engine across Streamlit reruns.
    st.cache_resource keeps one connection pool alive for the session.
    """
    password = quote_plus(os.getenv("DB_PASSWORD"))
    return create_engine(
        f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{password}"
        f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    )


@st.cache_data
def load_data():
    """
    Load and cache all data from MySQL.
    st.cache_data caches the DataFrame so the database is not
    queried on every user interaction — only on first load.
    """
    engine = get_engine()
    df = pd.read_sql("SELECT * FROM master_dataset ORDER BY release_year", engine)
    df_cpi = pd.read_sql("SELECT year, annual_cpi FROM cpi_data ORDER BY year", engine)
    df_fin = pd.read_sql("""
        SELECT fiscal_year, total_revenue_usd_millions,
               gross_margin_pct, net_income_usd_millions
        FROM taketwo_financials ORDER BY fiscal_year
    """, engine)
    return df, df_cpi, df_fin


@st.cache_data
def run_model(df_json, cpi_json):
    """
    Train model and generate prediction. Cached so it only reruns
    when the underlying data changes, not on every user interaction.
    DataFrames are passed as JSON strings for cache compatibility.
    """
    from io import StringIO
    df = pd.read_json(StringIO(df_json))
    df_cpi = pd.read_json(StringIO(cpi_json))

    features = ["release_year", "platform_generation",
                "inflation_multiplier", "had_premium_edition"]
    X = df[features]
    y = df["base_price_real"]

    loo = LeaveOneOut()
    preds, actuals = [], []
    for train_idx, test_idx in loo.split(X.values):
        m = LinearRegression()
        m.fit(X.values[train_idx], y.values[train_idx])
        preds.append(m.predict(X.values[test_idx])[0])
        actuals.append(y.values[test_idx][0])

    model = LinearRegression()
    model.fit(X, y)
    mae = mean_absolute_error(actuals, preds)

    recent = df_cpi.tail(5)
    avg_growth = (
        (recent["annual_cpi"].iloc[-1] / recent["annual_cpi"].iloc[0])
        ** (1 / (len(recent) - 1)) - 1
    )
    cpi_2025 = df_cpi.loc[df_cpi["year"] == 2025, "annual_cpi"].values[0]
    cpi_2026 = cpi_2025 * (1 + avg_growth)
    multiplier_2026 = round(cpi_2025 / cpi_2026, 4)

    X_pred = pd.DataFrame(
        [[2026, 3, multiplier_2026, 1]],
        columns=features
    )
    pred_real = model.predict(X_pred)[0]
    pred_nominal = round(pred_real / multiplier_2026, 2)
    mae_nominal = round(mae / multiplier_2026, 2)

    gen3 = df[
        (df["platform_generation"] == 3) &
        (df["had_premium_edition"] == 1) &
        (df["premium_price_nominal"].notna())
    ]
    avg_gap = (gen3["premium_price_nominal"] - gen3["base_price_nominal"]).mean()
    pred_premium = round(pred_nominal + avg_gap, 2)

    return {
        "pred_real": round(pred_real, 2),
        "pred_nominal": pred_nominal,
        "pred_premium": pred_premium,
        "mae": round(mae, 2),
        "mae_nominal": mae_nominal,
        "low": round(pred_nominal - mae_nominal, 2),
        "high": round(pred_nominal + mae_nominal, 2),
        "cpi_2026": round(cpi_2026, 3),
        "avg_growth_pct": round(avg_growth * 100, 2)
    }


# ── Load data ─────────────────────────────────────────────────────────────────
df, df_cpi, df_fin = load_data()
prediction = run_model(df.to_json(), df_cpi.to_json())

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">GTA VI Economy Map</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Predicting GTA VI launch pricing using 16 years of AAA game pricing data, '
    'US CPI inflation, and Take-Two financial analysis</div>',
    unsafe_allow_html=True
)

# ── Overview metrics ──────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Games Analysed", "42")
with col2:
    st.metric("Publishers", "5")
with col3:
    st.metric("Years Covered", "2007 – 2023")
with col4:
    st.metric("Predicted Base Price", f"${prediction['pred_nominal']}")
with col5:
    st.metric("Predicted Premium Price", f"${prediction['pred_premium']}")

st.divider()

# ── Section 1: Price history ──────────────────────────────────────────────────
st.markdown('<div class="section-header">1. Nominal vs Real Price History</div>',
            unsafe_allow_html=True)

st.markdown(
    '<div class="insight-box">The nominal price of AAA games held flat at $59.99 for 13 years. '
    'In real (inflation-adjusted) terms, however, games became significantly cheaper over time. '
    'A $59.99 game in 2007 cost the equivalent of $93 in today\'s money. '
    'The jump to $69.99 in 2020 still left games cheaper in real terms than they were in 2007.</div>',
    unsafe_allow_html=True
)

avg_real = df.groupby("release_year")["base_price_real"].mean()
avg_nominal = df.groupby("release_year")["base_price_nominal"].mean()
years = sorted(df["release_year"].unique())

fig1, ax1 = plt.subplots(figsize=(12, 4.5))
ax1.plot(years, [avg_real[y] for y in years],
         color="#2E86C1", linewidth=2.5, marker="o", markersize=6,
         label="Real price (2025 $)", zorder=3)
ax1.plot(years, [avg_nominal[y] for y in years],
         color="#E74C3C", linewidth=2.5, marker="s", markersize=6,
         label="Nominal price", zorder=3)
ax1.axvspan(2019.5, 2023.5, alpha=0.07, color="orange", label="$69.99 transition era")
ax1.fill_between(years,
                 [avg_nominal[y] for y in years],
                 [avg_real[y] for y in years],
                 alpha=0.08, color="#2E86C1", label="Inflation gap")
ax1.set_xlabel("Release Year")
ax1.set_ylabel("Average Price (USD)")
ax1.set_title("AAA Game Prices: Nominal vs Real (2025 Dollars)", fontweight="bold")
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax1.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax1.legend(fontsize=9)
ax1.grid(axis="y", alpha=0.3)
ax1.set_xlim(2006, 2024)
plt.tight_layout()
st.pyplot(fig1)
plt.close()

# ── Section 2: Inflation impact ───────────────────────────────────────────────
st.markdown('<div class="section-header">2. Inflation Impact by Console Generation</div>',
            unsafe_allow_html=True)

df_copy = df.copy()
df_copy["inflation_added"] = df_copy["base_price_real"] - df_copy["base_price_nominal"]
gen_avg = df_copy.groupby("platform_generation").agg(
    avg_nominal=("base_price_nominal", "mean"),
    avg_real=("base_price_real", "mean")
).round(2)

gen_labels = ["Gen 1\n(PS3/360\n2007-2013)",
              "Gen 2\n(PS4/One\n2014-2019)",
              "Gen 3\n(PS5/Series\n2020-2023)"]

fig2, ax2 = plt.subplots(figsize=(10, 4.5))
x = np.arange(3)
w = 0.35
bars1 = ax2.bar(x - w/2, gen_avg["avg_nominal"],
                width=w, color="#E74C3C", alpha=0.85, label="Nominal price", zorder=3)
bars2 = ax2.bar(x + w/2, gen_avg["avg_real"],
                width=w, color="#2E86C1", alpha=0.85, label="Real price (2025 $)", zorder=3)
for bar in bars1:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             f"${bar.get_height():.2f}", ha="center", va="bottom", fontsize=9)
for bar in bars2:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             f"${bar.get_height():.2f}", ha="center", va="bottom", fontsize=9)
ax2.set_xticks(x)
ax2.set_xticklabels(gen_labels, fontsize=10)
ax2.set_ylabel("Average Price (USD)")
ax2.set_title("Inflation Impact by Console Generation", fontweight="bold")
ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax2.legend(fontsize=10)
ax2.grid(axis="y", alpha=0.3)
ax2.set_ylim(0, 100)
plt.tight_layout()
st.pyplot(fig2)
plt.close()

# ── Section 3: Publisher comparison ──────────────────────────────────────────
st.markdown('<div class="section-header">3. Publisher Pricing Strategy</div>',
            unsafe_allow_html=True)

st.markdown(
    '<div class="insight-box">All five publishers tracked the same real price decline from 2007 to 2019. '
    'Nintendo is the notable outlier in 2022 — holding Pokemon Scarlet/Violet at $59.99 while every '
    'other publisher had moved to $69.99. By 2023 even Nintendo followed with Tears of the Kingdom.</div>',
    unsafe_allow_html=True
)

publisher_year = df.groupby(["publisher", "release_year"])["base_price_real"].mean().reset_index()
colors = {
    "Activision":     "#E74C3C",
    "EA":             "#F39C12",
    "Nintendo":       "#E91E63",
    "Rockstar Games": "#2E86C1",
    "Sony":           "#27AE60"
}

fig3, ax3 = plt.subplots(figsize=(12, 4.5))
for pub in sorted(df["publisher"].unique()):
    pub_data = publisher_year[publisher_year["publisher"] == pub].sort_values("release_year")
    ax3.plot(pub_data["release_year"], pub_data["base_price_real"],
             color=colors.get(pub, "gray"), linewidth=1.5,
             marker="o", markersize=5, label=pub, alpha=0.85)
ax3.set_xlabel("Release Year")
ax3.set_ylabel("Real Base Price (2025 $)")
ax3.set_title("Real Price by Publisher Over Time", fontweight="bold")
ax3.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax3.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax3.legend(fontsize=9)
ax3.grid(axis="y", alpha=0.3)
ax3.set_xlim(2006, 2024)
plt.tight_layout()
st.pyplot(fig3)
plt.close()

# ── Section 4: Premium gap ────────────────────────────────────────────────────
st.markdown('<div class="section-header">4. Premium Edition Markup</div>',
            unsafe_allow_html=True)

premium = df[(df["had_premium_edition"] == 1) & (df["premium_price_nominal"].notna())].copy()
premium["gap"] = premium["premium_price_nominal"] - premium["base_price_nominal"]
avg_gap_by_year = premium.groupby("release_year")["gap"].mean().round(2)

fig4, ax4 = plt.subplots(figsize=(11, 4.5))
bars = ax4.bar(avg_gap_by_year.index, avg_gap_by_year.values,
               color="#1A3A5C", alpha=0.85, width=0.7, zorder=3)
for bar, val in zip(bars, avg_gap_by_year.values):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
             f"${val:.0f}", ha="center", va="bottom", fontsize=9)
ax4.axhline(y=avg_gap_by_year.mean(), color="#E74C3C", linestyle="--",
            linewidth=1.5, label=f"Average gap: ${avg_gap_by_year.mean():.2f}", zorder=4)
ax4.set_xlabel("Release Year")
ax4.set_ylabel("Premium Gap (USD)")
ax4.set_title("Premium Edition Markup Over Base Price by Year", fontweight="bold")
ax4.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax4.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax4.legend(fontsize=10)
ax4.grid(axis="y", alpha=0.3)
plt.tight_layout()
st.pyplot(fig4)
plt.close()

# ── Section 5: The prediction ─────────────────────────────────────────────────
st.markdown('<div class="section-header">5. GTA VI Price Prediction</div>',
            unsafe_allow_html=True)

col_pred1, col_pred2 = st.columns(2)

with col_pred1:
    st.markdown("**Model inputs for GTA VI (2026)**")
    st.markdown(f"- Release year: **2026**")
    st.markdown(f"- Platform generation: **3** (PS5 / Xbox Series X)")
    st.markdown(f"- Premium edition: **Yes** (Rockstar has offered one since GTA V)")
    st.markdown(f"- Estimated 2026 CPI: **{prediction['cpi_2026']}**")
    st.markdown(f"- Average annual CPI growth used: **{prediction['avg_growth_pct']}%**")
    st.markdown(f"- Model MAE (LOO): **${prediction['mae']}** in 2025 dollar terms")

with col_pred2:
    st.markdown("**Prediction**")
    st.markdown(f"### Base Edition: ${prediction['pred_nominal']}")
    st.markdown(
        f'<p style="font-size:16px; color:black;">Confidence range: '
        f'${prediction["low"]} – ${prediction["high"]}</p>',
        unsafe_allow_html=True
    )
    st.markdown(f"### Premium Edition: ${prediction['pred_premium']}")
    st.markdown(
        f'<p style="font-size:16px; color:black;">Based on average Gen 3 premium gap of '
        f'${round(prediction["pred_premium"] - prediction["pred_nominal"], 2)}</p>',
        unsafe_allow_html=True
    )

fig5, axes5 = plt.subplots(1, 2, figsize=(13, 4.5))

ax5a = axes5[0]
avg_real_pred = df.groupby("release_year")["base_price_real"].mean()
years_pred = sorted(df["release_year"].unique())
ax5a.plot(years_pred, [avg_real_pred[y] for y in years_pred],
          color="#2E86C1", linewidth=2, marker="o", markersize=5,
          label="Historical avg real price", zorder=3)
ax5a.scatter([2026], [prediction["pred_real"]],
             color="#E74C3C", s=200, zorder=5, marker="*",
             label=f"GTA VI: ${prediction['pred_real']} (real)")
ax5a.errorbar([2026], [prediction["pred_real"]], yerr=prediction["mae"],
              fmt="none", color="#E74C3C", capsize=7, linewidth=2, zorder=4)
ax5a.set_xlabel("Release Year")
ax5a.set_ylabel("Real Price (2025 $)")
ax5a.set_title("Real Price Trend + GTA VI Prediction", fontweight="bold")
ax5a.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax5a.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
ax5a.legend(fontsize=9)
ax5a.grid(axis="y", alpha=0.3)

ax5b = axes5[1]
editions = ["Base Edition", "Premium Edition"]
prices = [prediction["pred_nominal"], prediction["pred_premium"]]
bar_colors = ["#2E86C1", "#1A3A5C"]
bars5 = ax5b.bar(editions, prices, color=bar_colors, width=0.5, zorder=3)
ax5b.errorbar(["Base Edition"], [prediction["pred_nominal"]],
              yerr=prediction["mae_nominal"],
              fmt="none", color="#E74C3C", capsize=8, linewidth=2, zorder=4)
for bar, price in zip(bars5, prices):
    ax5b.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
              f"${price:.2f}", ha="center", va="bottom", fontweight="bold", fontsize=13)
ax5b.text(0, prediction["pred_nominal"] - 9,
          f"Range: ${prediction['low']} - ${prediction['high']}",
          ha="center", fontsize=9, color="#E74C3C")
ax5b.set_ylabel("Predicted Launch Price (USD)")
ax5b.set_title("GTA VI Predicted Launch Pricing", fontweight="bold")
ax5b.yaxis.set_major_formatter(mticker.FormatStrFormatter("$%.0f"))
ax5b.set_ylim(0, max(prices) * 1.2)
ax5b.grid(axis="y", alpha=0.3)

plt.suptitle("GTA VI Economy Map — Model Prediction (2026)",
             fontsize=13, fontweight="bold", y=1.02)
plt.tight_layout()
st.pyplot(fig5)
plt.close()

st.markdown(
    '<div class="limitation-box"><strong>Model limitations:</strong> 42 data points is adequate '
    'but not large. The model learns industry-wide pricing trends, not Rockstar-specific behaviour. '
    'Rockstar has never released a mainline GTA at $69.99 — the $69.72 prediction reflects where '
    'the industry average sits, not a Rockstar-specific premium. The confidence interval is honest '
    'about this uncertainty.</div>',
    unsafe_allow_html=True
)

# ── Section 6: Take-Two financials ────────────────────────────────────────────
st.markdown('<div class="section-header">6. Take-Two Financial Context</div>',
            unsafe_allow_html=True)

st.markdown(
    '<div class="insight-box">Take-Two\'s revenue spiked dramatically in FY2014 (GTA V launch) '
    'and grew steadily through the GTA Online era. The large net losses in FY2023-2025 reflect '
    'goodwill impairment charges from the $12.7B Zynga acquisition, not operational decline. '
    'Gross margin has remained strong at 42-56%, indicating the core games business is healthy.</div>',
    unsafe_allow_html=True
)

fig6, ax6a = plt.subplots(figsize=(12, 4.5))
ax6b = ax6a.twinx()

ax6a.bar(df_fin["fiscal_year"], df_fin["total_revenue_usd_millions"],
         color="#2E86C1", alpha=0.7, width=0.7, label="Revenue ($M)", zorder=2)
ax6b.plot(df_fin["fiscal_year"], df_fin["gross_margin_pct"],
          color="#E74C3C", linewidth=2.5, marker="o",
          markersize=6, label="Gross Margin %", zorder=3)

for year, label in [(2014, "GTA V"), (2019, "RDR2")]:
    ax6a.axvline(x=year, color="gray", linestyle=":", alpha=0.6, linewidth=1.5)
    ax6a.text(year + 0.1, df_fin["total_revenue_usd_millions"].max() * 0.92,
              label, fontsize=8, color="gray")

ax6a.set_xlabel("Fiscal Year")
ax6a.set_ylabel("Revenue (USD Millions)", color="#2E86C1")
ax6b.set_ylabel("Gross Margin %", color="#E74C3C")
ax6a.set_title("Take-Two Interactive: Revenue & Gross Margin (2012-2025)", fontweight="bold")
ax6a.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}M"))
ax6b.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax6a.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))

lines1, labels1 = ax6a.get_legend_handles_labels()
lines2, labels2 = ax6b.get_legend_handles_labels()
ax6a.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")
ax6a.grid(axis="y", alpha=0.2)

plt.tight_layout()
st.pyplot(fig6)
plt.close()

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    """
    <div style="color: #95A5A6; font-size: 0.85rem;">
    <strong>Data sources:</strong>
    SteamSpy / VGInsights (game pricing) &nbsp;|&nbsp;
    US Bureau of Labor Statistics (CPI data) &nbsp;|&nbsp;
    Macrotrends / SEC EDGAR (Take-Two financials) &nbsp;|&nbsp;
    Publisher press releases<br>
    <strong>Methodology:</strong>
    Linear regression with Leave-One-Out cross-validation.
    Prices inflation-adjusted to 2025 dollars using US CPI.
    Prediction made before GTA VI launch — to be verified on release.
    </div>
    """,
    unsafe_allow_html=True
)
