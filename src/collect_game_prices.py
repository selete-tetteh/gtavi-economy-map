"""
collect_game_prices.py
----------------------
Loads curated historical AAA game pricing data into MySQL.

Data sourced from:
- Steam store historical records (SteamSpy / VGInsights)
- Publisher press releases and archived store pages
- Wikipedia game release pages

Why hardcoded rather than scraped?
There is no reliable public API for historical game prices.
For a small, verifiable dataset, explicit sourcing is more
defensible and reproducible than fragile web scraping.
Each price can be traced to a primary source.

Publishers included:
- Activision (Call of Duty series, 2007-2023)
- EA (Battlefield and FIFA/FC series, 2011-2023)
- Nintendo (Switch first-party titles, 2017-2023)
- Rockstar Games (GTA and RDR series, 2008-2019)
- Sony (PlayStation first-party titles, 2017-2023)

Platform generations:
- 1 = PS3 / Xbox 360 era (2007-2013)
- 2 = PS4 / Xbox One era (2014-2019)
- 3 = PS5 / Xbox Series era (2020-present)
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


GAME_PRICES = [
    # Rockstar Games
    ("Grand Theft Auto IV",              "Rockstar Games", 2008, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Red Dead Redemption",              "Rockstar Games", 2010, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Grand Theft Auto V",               "Rockstar Games", 2013, "PS3/Xbox 360",    1, 59.99, 79.99, 1),
    ("Grand Theft Auto V (PC)",          "Rockstar Games", 2015, "PC",              2, 59.99, 79.99, 1),
    ("Red Dead Redemption 2",            "Rockstar Games", 2018, "PS4/Xbox One",    2, 59.99, 99.99, 1),
    ("Red Dead Redemption 2 (PC)",       "Rockstar Games", 2019, "PC",              2, 59.99, 99.99, 1),

    # Activision — Call of Duty
    ("Call of Duty 4: Modern Warfare",   "Activision",     2007, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Call of Duty: Modern Warfare 2",   "Activision",     2009, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Call of Duty: Black Ops",          "Activision",     2010, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Call of Duty: Modern Warfare 3",   "Activision",     2011, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Call of Duty: Black Ops II",       "Activision",     2012, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Call of Duty: Ghosts",             "Activision",     2013, "PS3/Xbox 360",    1, 59.99, 79.99, 1),
    ("Call of Duty: Advanced Warfare",   "Activision",     2014, "PS4/Xbox One",    2, 59.99, 79.99, 1),
    ("Call of Duty: Black Ops III",      "Activision",     2015, "PS4/Xbox One",    2, 59.99, 99.99, 1),
    ("Call of Duty: Infinite Warfare",   "Activision",     2016, "PS4/Xbox One",    2, 59.99, 79.99, 1),
    ("Call of Duty: WWII",               "Activision",     2017, "PS4/Xbox One",    2, 59.99, 99.99, 1),
    ("Call of Duty: Black Ops 4",        "Activision",     2018, "PS4/Xbox One",    2, 59.99, 99.99, 1),
    ("Call of Duty: Modern Warfare",     "Activision",     2019, "PS4/Xbox One",    2, 59.99, 99.99, 1),
    ("Call of Duty: Black Ops Cold War", "Activision",     2020, "PS5/Xbox Series", 3, 69.99, 99.99, 1),
    ("Call of Duty: Modern Warfare II",  "Activision",     2022, "PS5/Xbox Series", 3, 69.99, 99.99, 1),
    ("Call of Duty: Modern Warfare III", "Activision",     2023, "PS5/Xbox Series", 3, 69.99, 99.99, 1),

    # EA
    ("Battlefield 3",                    "EA",             2011, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Battlefield 4",                    "EA",             2013, "PS3/Xbox 360",    1, 59.99, 79.99, 1),
    ("FIFA 14",                          "EA",             2013, "PS3/Xbox 360",    1, 59.99, None,  0),
    ("Battlefield 1",                    "EA",             2016, "PS4/Xbox One",    2, 59.99, 79.99, 1),
    ("FIFA 18",                          "EA",             2017, "PS4/Xbox One",    2, 59.99, 79.99, 1),
    ("Battlefield V",                    "EA",             2018, "PS4/Xbox One",    2, 59.99, 79.99, 1),
    ("FIFA 22",                          "EA",             2021, "PS5/Xbox Series", 3, 69.99, 99.99, 1),
    ("Battlefield 2042",                 "EA",             2021, "PS5/Xbox Series", 3, 69.99, 99.99, 1),
    ("EA Sports FC 24",                  "EA",             2023, "PS5/Xbox Series", 3, 69.99, 99.99, 1),

    # Sony First-Party
    ("God of War",                       "Sony",           2018, "PS4",             2, 59.99, None,  0),
    ("Marvel's Spider-Man",              "Sony",           2018, "PS4",             2, 59.99, 79.99, 1),
    ("Horizon Zero Dawn",                "Sony",           2017, "PS4",             2, 59.99, 79.99, 1),
    ("The Last of Us Part II",           "Sony",           2020, "PS4",             2, 59.99, 79.99, 1),
    ("Demon's Souls",                    "Sony",           2020, "PS5",             3, 69.99, None,  0),
    ("God of War Ragnarok",              "Sony",           2022, "PS5",             3, 69.99, 79.99, 1),
    ("Marvel's Spider-Man 2",            "Sony",           2023, "PS5",             3, 69.99, 79.99, 1),
    ("Horizon Forbidden West",           "Sony",           2022, "PS5",             3, 69.99, 79.99, 1),

    # Nintendo
    ("The Legend of Zelda: Breath of the Wild", "Nintendo", 2017, "Switch",         2, 59.99, None,  0),
    ("Super Mario Odyssey",              "Nintendo",       2017, "Switch",          2, 59.99, None,  0),
    ("Pokemon Scarlet/Violet",           "Nintendo",       2022, "Switch",          3, 59.99, None,  0),
    ("The Legend of Zelda: Tears of the Kingdom", "Nintendo", 2023, "Switch",       3, 69.99, None,  0),
]


def load_game_prices():
    """
    Insert all game price records into MySQL.
    Clears existing data first so the script is safe to rerun.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("DELETE FROM game_prices")

        insert_query = """
            INSERT INTO game_prices
                (game_title, publisher, release_year, platform,
                 platform_generation, base_price_usd, premium_price_usd, had_premium_edition)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """

        cursor.executemany(insert_query, GAME_PRICES)
        conn.commit()

        print(f"Loaded {cursor.rowcount} records into game_prices")

        cursor.execute("""
            SELECT publisher, COUNT(*) as count
            FROM game_prices
            GROUP BY publisher
            ORDER BY publisher
        """)
        print("\nRecords per publisher:")
        for row in cursor.fetchall():
            print(f"  {row[0]:<20} {row[1]}")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    load_game_prices()
