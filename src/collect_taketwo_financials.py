"""
collect_taketwo_financials.py
-----------------------------
Loads Take-Two Interactive annual financial data into MySQL.

Data sourced from Macrotrends (macrotrends.net/stocks/charts/TTWO),
which aggregates figures from Take-Two's SEC 10-K annual filings.

Metrics collected:
- Total net revenue (USD millions)
- Gross profit (USD millions)
- Gross margin % (derived: gross profit / revenue * 100)
- Net income (USD millions)

Fiscal year note:
Take-Two's fiscal year ends March 31. The year label used here
matches Macrotrends' convention — FY2025 means the year ending
March 31, 2025. This is noted in the database and accounted for
when aligning with CPI and game release year data.

Why manual data over API?
The SEC EDGAR API stores Take-Two's revenue across multiple
fragmented accounting concepts due to their fiscal year change
in 2017. Reconstructing total revenue programmatically would
require complex logic with high error risk. Using verified
figures from Macrotrends — which cites SEC filings directly —
is more accurate and reproducible for this dataset size.
"""

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


# Annual financials sourced from Macrotrends / Take-Two SEC 10-K filings
# Format: (fiscal_year, revenue_usd_millions, gross_profit_usd_millions, net_income_usd_millions)
# Gross margin % is derived in the load function — not hardcoded
TAKETWO_FINANCIALS = [
    (2012,  826,  297, -109),
    (2013, 1214,  499,  -29),
    (2014, 2351,  936,  321),
    (2015, 1083,  288, -279),
    (2016, 1414,  600,   -8),
    (2017, 1780,  757,   67),
    (2018, 1793,  895,  174),
    (2019, 2668, 1145,  334),
    (2020, 3089, 1547,  404),
    (2021, 3373, 1838,  589),
    (2022, 3505, 1969,  418),
    (2023, 5350, 2285, -1125),
    (2024, 5350, 2242, -3744),
    (2025, 5634, 3062, -4479),
]


def load_taketwo_financials():
    """
    Insert Take-Two financial records into MySQL.
    Gross margin % is calculated here rather than hardcoded
    so it stays consistent with the revenue and gross profit figures.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM taketwo_financials")

    insert_query = """
        INSERT INTO taketwo_financials
            (fiscal_year, total_revenue_usd_millions, gross_margin_pct, net_income_usd_millions)
        VALUES (%s, %s, %s, %s)
    """

    records = []
    for row in TAKETWO_FINANCIALS:
        fiscal_year, revenue, gross_profit, net_income = row
        gross_margin = round((gross_profit / revenue) * 100, 2) if revenue > 0 else None
        records.append((fiscal_year, revenue, gross_margin, net_income))

    cursor.executemany(insert_query, records)
    conn.commit()

    print(f"Loaded {cursor.rowcount} Take-Two financial records into MySQL")

    cursor.execute("""
        SELECT fiscal_year, total_revenue_usd_millions, gross_margin_pct, net_income_usd_millions
        FROM taketwo_financials
        ORDER BY fiscal_year
    """)
    rows = cursor.fetchall()

    print("\nVerification: Records in taketwo_financials")
    print(f"  {'Year':<8} {'Revenue ($M)':<16} {'Gross Margin %':<18} {'Net Income ($M)'}")
    print(f"  {'-'*58}")
    for row in rows:
        revenue = f"${row[1]:,.0f}M"
        margin = f"{row[2]}%" if row[2] else "N/A"
        net_income = f"${row[3]:,.0f}M"
        print(f"  {row[0]:<8} {revenue:<16} {margin:<18} {net_income}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    load_taketwo_financials()
