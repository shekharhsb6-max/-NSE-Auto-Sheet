import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta
import os
import json

# ==========================================================
# 1. Google Credentials
# ==========================================================

creds_json = os.environ.get("GCP_CREDENTIALS")
creds_dict = json.loads(creds_json)

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict,
    scope
)

client = gspread.authorize(creds)

spreadsheet_id = "1CKkvMXmWana29P4pMdPvo3nmZiC9OzQM1BC8U7BT9pw"

spreadsheet = client.open_by_key(spreadsheet_id)

worksheet = spreadsheet.worksheet("Top 250 Stocks")


# ==========================================================
# 2. Fetch NSE Bhav Copy
# ==========================================================

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = (
        f"https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

    print("\nDownloading:")
    print(url)

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(url, headers=headers, timeout=20)

        if response.status_code != 200:
            print("HTTP Status:", response.status_code)
            return None

        with zipfile.ZipFile(io.BytesIO(response.content)) as z:

            csv_name = z.namelist()[0]

            with z.open(csv_name) as f:
                df = pd.read_csv(f)

        print("\nColumns Found:")
        print(df.columns.tolist())

        # --------------------------------------------------

        sym_col = "TckrSymb" if "TckrSymb" in df.columns else "SYMBOL"

        if "PrvsClsgPric" in df.columns:
            close_col = "PrvsClsgPric"
        elif "ClsPric" in df.columns:
            close_col = "ClsPric"
        else:
            close_col = "CLOSE"

        print("\nUsing Close Column:", close_col)

        series_col = "SctySrs" if "SctySrs" in df.columns else "SERIES"

        volume_candidates = [
            "TtlTradgVol",
            "TtlTrdQty",
            "TotTrdQty",
            "TOTTRDQTY"
        ]

        vol_col = None

        for c in volume_candidates:
            if c in df.columns:
                vol_col = c
                break

        if vol_col is None:
            raise Exception("Volume column not found")

        # --------------------------------------------------

        if series_col in df.columns:
            df = df[df[series_col].astype(str).str.strip() == "EQ"]

        filter_keywords = "BEES|ETF|GOLD|LIQUID|CASE|SILVER|LIQ"

        df = df[
            ~df[sym_col].astype(str).str.contains(
                filter_keywords,
                case=False,
                na=False
            )
        ]

        # --------------------------------------------------
        # DEBUG
        # --------------------------------------------------

        ultra = df[df[sym_col] == "ULTRACEMCO"]

        if not ultra.empty:

            print("\nULTRACEMCO")

            cols = [
                c for c in [
                    sym_col,
                    "PrvsClsgPric",
                    "ClsPric",
                    "LastPric",
                    vol_col
                ]
                if c in ultra.columns
            ]

            print(ultra[cols].to_string(index=False))

        # --------------------------------------------------

        df_top = (
            df
            .sort_values(by=vol_col, ascending=False)
            .head(250)
        )

        return df_top[
            [sym_col, vol_col, close_col]
        ].values.tolist()

    except Exception as e:

        print("ERROR:", e)

        return None


# ==========================================================
# 3. Find Latest Trading Day
# ==========================================================

today = datetime.now()

data_to_insert = None

fetched_date = ""

for i in range(5):

    d = today - timedelta(days=i)

    if d.weekday() >= 5:
        continue

    print("\nTrying:", d.strftime("%d-%b-%Y"))

    data_to_insert = fetch_bhavcopy_for_date(d)

    if data_to_insert:

        fetched_date = d.strftime("%d-%b-%Y")

        break


# ==========================================================
# 4. Update Google Sheet
# ==========================================================

if data_to_insert:

    worksheet.batch_clear(["A2:C251"])

    worksheet.update(
        range_name="A2",
        values=data_to_insert
    )

    ist = (
        datetime.utcnow()
        + timedelta(hours=5, minutes=30)
    ).strftime("%d-%b %H:%M")

    status_msg = (
        f"Data Date: {fetched_date} | "
        f"Last Update: {ist} (IST)"
    )

    worksheet.update(
        range_name="N1",
        values=[[status_msg]]
    )

    print("\nSUCCESS")
    print("Spreadsheet :", spreadsheet.title)
    print("Rows Updated :", len(data_to_insert))

else:

    print("\nFAILED")
