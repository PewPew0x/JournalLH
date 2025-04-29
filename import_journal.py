import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from hyperliquid.info import Info

# 1) Google Sheets setup
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds  = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', SCOPES)
gc     = gspread.authorize(creds)
sheet  = gc.open_by_key('1UnamfsgIvRiCCUOwGFi9GSmK8tR1zSgiuZBSMvKytoQ').worksheet('Journal')

# 2) Pull your fills
wallet = '0x7a792EA28D2305c5d964e085F983e0e13Ef8daeE'
fills  = Info().user_fills(wallet)

# 3) Transform into rows
rows = []
cutoff = pd.Timestamp('2025-04-27T00:00:00+08:00')
for f in fills:
    # normalize timestamp
    t = pd.to_datetime(f.get("time"), unit='ms', utc=True).tz_convert('Asia/Singapore')
    if t < cutoff: 
        continue
    # skip non-perps
    coin = f.get("coin","")
    if "/" in coin or coin.startswith("@"):
        continue

    # 3a) robust price extraction
    raw_price = f.get("price", f.get("px"))
    if raw_price is None:
        # if neither key exists, skip this fill
        continue
    price = float(raw_price)

    # 3b) side, entry & exit
    side  = "Long" if f.get("side")=="buy" else "Short"
    entry = price
    exit_ = price

    # 3c) size & PnL
    sz    = float(f.get("sz", 0))
    usd_sz= sz * price
    fee   = float(f.get("fee", 0))
    closed= float(f.get("closedPnl", f.get("pnl", 0)))
    gross = closed + fee
    net   = closed
    outcome = "Win" if net>0 else ("Loss" if net<0 else "BE")

    rows.append([
        t.date().strftime("%Y-%m-%d"),    # A: Date
        t.strftime("%H:%M"),              # B: Time
        coin,                             # C: Asset
        "",                               # D: SetupPattern
        side,                             # E: Side (Long/Short)
        entry,                            # F: EntryPrice
        "",                               # G: StopPrice (manual)
        "",                               # H: TargetPrice (manual)
        usd_sz,                           # I: PositionSizeAmount (USD)
        "",                               # J: RiskPerTrade_USD (sheet formula)
        "",                               # K: R_Ratio (sheet formula)
        exit_,                            # L: ExitPrice
        fee,                              # M: Fee_USD
        gross,                            # N: GrossPnL_USD
        net,                              # O: NetPnL_USD
        "",                               # P: R_Multiple (sheet formula)
        outcome,                          # Q: Outcome
        "", "", "", "", "",               # R–V: manual fields
        f.get("oid","")                   # W: FillOID
    ])

# 4) Append into the sheet (oldest first)
df = pd.DataFrame(rows[::-1])
sheet.append_rows(df.values.tolist(), value_input_option='USER_ENTERED')
