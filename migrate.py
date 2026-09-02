import gspread
import json
from google.oauth2.service_account import Credentials
from supabase import create_client
from datetime import datetime
import re

# --- connections ---
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
    return "" if v == "nan" or v == "None" else v

# --- migrate containers ---
print("Migrating containers...")
sheet = gc.open("Brodiaea Operations").worksheet("Inbound")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

batch = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    container = clean(r.get("CONTAINER", ""))
    if not container:
        continue
    batch.append({
        "arrival_date": parse_date(r.get("Arrival date", "")),
        "container": container,
        "account": clean(r.get("ACCOUNT", "")),
        "trucking_company": clean(r.get("TRUCKING COMPANY", "")),
        "container_status": clean(r.get("CONTAINER STATUS", "")),
        "dock_door": clean(r.get("DOCK DOOR", "")),
        "empty": to_bool(r.get("EMPTY", "")),
        "empty_timestamp": parse_date(r.get("Empty TImeStamp", "")),
        "empty_report_sent": to_bool(r.get("EMPTY REPORT SENT", "")),
        "received": to_bool(r.get("RECEIVED", "")),
        "picked_up": to_bool(r.get("PICKED UP", "")),
        "warehouse": clean(r.get("WAREHOUSE", "")),
        "sent_documents": to_bool(r.get("SENT DOCUMENTS", "")),
        "sku_count": to_int(r.get("SKU Count", 0)),
        "carton_count": to_int(r.get("Carton Count", 0)),
        "billed": to_bool(r.get("Billed?", "")),
    })

if batch:
    supabase.table("containers").insert(batch).execute()
    print(f"  inserted {len(batch)} containers")

# --- migrate dock status ---
print("Migrating dock status...")
sheet = gc.open("Brodiaea Operations").worksheet("Dock_Status")
data = sheet.get_all_values()
headers = [h.strip() for h in data[0]]
rows = data[1:]

batch = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    door = clean(r.get("Door", ""))
    if not door:
        continue
    batch.append({
        "door": door,
        "status": clean(r.get("Status", "Vacant")) or "Vacant",
        "container_trailer": clean(r.get("Container #/Trailer", "")),
        "unloading_empty": clean(r.get("Unloading/Empty", "")),
        "carrier": clean(r.get("Carrier", "")),
        "customer": clean(r.get("CUSTOMER", "")),
        "delivery_time": clean(r.get("Delivery Time", "")),
        "notes": clean(r.get("Notes", "")),
    })

if batch:
    supabase.table("dock_status").insert(batch).execute()
    print(f"  inserted {len(batch)} dock doors")

# --- migrate outbound MAD ---
print("Migrating outbound MAD...")
sheet = gc.open("Brodiaea Operations").worksheet("Outbound-MAD 2026")
data = sheet.get_all_values()
headers = [h.strip() for h in data[1]]
rows = data[2:]

batch = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    account = clean(r.get("ACCOUNT", ""))
    if not account:
        continue
    batch.append({
        "business": "MAD",
        "account": account,
        "carrier": clean(r.get("CARRIER", "")),
        "date": parse_date(r.get("DATE", "")),
        "freight_terms": clean(r.get("FREIGHT TERMS", "")),
        "appt_time": clean(r.get("APPT TIME", "")),
        "consignee": clean(r.get("CONSIGNEE", "")),
        "sales_order": clean(r.get("SALES ORDER", "")),
        "po": clean(r.get("PO", "")),
        "ctn": to_int(r.get("CARTONS", 0)),
        "pallet_total": to_int(r.get("PALLET TOTAL", 0)),
        "ready_pu": to_bool(r.get("READY FOR PU", "")),
        "load_number": clean(r.get("LOAD #", "")),
        "pu": to_bool(r.get("PU", "")),
        "billed": to_bool(r.get("Billed?", "")),
    })

if batch:
    supabase.table("outbound").insert(batch).execute()
    print(f"  inserted {len(batch)} MAD shipments")

# --- migrate outbound Instaship ---
print("Migrating outbound Instaship...")
sheet = gc.open("Brodiaea Operations").worksheet("Outbound-Instaship 2026")
data = sheet.get_all_values()
headers = [h.strip() for h in data[1]]
rows = data[2:]

batch = []
for row in rows:
    r = dict(zip(headers, row + [""] * (len(headers) - len(row))))
    account = clean(r.get("ACCOUNT", ""))
    if not account:
        continue
    batch.append({
        "business": "Instaship",
        "account": account,
        "carrier": clean(r.get("CARRIER", "")),
        "date": parse_date(r.get("DATE", "")),
        "freight_terms": clean(r.get("FREIGHT TERMS", "")),
        "appt_time": "",
        "consignee": clean(r.get("CONSIGNEE", "")),
        "sales_order": clean(r.get("SALES ORDER", "")),
        "po": clean(r.get("PO", "")),
        "ctn": to_int(r.get("CTN", 0)),
        "pallet_total": to_int(r.get("PALLET TOTAL", 0)),
        "ready_pu": to_bool(r.get("READY PU", "")),
        "load_number": clean(r.get("LOAD #", "")),
        "pu": to_bool(r.get("PU", "")),
        "billed": to_bool(r.get("BILLED?", "")),
    })

if batch:
    supabase.table("outbound").insert(batch).execute()
    print(f"  inserted {len(batch)} Instaship shipments")

print("Migration complete!")