import gspread
import pandas as pd

gc = gspread.service_account(filename="credentials.json")

sheet = gc.open("Brodiaea Operations").worksheet("Inbound")

df = pd.DataFrame(sheet.get_all_values())
df.columns = df.iloc[0]
df = df[1:].reset_index(drop=True)

print(df.columns.tolist())
print(df.head())