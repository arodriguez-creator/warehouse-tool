import gspread
import json
from google.oauth2.service_account import Credentials
from supabase import create_client
from datetime import datetime

creds_dict = json.load(open("credentials.json"))
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
gc = gspread.authorize(creds)

SUPABASE_URL = "https://rjwlvflwncltvicodoqj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqd2x2Zmx3bmNsdHZpY29kb3FqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgzMDQwNjUsImV4cCI6MjEwMzg4MDA2NX0.8D3ufML8f8nOTnPqlqkmRuZgLsRUHNk0YuU0eQZm3Ic"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def parse_date(val):
    if not val or str(val).strip() == "":
        return None
    for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%-m/%-d/%Y", "%-m/%-d/%y"]:
        try:
            return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
        except:
            pass
    return None

def to_bool(val):
    return str(val).strip().upper() == "TRUE"

def to_int(val):
    try:
        return int(str(val).replace(",", "").strip())
    except:
        return 0

def clean(val):
    v = str(val).strip()
    return "" if v in ["nan", "None", ""] else v

print("Reading Amazon pickups sheet...")
sheet = gc.open("SAKAR Amazon Pick ups").worksheet("PICK UPS 26'")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

print(f"Headers: {headers[:11]}")

updated = 0
skipped = 0

for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    so = clean(r.get("Sales order", ""))
    if not so:
        skipped += 1
        continue
    
    pickup_date = parse_date(r.get("Pick up date", ""))
    
    if pickup_date:
        result = supabase.table("amazon_pickups")\
            .update({"pickup_date": pickup_date})\
            .eq("sales_order", so)\
            .execute()
        updated += 1
    else:
        skipped += 1

print(f"Updated: {updated} rows")
print(f"Skipped: {skipped} rows (no date)")
print("Done!")