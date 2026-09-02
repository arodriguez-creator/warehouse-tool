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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqd2x2Zmx3bmNsdHZpY29kb3FqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4ODMwNDA2NSwiZXhwIjoyMTAzODgwMDY1fQ.w0qhh3nrmF06NxCzubVuHwXaCce56rAz6Enn_2iCdVA"
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

print("Migrating Amazon pickups...")
sheet = gc.open("SAKAR Amazon Pick ups").worksheet("PICK UPS 26'")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

batch = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    so = clean(r.get("Sales order", ""))
    if not so:
        continue
    batch.append({
        "sales_order": so,
        "arn": clean(r.get("ARN#", "")),
        "carrier": clean(r.get("CARRIER", "")),
        "pallets": to_int(r.get("Pallets", 0)),
        "picked": to_bool(r.get("Picked", "")),
        "ready": to_bool(r.get("Ready", "")),
        "bol_printed": to_bool(r.get("Printed BOL & pallet labels", "")),
        "pickup_date": parse_date(r.get("Pick up date", "")),
        "picked_up": to_bool(r.get("Picked up", "")),
        "cartons": to_int(r.get("Cartons", 0)),
        "notes": clean(r.get("Notes (reason for trouble)", "")),
    })

if batch:
    supabase.table("amazon_pickups").insert(batch).execute()
    print(f"  inserted {len(batch)} Amazon pickup rows")

print("Done!")