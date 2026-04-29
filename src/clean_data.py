"""
clean_data.py
-------------
Pulls raw data from MySQL, applies inflation adjustment,
merges datasets, and writes the master dataset back to MySQL.

Steps:
1. Load game_prices, cpi_data, and taketwo_financials from MySQL
2. Adjust all nominal prices to 2025 dollar terms using CPI data
3. Merge with Take-Two financials by year
4. Write the master dataset to MySQL

Why inflation-adjust?
A game priced at $59.99 in 2007 represents more purchasing power
than $59.99 in 2025. Adjusting all prices to a common base year
(2025) lets the regression model compare real value across time.
Without this step the model sees no meaningful price trend.

Formula: real_price = nominal_price * (CPI_2025 / CPI_release_year)

Why write back to MySQL?
The master dataset is queryable independently of Python.
Anyone with database access can run SQL queries against it
without touching the codebase. SQL is the source of truth.
"""

import pandas as pd
import os
from dotenv import load_dotenv
from urllib.parse import quote_plus
from sqlalchemy import create_engine
import mysql.connector

load_dotenv()


def get_connection():
    """Raw MySQL connection for write operations."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )


def get_engine():
    """SQLAlchemy engine for pandas read operations."""
    password = quote_plus(os.getenv("DB_PASSWORD"))
    return create_engine(
        f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{password}"
        f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
    )


def load_raw_data():
    """Load all three raw tables from MySQL into DataFrames."""
    engine = get_engine()
    prices = pd.read_sql("SELECT * FROM game_prices ORDER BY release_year", engine)
    cpi = pd.read_sql("SELECT year, annual_cpi FROM cpi_data ORDER BY year", engine)
    financials = pd.read_sql("""
        SELECT fiscal_year, total_revenue_usd_millions,
               gross_margin_pct, net_income_usd_millions
        FROM taketwo_financials
        ORDER BY fiscal_year
    """, engine)

    print(f"Loaded {len(prices)} price records")
    print(f"Loaded {len(cpi)} CPI records")
    print(f"Loaded {len(financials)} financial records")

    return prices, cpi, financials


def adjust_for_inflation(prices_df, cpi_df):
    """
    Adjust all nominal prices to 2025 dollar terms.

    The inflation multiplier for each game is:
        CPI_2025 / CPI_release_year

    A multiplier above 1.0 means prices have risen since that year.
    A game from 2007 has a multiplier of ~1.55, meaning $59.99 in
    2007 is equivalent to ~$93 in 2025 purchasing power terms.
    """
    cpi_2025 = cpi_df.loc[cpi_df["year"] == 2025, "annual_cpi"].values[0]
    print(f"\nBase year CPI (2025): {cpi_2025}")

    df = prices_df.merge(
        cpi_df.rename(columns={"year": "release_year", "annual_cpi": "annual_cpi"}),
        on="release_year",
        how="left"
    )

    missing = df[df["annual_cpi"].isna()]["release_year"].unique()
    if len(missing) > 0:
        print(f"Warning: Missing CPI data for years: {missing}")
    else:
        print("CPI data found for all release years")

    df["cpi_2025"] = cpi_2025
    df["inflation_multiplier"] = (cpi_2025 / df["annual_cpi"]).round(4)
    df["base_price_real"] = (df["base_price_usd"] * df["inflation_multiplier"]).round(2)
    df["premium_price_real"] = (df["premium_price_usd"] * df["inflation_multiplier"]).round(2)

    return df


def merge_with_financials(prices_df, financials_df):
    """
    Merge inflation-adjusted prices with Take-Two financial data.
    Matched on calendar year. Take-Two's fiscal year offset is
    noted in the README methodology section.
    """
    return prices_df.merge(
        financials_df.rename(columns={"fiscal_year": "release_year"}),
        on="release_year",
        how="left"
    )


def write_master_dataset(df):
    """
    Write the cleaned master dataset to MySQL.
    Uses try/finally to guarantee connections close even on error,
    preventing table metadata lock issues from orphaned connections.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM master_dataset")

        insert_query = """
            INSERT INTO master_dataset (
                game_title, publisher, release_year, platform,
                platform_generation, had_premium_edition,
                base_price_nominal, premium_price_nominal,
                base_price_real, premium_price_real,
                annual_cpi, cpi_2025, inflation_multiplier,
                revenue_usd_millions, gross_margin_pct, net_income_usd_millions
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        def val(v):
            return None if pd.isna(v) else v

        records = []
        for _, row in df.iterrows():
            records.append((
                row["game_title"],
                row["publisher"],
                int(row["release_year"]),
                row["platform"],
                int(row["platform_generation"]),
                int(row["had_premium_edition"]),
                val(row["base_price_usd"]),
                val(row["premium_price_usd"]),
                val(row["base_price_real"]),
                val(row["premium_price_real"]),
                val(row["annual_cpi"]),
                val(row["cpi_2025"]),
                val(row["inflation_multiplier"]),
                val(row.get("total_revenue_usd_millions")),
                val(row.get("gross_margin_pct")),
                val(row.get("net_income_usd_millions")),
            ))

        cursor.executemany(insert_query, records)
        conn.commit()
        print(f"\nWritten {cursor.rowcount} records to master_dataset")

    finally:
        cursor.close()
        conn.close()


def run():
    prices, cpi, financials = load_raw_data()
    prices = adjust_for_inflation(prices, cpi)
    master = merge_with_financials(prices, financials)
    write_master_dataset(master)
    print("clean_data.py complete")


if __name__ == "__main__":
    run()
