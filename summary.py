import pandas as pd

df = pd.read_excel("rates.xlsx")

# use median instead of mean — much harder to skew
median_uph = df["UPH"].median()
mad = (df["UPH"] - median_uph).abs().median()  # median absolute deviation

# flag anyone more than 3x the typical spread above the median
df["flag"] = df["UPH"] > (median_uph + 3 * mad)

print("=== shift summary ===")
print(f"Team members: {len(df)}")
print(f"Total units picked: {df['Total Units'].sum()}")
print(f"Total lines: {df['Total Lines'].sum()}")
print(f"Total errors: {df['Total Errors'].sum()}")

print("\n=== pick rates ===")
print(df[["Team Member", "Hours", "UPH", "Total Units", "flag"]].to_string(index=False))

print("\n=== flagged for review ===")
flagged = df[df["flag"] == True]
for _, row in flagged.iterrows():
    print(f"  {row['Team Member']} — UPH of {row['UPH']:,.0f} vs median of {median_uph:,.0f}")