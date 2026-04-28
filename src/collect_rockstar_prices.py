"""
collect_rockstar_prices.py
--------------------------
Loads curated historical Rockstar Games pricing data into MySQL.

Data sourced from:
- Steam store historical records (SteamSpy / VGInsights)
- Wikipedia game release pages
- Archived Rockstar Newswire announcements

Why hardcoded? There is no reliable public API for historical game prices.
For a small, verifiable dataset like this, explicit sourcing is more
defensible and reproducible than fragile web scraping.
"""

import mysql.connector
import os
from dotenv import load_dotenv

# Load database credentials from .env file
# This keeps passwords out of the codebase entirely
load_dotenv()

# ─── DATABASE CONNECTION ───────────────────────────────────────────────────────
def get_connection():
    """Create and return a MySQL database connection."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ─── DATA ─────────────────────────────────────────────────────────────────────
# Each record: (game_title, release_year, platform, base_price_usd, premium_price_usd, publisher)
# NULL premium price = no deluxe edition existed at launch
ROCKSTAR_PRICES = [
    ("Grand Theft Auto IV",         2008, "PS3/Xbox 360/PC", 59.99, None,  "Rockstar Games"),
    ("Red Dead Redemption",         2010, "PS3/Xbox 360",    59.99, None,  "Rockstar Games"),
    ("Grand Theft Auto V",          2013, "PS3/Xbox 360",    59.99, 79.99, "Rockstar Games"),
    ("Grand Theft Auto V (PC)",     2015, "PC",              59.99, 79.99, "Rockstar Games"),
    ("Red Dead Redemption 2",       2018, "PS4/Xbox One",    59.99, 99.99, "Rockstar Games"),
    ("Red Dead Redemption 2 (PC)",  2019, "PC",              59.99, 99.99, "Rockstar Games"),
    ("Grand Theft Auto V (Next-Gen)",2022,"PS5/Xbox Series", 39.99, None,  "Rockstar Games"),
]

# ─── LOAD FUNCTION ────────────────────────────────────────────────────────────
def load_rockstar_prices():
    """
    Insert Rockstar pricing records into MySQL.
    Uses INSERT IGNORE so re-running the script never creates duplicates.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Clear existing data before reloading
    # This makes the script idempotent — safe to run multiple times
    cursor.execute("DELETE FROM rockstar_prices")

    insert_query = """
        INSERT INTO rockstar_prices 
            (game_title, release_year, platform, base_price_usd, premium_price_usd, publisher)
        VALUES 
            (%s, %s, %s, %s, %s, %s)
    """

    cursor.executemany(insert_query, ROCKSTAR_PRICES)
    conn.commit()

    print(f" Loaded {cursor.rowcount} Rockstar price records into MySQL")

    # Verify by reading back what was inserted
    cursor.execute("SELECT game_title, release_year, base_price_usd FROM rockstar_prices ORDER BY release_year")
    rows = cursor.fetchall()
    print("\n── Verification: Records in rockstar_prices ──")
    for row in rows:
        print(f"  {row[1]}  |  {row[0]:<40} |  ${row[2]}")

    cursor.close()
    conn.close()

# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    load_rockstar_prices()
