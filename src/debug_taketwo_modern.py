"""
Diagnostic script to inspect Take-Two's modern revenue concept.
Their fiscal year ends March 31 from 2018 onwards.
Run once to diagnose, then delete.
"""

import requests

TAKETWO_CIK = "0000906709"
HEADERS = {"User-Agent": "gtavi-economy-map-portfolio seleteakpotosu@email.com"}

url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{TAKETWO_CIK}.json"
facts = requests.get(url, headers=HEADERS).json()

usgaap = facts["facts"]["us-gaap"]

# Check the modern revenue concept
concept = "RevenueFromContractWithCustomerExcludingAssessedTax"
entries = usgaap[concept]["units"]["USD"]

# Only show full year entries (12 month periods) from 10-K filings
print("Full year 10-K entries for RevenueFromContractWithCustomerExcludingAssessedTax:")
print(f"  {'Form':<8} {'Start':<14} {'End':<14} {'Value (USD)'}")
print(f"  {'-'*55}")
for e in sorted(entries, key=lambda x: x.get("end", "")):
    if e.get("form") != "10-K":
        continue
    start = e.get("start", "")
    end = e.get("end", "")
    # Only full year periods (approximately 12 months)
    if start and end:
        from datetime import datetime
        try:
            delta = datetime.strptime(end, "%Y-%m-%d") - datetime.strptime(start, "%Y-%m-%d")
            if delta.days >= 340:
                print(f"  {e.get('form',''):<8} {start:<14} {end:<14} {e.get('val',0):>16,.0f}")
        except:
            pass
