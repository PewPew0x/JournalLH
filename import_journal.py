import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from hyperliquid.info import Info

# 1) Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds  = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPES)
gc     = gspread.authorize(creds)
sheet  = gc.open_by_key('1UnamfsgIvRiCCUOwGFi9GSmK8tR1zSgiuZBSMvKytoQ').worksheet('Journal')

# 2) Figure out where we left off – skip header row
all_oids = sheet.col_values(23)  # Column W (1-based)
data_oids = all_oids[1:]         # drop header at index 0
if data_oids:
    last_seen_oid = data_oids[-1]
    print(f"Last seen OID from sheet: {last_seen_oid}")
else:
    last_seen_oid = None
    print("No previous fills found in sheet – first run!")

# 3) Pull your fills (newest first)
wallet = '0x7a792EA28D2305c5d964e085F983e0e13Ef8daeE'
fills  = Info().user_fills(wallet)

# 4) Build only the new rows, stop when we hit last_seen_oid
rows = []
cutoff = pd.Timestamp('2025-04-27T00:00:00+08:00')

for f in fills:
    oid = f.get("oid")
    # break if we hit the last one we already logged
    if oid and oid == last_seen_oid:
        print(f"Reached previously-logged fill {oid}, stopping loop.")
        break

    # parse timestamp
    t = pd.to_datetime(f.get("time"), unit='ms', utc=True).tz_convert('Asia/Singapore')
    if t < cutoff:
        continue

    coin = f.get("coin","")
    if "/" in coin or coin.startswith("@"):
        continue

    # robust price lookup
    raw_price = f.get("price", f.get("px"))
    if raw_price is None:
        continue
    price = float(raw_price)

    side   = "Long" if f.get("side")=="buy" else "Short"
    entry  = price
    exit_  = price
    sz     = float(f.get("sz", 0))
    usd_sz = sz * price

    fee    = float(f.get("fee", 0))
    closed = float(f.get("closedPnl", f.get("pnl", 0)))
    gross  = closed + fee
    net    = closed
    outcome= "Win" if net>0 else ("Loss" if net<0 else "BE")

    rows.append([
        t.date().strftime("%Y-%m-%d"),  # A
        t.strftime("%H:%M"),            # B
        coin,                           # C
        "",                             # D
        side,                           # E
        entry,                          # F
        "",                             # G
        "",                             # H
        usd_sz,                         # I
        "",                             # J
        "",                             # K
        exit_,                          # L
        fee,                            # M
        gross,                          # N
        net,                            # O
        "",                             # P
        outcome,                        # Q
        "", "", "", "", "",             # R–V
        oid                             # W
    ])

# 5) Append only if there’s something new
if rows:
    # reverse so oldest-newest
    df = pd.DataFrame(rows[::-1])
    sheet.append_rows(df.values.tolist(), value_input_option='USER_ENTERED')
    print(f"Appended {len(rows)} new fills.")
else:
    print("No new fills since last run.")
