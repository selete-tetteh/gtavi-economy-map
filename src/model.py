"""
model.py
--------
Builds a linear regression model to predict GTA VI launch pricing.

Reads from the master_dataset table in MySQL, engineers features,
trains a linear regression model, evaluates it, and prints the
GTA VI price prediction with a confidence interval.

Why linear regression?
With only 7 data points, complex models like random forests or
neural networks would overfit badly — they would memorise the
training data rather than learn a generalizable pattern.
Linear regression is transparent, explainable, and appropriate
for small structured datasets with a clear numeric target.
Being able to explain your model choice is as important as
the model itself, particularly in interviews.

Features used:
- release_year: captures the time trend in pricing
- inflation_multiplier: captures the real purchasing power context
- gross_margin_pct: captures Take-Two's financial health at launch time

Target variable:
- base_price_real: inflation-adjusted base launch price in 2025 dollars
  We predict in real terms then convert back to nominal at the end.
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import LeaveOneOut
import os
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    """
    Create a SQLAlchemy engine for MySQL.
    Passwords containing special characters must be URL-encoded
    so SQLAlchemy parses the connection string correctly.
    """
    from urllib.parse import quote_plus
    user = os.getenv("DB_USER")
    password = quote_plus(os.getenv("DB_PASSWORD"))
    host = os.getenv("DB_HOST")
    database = os.getenv("DB_NAME")
    return create_engine(f"mysql+mysqlconnector://{user}:{password}@{host}/{database}")


def load_master_dataset(engine):
    """
    Load the master dataset from MySQL.
    We exclude the GTA V Next-Gen re-release from modelling —
    it was a discounted port, not a new title, and would skew
    the model's understanding of new release pricing.
    """
    query = """
        SELECT
            game_title,
            release_year,
            base_price_real,
            premium_price_real,
            inflation_multiplier,
            gross_margin_pct
        FROM master_dataset
        WHERE game_title != 'Grand Theft Auto V (Next-Gen)'
        ORDER BY release_year
    """
    df = pd.read_sql(query, engine)
    print(f"Loaded {len(df)} records for modelling")
    print(f"Years covered: {df['release_year'].min()} to {df['release_year'].max()}")
    return df


def engineer_features(df):
    """
    Prepare the feature matrix (X) and target vector (y).

    We drop rows with missing values in any feature column.
    For this dataset that means rows without Take-Two financial
    data (2008 and 2010) will be excluded from the financial
    feature but included in simpler feature sets.

    Two models are trained:
    - Model A: year + inflation only (uses all 6 records)
    - Model B: year + inflation + gross margin (uses records with financial data)

    This is honest modelling — we do not impute or guess missing values
    for a dataset this small. We acknowledge the limitation and train
    on what we have.
    """
    # Model A features — no financial data required
    X_a = df[["release_year", "inflation_multiplier"]].copy()
    y = df["base_price_real"].copy()

    # Model B features — requires gross margin
    df_b = df.dropna(subset=["gross_margin_pct"])
    X_b = df_b[["release_year", "inflation_multiplier", "gross_margin_pct"]].copy()
    y_b = df_b["base_price_real"].copy()

    print(f"\nModel A: {len(X_a)} records (year + inflation)")
    print(f"Model B: {len(X_b)} records (year + inflation + gross margin)")

    return X_a, y, X_b, y_b, df_b


def evaluate_model(model, X, y, model_name):
    """
    Evaluate model performance using Leave-One-Out cross validation.

    With only 6-7 data points, a standard train/test split would
    leave too few records in either set to be meaningful.
    Leave-One-Out (LOO) cross validation trains on all records
    except one, predicts the held-out record, then repeats for
    every record. This gives the most honest performance estimate
    for very small datasets.
    """
    loo = LeaveOneOut()
    predictions = []
    actuals = []

    X_arr = X.values
    y_arr = y.values

    for train_idx, test_idx in loo.split(X_arr):
        X_train, X_test = X_arr[train_idx], X_arr[test_idx]
        y_train, y_test = y_arr[train_idx], y_arr[test_idx]

        m = LinearRegression()
        m.fit(X_train, y_train)
        predictions.append(m.predict(X_test)[0])
        actuals.append(y_test[0])

    mae = mean_absolute_error(actuals, predictions)

    # Train final model on all data for prediction
    model.fit(X, y)
    r2 = r2_score(y, model.predict(X))

    print(f"\n{model_name} Performance:")
    print(f"  R-squared:           {r2:.4f}")
    print(f"  Mean Absolute Error: ${mae:.2f} (LOO cross-validation)")
    print(f"  Interpretation: On average, predictions are ${mae:.2f} off in 2025 dollar terms")

    return model, mae


def predict_gtavi(model_a, model_b, mae_a, mae_b, cpi_df):
    """
    Generate GTA VI price predictions using both models.

    Assumptions for GTA VI (2026):
    - release_year: 2026
    - inflation_multiplier: CPI_2025 / CPI_2026_estimate
      We estimate 2026 CPI by applying the average annual CPI
      growth rate from the last 5 years to 2025's value.
    - gross_margin_pct: We use Take-Two's FY2025 gross margin (54.35%)
      as the most recent available figure.

    Predictions are made in real (2025) dollar terms then converted
    back to nominal 2026 dollars for the final price estimate.
    """
    # Estimate 2026 CPI using recent inflation trend
    recent_cpi = cpi_df.tail(5)
    avg_annual_growth = (
        (recent_cpi["annual_cpi"].iloc[-1] / recent_cpi["annual_cpi"].iloc[0])
        ** (1 / (len(recent_cpi) - 1)) - 1
    )
    cpi_2025 = cpi_df["annual_cpi"].iloc[-1]
    cpi_2026_estimate = round(cpi_2025 * (1 + avg_annual_growth), 3)
    inflation_multiplier_2026 = round(cpi_2025 / cpi_2026_estimate, 4)

    print(f"\nGTA VI Prediction Assumptions:")
    print(f"  Estimated 2026 CPI:         {cpi_2026_estimate}")
    print(f"  Inflation multiplier (2026): {inflation_multiplier_2026}")
    print(f"  Average annual CPI growth:  {avg_annual_growth*100:.2f}%")

    # Model A prediction
    X_gtavi_a = np.array([[2026, inflation_multiplier_2026]])
    pred_a_real = model_a.predict(X_gtavi_a)[0]
    pred_a_nominal = round(pred_a_real / inflation_multiplier_2026, 2)

    # Model B prediction
    gross_margin_2026 = 54.35
    X_gtavi_b = np.array([[2026, inflation_multiplier_2026, gross_margin_2026]])
    pred_b_real = model_b.predict(X_gtavi_b)[0]
    pred_b_nominal = round(pred_b_real / inflation_multiplier_2026, 2)

    # Convert MAE to nominal for confidence intervals
    mae_a_nominal = round(mae_a / inflation_multiplier_2026, 2)
    mae_b_nominal = round(mae_b / inflation_multiplier_2026, 2)

    print(f"\nGTA VI Base Price Predictions:")
    print(f"  Model A (year + inflation):")
    print(f"    Real (2025 $):   ${pred_a_real:.2f}")
    print(f"    Nominal (2026 $): ${pred_a_nominal:.2f}")
    print(f"    Range:           ${pred_a_nominal - mae_a_nominal:.2f} to ${pred_a_nominal + mae_a_nominal:.2f}")

    print(f"\n  Model B (+ gross margin):")
    print(f"    Real (2025 $):   ${pred_b_real:.2f}")
    print(f"    Nominal (2026 $): ${pred_b_nominal:.2f}")
    print(f"    Range:           ${pred_b_nominal - mae_b_nominal:.2f} to ${pred_b_nominal + mae_b_nominal:.2f}")

    return {
        "model_a_nominal": pred_a_nominal,
        "model_b_nominal": pred_b_nominal,
        "mae_a_nominal": mae_a_nominal,
        "mae_b_nominal": mae_b_nominal,
        "cpi_2026_estimate": cpi_2026_estimate,
        "inflation_multiplier_2026": inflation_multiplier_2026
    }


def run():
    engine = get_engine()

    # Load data
    df = load_master_dataset(engine)
    cpi_df = pd.read_sql(
        "SELECT year, annual_cpi FROM cpi_data ORDER BY year",
        engine
    )

    # Engineer features
    X_a, y_a, X_b, y_b, df_b = engineer_features(df)

    # Train and evaluate both models
    model_a = LinearRegression()
    model_b = LinearRegression()

    model_a, mae_a = evaluate_model(model_a, X_a, y_a, "Model A (year + inflation)")
    model_b, mae_b = evaluate_model(model_b, X_b, y_b, "Model B (year + inflation + gross margin)")

    # Generate GTA VI predictions
    predictions = predict_gtavi(model_a, model_b, mae_a, mae_b, cpi_df)

    print("\nPhase 3 complete. Predictions ready for dashboard.")
    return model_a, model_b, predictions, df, cpi_df


if __name__ == "__main__":
    run()
