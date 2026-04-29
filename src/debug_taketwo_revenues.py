"""
Diagnostic script to inspect raw Revenues data from EDGAR.
Shows every entry including form type, date, and value.
Run once to diagnose, then delete.
"""

import requests

TAKETWO_CIK = "0000906709"
HEADERS = {"User-Agent": "gtavi-economy-map-portfolio seleteakpotosu@email.com"}

url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{TAKETWO_CIK}.json"
facts = requests.get(url, headers=HEADERS).json()

entries = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]

print("All entries under Revenues concept:")
print(f"  {'Form':<8} {'Start':<14} {'End':<14} {'Value (USD)'}")
print(f"  {'-'*55}")
for e in sorted(entries, key=lambda x: x.get("end", "")):
    print(f"  {e.get('form',''):<8} {e.get('start',''):<14} {e.get('end',''):<14} {e.get('val',0):,.0f}")
