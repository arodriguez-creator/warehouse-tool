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

supabase.auth.sign_in_with_password({
    "email": "app@brodiaea.internal",
    "password": "InstashiP2026!!!"
})

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

PLACEHOLDER_SO = {'--', '---', "Multiple SO's", "multiple so's", ''}

# --- sync containers ---
print("Syncing containers...")
sheet = gc.open("Brodiaea Operations").worksheet("Inbound")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

existing_keys = set()
offset = 0
while True:
    batch = supabase.table("containers").select("container, arrival_date")\
        .range(offset, offset + 999)\
        .execute()
    for r in batch.data:
        if r["arrival_date"]:
            existing_keys.add((r["container"], r["arrival_date"]))
    if len(batch.data) < 1000:
        break
    offset += 1000
print(f"  loaded {len(existing_keys)} existing container keys")

new_rows = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    container = clean(r.get("CONTAINER", ""))
    if not container or container.strip() == '':
        continue
    arrival = parse_date(r.get("Arrival date", ""))
    if not arrival:
        continue
    if (container, arrival) in existing_keys:
        continue
    new_rows.append({
        "arrival_date": arrival,
        "container": container,
        "account": clean(r.get("ACCOUNT", "")),
        "trucking_company": clean(r.get("TRUCKING COMPANY", "")),
        "container_status": clean(r.get("CONTAINER STATUS", "")),
        "dock_door": clean(r.get("DOCK DOOR", "")),
        "empty": to_bool(r.get("EMPTY", "")),
        "empty_timestamp": parse_date(r.get("Empty TImeStamp", "")),
        "received": to_bool(r.get("RECEIVED", "")),
        "picked_up": to_bool(r.get("PICKED UP", "")),
        "warehouse": clean(r.get("WAREHOUSE", "")),
        "sku_count": to_int(r.get("SKU Count", 0)),
        "carton_count": to_int(r.get("Carton Count", 0)),
        "billed": to_bool(r.get("Billed?", "")),
    })

if new_rows:
    supabase.table("containers").insert(new_rows).execute()
    print(f"  added {len(new_rows)} new containers")
else:
    print("  no new containers")

# --- sync outbound MAD ---
print("Syncing outbound MAD...")
sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
data = sheet.get_all_values()
headers = [h.strip() for h in data[1]]
rows = data[2:]

existing_keys = set()
offset = 0
while True:
    batch = supabase.table("outbound").select("sales_order, po")\
        .eq("business", "MAD")\
        .range(offset, offset + 999)\
        .execute()
    for r in batch.data:
        existing_keys.add((r["sales_order"], r["po"]))
    if len(batch.data) < 1000:
        break
    offset += 1000
print(f"  loaded {len(existing_keys)} existing MAD keys")

new_rows = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    so = clean(r.get("SALES ORDER", ""))
    account = clean(r.get("ACCOUNT", ""))
    po = clean(r.get("PO", ""))
    if not so or not account or so.lower() in PLACEHOLDER_SO:
        continue
    if (so, po) in existing_keys:
        continue
    new_rows.append({
        "business": "MAD",
        "account": account,
        "carrier": clean(r.get("CARRIER", "")),
        "date": parse_date(r.get("DATE", "")),
        "freight_terms": clean(r.get("FREIGHT TERMS", "")),
        "appt_time": clean(r.get("APPT TIME", "")),
        "consignee": clean(r.get("CONSIGNEE", "")),
        "sales_order": so,
        "po": po,
        "ctn": to_int(r.get("CARTONS", 0)),
        "pallet_total": to_int(r.get("PALLET TOTAL", 0)),
        "load_number": clean(r.get("LOAD #", "")),
        "pu": to_bool(r.get("PU", "")),
        "billed": to_bool(r.get("Billed?", "")),
    })

if new_rows:
    supabase.table("outbound").insert(new_rows).execute()
    print(f"  added {len(new_rows)} new MAD shipments")
else:
    print("  no new MAD shipments")

# --- sync outbound Instaship ---
print("Syncing outbound Instaship...")
sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
data = sheet.get_all_values()
headers = [h.strip() for h in data[1]]
rows = data[2:]

existing_keys = set()
offset = 0
while True:
    batch = supabase.table("outbound").select("sales_order, po")\
        .eq("business", "Instaship")\
        .range(offset, offset + 999)\
        .execute()
    for r in batch.data:
        existing_keys.add((r["sales_order"], r["po"]))
    if len(batch.data) < 1000:
        break
    offset += 1000
print(f"  loaded {len(existing_keys)} existing Instaship keys")

new_rows = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    so = clean(r.get("SALES ORDER", ""))
    account = clean(r.get("ACCOUNT", ""))
    po = clean(r.get("PO", ""))
    if not so or not account or so.lower() in PLACEHOLDER_SO:
        continue
    if (so, po) in existing_keys:
        continue
    new_rows.append({
        "business": "Instaship",
        "account": account,
        "carrier": clean(r.get("CARRIER", "")),
        "date": parse_date(r.get("DATE", "")),
        "freight_terms": clean(r.get("FREIGHT TERMS", "")),
        "appt_time": "",
        "consignee": clean(r.get("CONSIGNEE", "")),
        "sales_order": so,
        "po": po,
        "ctn": to_int(r.get("CTN", 0)),
        "pallet_total": to_int(r.get("PALLET TOTAL", 0)),
        "load_number": clean(r.get("LOAD #", "")),
        "pu": to_bool(r.get("PU", "")),
        "billed": to_bool(r.get("BILLED?", "")),
    })

if new_rows:
    supabase.table("outbound").insert(new_rows).execute()
    print(f"  added {len(new_rows)} new Instaship shipments")
else:
    print("  no new Instaship shipments")

# --- sync amazon pickups ---
print("Syncing Amazon pickups...")
sheet = gc.open("SAKAR Amazon Pick ups").worksheet("PICK UPS 26'")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

existing_keys = set()
offset = 0
while True:
    batch = supabase.table("amazon_pickups").select("sales_order, arn")\
        .range(offset, offset + 999)\
        .execute()
    for r in batch.data:
        existing_keys.add((r["sales_order"], r["arn"]))
    if len(batch.data) < 1000:
        break
    offset += 1000
print(f"  loaded {len(existing_keys)} existing Amazon keys")

new_rows = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    so = clean(r.get("Sales order", ""))
    arn = clean(r.get("ARN#", ""))
    if not so or so.lower() in PLACEHOLDER_SO:
        continue
    if (so, arn) in existing_keys:
        continue
    new_rows.append({
        "sales_order": so,
        "arn": arn,
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

if new_rows:
    supabase.table("amazon_pickups").insert(new_rows).execute()
    print(f"  added {len(new_rows)} new Amazon pickups")
else:
    print("  no new Amazon pickups")

print("\nSync complete!")
