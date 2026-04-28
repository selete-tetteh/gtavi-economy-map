"""
collect_cpi_data.py
-------------------
Fetches annual US CPI (Consumer Price Index) data from the
Bureau of Labor Statistics (BLS) public API and loads it into MySQL.

Series ID: CUUR0000SA0
- CUUR = CPI for All Urban Consumers
- 0000 = US City Average
- SA0  = All items, not seasonally adjusted

Why this series? It is the standard measure used by economists
to calculate inflation-adjusted (real) prices over time.

BLS API documentation: https://www.bls.gov/developers/api_python.htm
No API key required for requests covering up to 10 years.
We make two requests to cover 2000-2026.
"""

import requests
import mysql.connector
import os
import json
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


def fetch_cpi_from_bls(start_year, end_year):
    """
    Fetch annual CPI data from the BLS public API.
    The API returns monthly values — we average them to get an annual figure.
    This is standard practice for annual inflation comparisons.
    """
    url = "https://api.bls.gov/publicAPI/v1/timeseries/data/"

    payload = {
        "seriesid": ["CUUR0000SA0"],
        "startyear": str(start_year),
        "endyear": str(end_year)
    }

    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()

    if data["status"] != "REQUEST_SUCCEEDED":
        raise Exception(f"BLS API request failed: {data['message']}")

    return data["Results"]["series"][0]["data"]


def parse_annual_averages(raw_data):
    """
    Convert monthly BLS data into annual averages.

    The BLS returns one value per month. We group by year
    and average the 12 monthly values to get a single annual CPI.
    Annual averages are more stable and appropriate for
    year-over-year price comparisons.
    """
    from collections import defaultdict

    monthly = defaultdict(list)

    for record in raw_data:
        year = int(record["year"])
        if record["period"] == "M13":
            continue
        if record["value"] == "-":
            continue
        monthly[year].append(float(record["value"]))

    annual = {}
    for year, values in monthly.items():
        if len(values) >= 6:
            annual[year] = round(sum(values) / len(values), 3)

    return annual


def load_cpi_data():
    """
    Fetch CPI data for 2000-2026 and load into MySQL.
    Two API requests needed because the free BLS API
    has a 10-year limit per request.
    """
    print("Fetching CPI data from BLS API...")

    raw_2000_2009 = fetch_cpi_from_bls(2000, 2009)
    raw_2010_2019 = fetch_cpi_from_bls(2010, 2019)
    raw_2020_2026 = fetch_cpi_from_bls(2020, 2026)

    all_raw = raw_2000_2009 + raw_2010_2019 + raw_2020_2026
    annual_cpi = parse_annual_averages(all_raw)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM cpi_data")

    insert_query = """
        INSERT INTO cpi_data (year, annual_cpi)
        VALUES (%s, %s)
    """

    records = sorted(annual_cpi.items())
    cursor.executemany(insert_query, records)
    conn.commit()

    print(f"Loaded {cursor.rowcount} annual CPI records into MySQL")

    cursor.execute("SELECT year, annual_cpi FROM cpi_data ORDER BY year")
    rows = cursor.fetchall()
    print("\nVerification: Records in cpi_data")
    print(f"  {'Year':<8} {'Annual CPI'}")
    print(f"  {'-'*20}")
    for row in rows:
        print(f"  {row[0]:<8} {row[1]}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    load_cpi_data()
