"""
clean_data.py
-------------
Pulls raw data from MySQL, cleans and merges it into a single
master dataset, then writes it back to MySQL.

Steps:
1. Load all three raw tables from MySQL into pandas DataFrames
2. Inflation-adjust Rockstar prices to 2025 dollar terms using CPI data
3. Align datasets by year and merge into one master DataFrame
4. Write the master dataset back to MySQL as master_dataset

Why inflation-adjust?
A $59.99 game in 2008 is not the same as $59.99 in 2025.
Adjusting all prices to a common base year (2025) lets us
compare real purchasing power across time. Without this step,
the regression model would treat a 2008 price and a 2025 price
as equivalent, which would produce a misleading prediction.

Why write back to MySQL?
Keeping the master dataset in MySQL means it is queryable
independently of Python. Anyone with database access can
run SQL queries against it without touching the codebase.
This is the separation of concerns principle — the database
is the source of truth, Python is the analysis layer.
"""

import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Create and return a MySQL database connection."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def load_table(query):
    """
    Execute a SQL query and return results as a pandas DataFrame.
    Using pandas read_sql means we get proper column names and
    data types automatically — no manual parsing needed.
    """
    conn = get_connection()
    df = pd.read_sql(query, conn)
    conn.close()
    return df


def load_raw_data():
    """Load all three raw tables from MySQL."""
    prices = load_table("SELECT * FROM rockstar_prices")
    cpi = load_table("SELECT year, annual_cpi FROM cpi_data ORDER BY year")
    financials = load_table("""
        SELECT fiscal_year, total_revenue_usd_millions,
               gross_margin_pct, net_income_usd_millions
        FROM taketwo_financials
        ORDER BY fiscal_year
    """)

    print(f"Loaded {len(prices)} price records")
    print(f"Loaded {len(cpi)} CPI records")
    print(f"Loaded {len(financials)} financial records")

    return prices, cpi, financials


def adjust_for_inflation(prices_df, cpi_df):
    """
    Adjust all nominal prices to 2025 dollar terms.

    Formula: real_price = nominal_price * (cpi_2025 / cpi_release_year)

    Example:
    GTA V launched at $59.99 in 2013.
    CPI in 2013 = 232.957, CPI in 2025 = ~314.
    Real price = $59.99 * (314 / 232.957) = ~$80.84

    This means in real purchasing power, GTA V cost the
    equivalent of $80.84 in today's money — not $59.99.
    """
    # Get the 2025 CPI value as our base year
    cpi_2025 = cpi_df.loc[cpi_df["year"] == 2025, "annual_cpi"].values[0]
    print(f"\nBase year CPI (2025): {cpi_2025}")

    # Merge prices with CPI data on release year
    df = prices_df.merge(
        cpi_df.rename(columns={"year": "release_year", "annual_cpi": "annual_cpi"}),
        on="release_year",
        how="left"
    )

    # Flag any years missing CPI data
    missing_cpi = df[df["annual_cpi"].isna()]["release_year"].tolist()
    if missing_cpi:
        print(f"Warning: No CPI data found for years: {missing_cpi}")

    # Calculate inflation multiplier and adjusted prices
    df["cpi_2025"] = cpi_2025
    df["inflation_multiplier"] = (cpi_2025 / df["annual_cpi"]).round(4)
    df["base_price_real"] = (df["base_price_usd"] * df["inflation_multiplier"]).round(2)
    df["premium_price_real"] = (df["premium_price_usd"] * df["inflation_multiplier"]).round(2)

    return df


def merge_with_financials(prices_df, financials_df):
    """
    Merge inflation-adjusted prices with Take-Two financial data.

    We match on release year. Take-Two's fiscal year ends March 31,
    so their FY2014 (ending March 2014) is the closest financial
    context for a game released in calendar year 2013.
    We account for this with a one-year offset for pre-2018 data.

    For simplicity at this stage we match on calendar year directly
    and note the fiscal year offset in the README methodology section.
    """
    df = prices_df.merge(
        financials_df.rename(columns={"fiscal_year": "release_year"}),
        on="release_year",
        how="left"
    )

    return df


def write_master_dataset(df, conn):
    """
    Write the cleaned master dataset to MySQL.
    Clears existing data first so the script is safe to rerun.
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM master_dataset")

    insert_query = """
        INSERT INTO master_dataset (
            game_title, release_year, platform,
            base_price_nominal, premium_price_nominal,
            base_price_real, premium_price_real,
            annual_cpi, cpi_2025, inflation_multiplier,
            revenue_usd_millions, gross_margin_pct, net_income_usd_millions
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    records = []
    for _, row in df.iterrows():
        records.append((
            row["game_title"],
            int(row["release_year"]),
            row["platform"],
            row["base_price_usd"] if pd.notna(row["base_price_usd"]) else None,
            row["premium_price_usd"] if pd.notna(row["premium_price_usd"]) else None,
            row["base_price_real"] if pd.notna(row["base_price_real"]) else None,
            row["premium_price_real"] if pd.notna(row["premium_price_real"]) else None,
            row["annual_cpi"] if pd.notna(row["annual_cpi"]) else None,
            row["cpi_2025"] if pd.notna(row["cpi_2025"]) else None,
            row["inflation_multiplier"] if pd.notna(row["inflation_multiplier"]) else None,
            row["total_revenue_usd_millions"] if pd.notna(row["total_revenue_usd_millions"]) else None,
            row["gross_margin_pct"] if pd.notna(row["gross_margin_pct"]) else None,
            row["net_income_usd_millions"] if pd.notna(row["net_income_usd_millions"]) else None,
        ))

    cursor.executemany(insert_query, records)
    conn.commit()
    print(f"\nWritten {cursor.rowcount} records to master_dataset in MySQL")
    cursor.close()


def verify_master_dataset(conn):
    """Read back and print the master dataset for verification."""
    df = pd.read_sql("SELECT * FROM master_dataset ORDER BY release_year", conn)

    print("\nVerification: master_dataset")
    print(f"  {'Year':<8} {'Game':<40} {'Nominal':<12} {'Real (2025)':<14} {'Multiplier'}")
    print(f"  {'-'*80}")
    for _, row in df.iterrows():
        nominal = f"${row['base_price_nominal']}" if pd.notna(row['base_price_nominal']) else "N/A"
        real = f"${row['base_price_real']}" if pd.notna(row['base_price_real']) else "N/A"
        multiplier = f"{row['inflation_multiplier']}x" if pd.notna(row['inflation_multiplier']) else "N/A"
        print(f"  {int(row['release_year']):<8} {row['game_title']:<40} {nominal:<12} {real:<14} {multiplier}")

    return df


def run():
    prices, cpi, financials = load_raw_data()
    prices = adjust_for_inflation(prices, cpi)
    master = merge_with_financials(prices, financials)

    conn = get_connection()
    write_master_dataset(master, conn)
    verify_master_dataset(conn)
    conn.close()

    print("\nPhase 2 complete. Master dataset ready for modelling.")


if __name__ == "__main__":
    run()
