import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import requests
import zipfile
import io
from datetime import datetime, timedelta, timezone
import os
import json
import traceback

# ==========================================
# 1. GOOGLE SHEETS AUTHENTICATION
# ==========================================

creds_json = os.environ.get('GCP_CREDENTIALS')

if not creds_json:
    raise Exception("CRITICAL: GCP_CREDENTIALS secret missing!")

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

# ==========================================
# 2. GOOGLE SHEET CONFIGURATION
# ==========================================

spreadsheet_id = "1CKkvMXmWana29P4pMdPvo3nmZiC9OzQM1BC8U7BT9pw"

worksheet = client.open_by_key(
    spreadsheet_id
).worksheet("Top 250 Stocks")

# ==========================================
# 3. NSE BHAVCOPY FETCHER
# ==========================================

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = (
        "https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": "https://www.nseindia.com/"
    }

    try:

        # Create Session
        session = requests.Session()

        # Fetch ZIP
        response = session.get(
            url,
            headers=headers,
            timeout=30
        )

        # HTTP Check
        if response.status_code != 200:

            print(
                f"HTTP Error "
                f"{response.status_code} "
                f"for {date_str}"
            )

            return None

        # ==========================================
        # OPEN ZIP FILE
        # ==========================================

        with zipfile.ZipFile(
            io.BytesIO(response.content)
        ) as z:

            csv_filename = z.namelist()[0]

            with z.open(csv_filename) as f:

                df = pd.read_csv(f)

        # ==========================================
        # CLEAN COLUMN NAMES
        # ==========================================

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        # ==========================================
        # DETECT REQUIRED COLUMNS
        # ==========================================

        sym_col = next(
            (
                c for c in [
                    'TckrSymb',
                    'SYMBOL'
                ]
                if c in df.columns
            ),
            None
        )

        close_col = next(
            (
                c for c in [
                    'ClsPric',
                    'CLOSE'
                ]
                if c in df.columns
            ),
            None
        )

        series_col = next(
            (
                c for c in [
                    'SctySrs',
                    'SERIES'
                ]
                if c in df.columns
            ),
            None
        )

        turnover_col = next(
            (
                c for c in [
                    'TtlTrfVal',
                    'TtlTrdVal',
                    'TURNOVER_LACS',
                    'TURNOVER'
                ]
                if c in df.columns
            ),
            None
        )

        # ==========================================
        # VALIDATE COLUMNS
        # ==========================================

        if not all([
            sym_col,
            close_col,
            turnover_col
        ]):

            print("Required columns missing!")
            print(df.columns.tolist())

            return None

        # ==========================================
        # KEEP ONLY EQ SERIES
        # ==========================================

        if series_col:

            df = df[
                df[series_col]
                .astype(str)
                .str.strip()
                == 'EQ'
            ]

        # ==========================================
        # REMOVE ETFs / BEES / GOLD
        # ==========================================

        filter_keywords = (
            'BEES|ETF|GOLD|LIQUID'
        )

        df = df[
            ~df[sym_col]
            .astype(str)
            .str.contains(
                filter_keywords,
                case=False,
                na=False
            )
        ]

        # ==========================================
        # CLEAN TURNOVER COLUMN
        # ==========================================

        df[turnover_col] = pd.to_numeric(
            df[turnover_col],
            errors='coerce'
        )

        df = df.dropna(
            subset=[turnover_col]
        )

        # ==========================================
        # SORT BY TURNOVER
        # ==========================================

        df_top = (
            df
            .sort_values(
                by=turnover_col,
                ascending=False
            )
            .head(250)
        )

        # ==========================================
        # RETURN VALUES
        # ==========================================

        return df_top[
            [
                sym_col,
                turnover_col,
                close_col
            ]
        ].values.tolist()

    # ==========================================
    # ZIP FILE ERROR
    # ==========================================

    except zipfile.BadZipFile:

        print(
            f"Bad ZIP file for {date_str}"
        )

        return None

    # ==========================================
    # GENERAL ERROR
    # ==========================================

    except Exception as e:

        print(
            f"Fetch Error for "
            f"{date_str}: {str(e)}"
        )

        traceback.print_exc()

        return None

# ==========================================
# 4. EXECUTION LOGIC
# ==========================================

date = datetime.now()

data_to_insert = None

fetched_date_str = ""

for i in range(7):

    test_date = date - timedelta(days=i)

    # Skip Saturday and Sunday
    if test_date.weekday() >= 5:
        continue

    print(
        f"Trying "
        f"{test_date.strftime('%d-%b-%Y')}"
    )

    data_to_insert = fetch_bhavcopy_for_date(
        test_date
    )

    if data_to_insert:

        fetched_date_str = (
            test_date.strftime('%d-%b-%Y')
        )

        break

# ==========================================
# 5. UPDATE GOOGLE SHEET
# ==========================================

if data_to_insert:

    try:

        # Clear old data
        worksheet.batch_clear(
            ['A2:C1000']
        )

        # Insert new data
        worksheet.update(
            range_name='A2',
            values=data_to_insert
        )

        # IST Timezone
        ist = timezone(
            timedelta(hours=5, minutes=30)
        )

        ist_now = datetime.now(ist).strftime(
            '%d-%b-%Y %H:%M'
        )

        # Status Message
        status_msg = (
            f"Data Date: {fetched_date_str} | "
            f"Last Update: {ist_now} IST"
        )

        # Update Status Cell
        worksheet.update(
            range_name='K2',
            values=[[status_msg]]
        )

        print(
            f"SUCCESS: "
            f"Top 250 Stocks Updated "
            f"for {fetched_date_str}"
        )

    except Exception as e:

        print(
            f"Google Sheet Error: "
            f"{str(e)}"
        )

        traceback.print_exc()

# ==========================================
# 6. FAILURE MESSAGE
# ==========================================

else:

    print(
        "FAILED"
    )

