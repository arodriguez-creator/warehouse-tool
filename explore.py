import pandas as pd

df = pd.read_excel("rates.xlsx")

print("=== columns ===")
print(df.columns.tolist())

print("\n=== first few rows ===")
print(df.head())

print("\n=== uph stats ===")
print(df["UPH"].describe())