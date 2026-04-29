"""
model.py
--------
Trains a linear regression model to predict GTA VI launch pricing.

Reads from master_dataset in MySQL, trains on 42 historical AAA
game titles across 5 publishers (2007-2023), and outputs a price
prediction with confidence interval for GTA VI (2026).

Why linear regression?
With 42 data points and a clear numeric target, linear regression
is the appropriate tool. It is transparent, explainable, and
directly defensible. Complex models would overfit on this dataset.

Features:
- release_year:          time trend in pricing
- platform_generation:   console era effect (1/2/3)
- inflation_multiplier:  real purchasing power context
- had_premium_edition:   whether a premium tier existed

Target: base_price_real (inflation-adjusted 2025 dollars)
Prediction is converted back to nominal at the end.

Evaluation: Leave-One-Out cross-validation.
With 42 data points, LOO provides the most honest error estimate.
"""

import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut

load_dotenv()


def get_engine():
    """SQLAlchemy engine for pandas read operations."""
    password = quote_plus(os.getenv("DB_PASSWORD"))
    return create_engine(
        f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{password}"
        f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    )


def load_data():
    """Load master dataset and CPI data from MySQL."""
    engine = get_engine()
    df = pd.read_sql("""
        SELECT game_title, publisher, release_year, platform_generation,
               had_premium_edition, base_price_nominal, base_price_real,
               premium_price_nominal, premium_price_real, inflation_multiplier
        FROM master_dataset
        ORDER BY release_year
    """, engine)
    df_cpi = pd.read_sql(
        "SELECT year, annual_cpi FROM cpi_data ORDER BY year", engine
    )
    return df, df_cpi


def train_model(df):
    """
    Train linear regression model using LOO cross-validation for evaluation.
    Returns the trained model and LOO MAE.
    """
    features = ["release_year", "platform_generation", "inflation_multiplier", "had_premium_edition"]
    target = "base_price_real"

    X = df[features]
    y = df[target]

    loo = LeaveOneOut()
    loo_preds, loo_actuals = [], []

    for train_idx, test_idx in loo.split(X.values):
        m = LinearRegression()
        m.fit(X.values[train_idx], y.values[train_idx])
        loo_preds.append(m.predict(X.values[test_idx])[0])
        loo_actuals.append(y.values[test_idx][0])

    model = LinearRegression()
    model.fit(X, y)

    mae = mean_absolute_error(loo_actuals, loo_preds)
    r2_train = r2_score(y, model.predict(X))
    r2_loo = r2_score(loo_actuals, loo_preds)

    print("Model Performance:")
    print(f"  R-squared (training): {r2_train:.4f}")
    print(f"  R-squared (LOO):      {r2_loo:.4f}")
    print(f"  MAE (LOO):            ${mae:.2f} in 2025 dollar terms")

    return model, mae


def predict_gtavi(model, mae, df, df_cpi):
    """
    Generate GTA VI price prediction for 2026.

    2026 CPI is estimated using the 5-year average annual growth rate.
    This is more conservative than using only the most recent year.
    """
    recent = df_cpi.tail(5)
    avg_growth = (
        (recent["annual_cpi"].iloc[-1] / recent["annual_cpi"].iloc[0])
        ** (1 / (len(recent) - 1)) - 1
    )
    cpi_2025 = df_cpi.loc[df_cpi["year"] == 2025, "annual_cpi"].values[0]
    cpi_2026 = cpi_2025 * (1 + avg_growth)
    multiplier_2026 = round(cpi_2025 / cpi_2026, 4)

    X_pred = pd.DataFrame([[2026, 3, multiplier_2026, 1]],
                           columns=["release_year", "platform_generation",
                                    "inflation_multiplier", "had_premium_edition"])
    pred_real = model.predict(X_pred)[0]
    pred_nominal = round(pred_real / multiplier_2026, 2)
    mae_nominal = round(mae / multiplier_2026, 2)

    gen3_premium = df[
        (df["platform_generation"] == 3) &
        (df["had_premium_edition"] == 1) &
        (df["premium_price_nominal"].notna())
    ].copy()
    avg_gap = (gen3_premium["premium_price_nominal"] - gen3_premium["base_price_nominal"]).mean()
    pred_premium = round(pred_nominal + avg_gap, 2)

    result = {
        "pred_real":        round(pred_real, 2),
        "pred_nominal":     pred_nominal,
        "pred_premium":     pred_premium,
        "mae_nominal":      mae_nominal,
        "low":              round(pred_nominal - mae_nominal, 2),
        "high":             round(pred_nominal + mae_nominal, 2),
        "cpi_2026":         round(cpi_2026, 3),
        "multiplier_2026":  multiplier_2026,
        "avg_growth_pct":   round(avg_growth * 100, 2)
    }

    print("\nGTA VI Prediction:")
    print(f"  Base edition (nominal 2026): ${result['pred_nominal']}")
    print(f"  Premium edition:             ${result['pred_premium']}")
    print(f"  Confidence range:            ${result['low']} - ${result['high']}")

    return result


def run():
    df, df_cpi = load_data()
    print(f"Loaded {len(df)} records for modelling")
    model, mae = train_model(df)
    prediction = predict_gtavi(model, mae, df, df_cpi)
    print("\nmodel.py complete")
    return model, mae, prediction, df, df_cpi


if __name__ == "__main__":
    run()
