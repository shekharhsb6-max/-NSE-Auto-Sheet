import gspread
from oauth2client.service_account import ServiceAccountCredentials

import pandas as pd
import requests
import zipfile
import io

from datetime import datetime, timedelta
import os
import json

# =========================================================
# GOOGLE SHEETS AUTH
# =========================================================

creds_json = os.environ.get('GCP_CREDENTIALS')

if not creds_json:

    print("ERROR: GCP_CREDENTIALS missing")
    exit()

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

# =========================================================
# GOOGLE SHEET DETAILS
# =========================================================

spreadsheet_id = "1D3E5lyH2QUq55AzsJqSbJj2tNkmOQht_8xUmt0mdvbk"

worksheet = client.open_by_key(
    spreadsheet_id
).worksheet("RAW_DATA")

# =========================================================
# NSE SESSION
# =========================================================

def get_session():

    session = requests.Session()

    session.headers.update({

        "User-Agent":
        (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),

        "Accept":
        (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),

        "Accept-Language":
        "en-US,en;q=0.9",

        "Referer":
        "https://www.nseindia.com/"
    })

    try:

        session.get(
            "https://www.nseindia.com",
            timeout=10
        )

    except Exception as e:

        print("Session Warmup Error:", e)

    return session

# =========================================================
# FETCH DELIVERY DATA
# =========================================================

def fetch_delivery(date_obj):

    try:

        session = get_session()

        date_str = date_obj.strftime("%d%m%Y")

        url = (
            "https://archives.nseindia.com/"
            "products/content/"
            f"sec_bhavdata_full_{date_str}.csv"
        )

        print("\nDELIVERY URL:")
        print(url)

        response = session.get(
            url,
            timeout=30
        )

        print(
            "Delivery Status:",
            response.status_code
        )

        if response.status_code != 200:

            return None

        from io import StringIO

        df = pd.read_csv(
            StringIO(response.text)
        )

        # =================================================
        # CLEAN COLUMN NAMES
        # =================================================

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        print("\nDELIVERY COLUMNS:")

        print(df.columns.tolist())

        # =================================================
        # CLEAN STRINGS
        # =================================================

        for col in df.columns:

            if df[col].dtype == object:

                df[col] = (
                    df[col]
                    .astype(str)
                    .str.strip()
                )

        # =================================================
        # REQUIRED COLUMNS
        # =================================================

        required_cols = [
            'SYMBOL',
            'SERIES',
            'DELIV_QTY',
            'DELIV_PER'
        ]

        for col in required_cols:

            if col not in df.columns:

                print(
                    f"Missing Delivery Column: {col}"
                )

                return None

        # =================================================
        # EQ ONLY
        # =================================================

        df = df[
            df['SERIES'] == 'EQ'
        ]

        print(
            "Delivery EQ Rows:",
            len(df)
        )

        # =================================================
        # NUMERIC CONVERSION
        # =================================================

        df['DELIV_QTY'] = pd.to_numeric(
            df['DELIV_QTY'],
            errors='coerce'
        )

        df['DELIV_PER'] = pd.to_numeric(
            df['DELIV_PER'],
            errors='coerce'
        )

        # =================================================
        # FINAL DELIVERY DATAFRAME
        # =================================================

        delivery_df = df[[
            'SYMBOL',
            'DELIV_QTY',
            'DELIV_PER'
        ]].copy()

        delivery_df.columns = [
            'SYMBOL',
            'DELIVERY_QTY',
            'DELIVERY_PERCENT'
        ]

        print(
            "Delivery Final Rows:",
            len(delivery_df)
        )

        return delivery_df

    except Exception as e:

        print("Delivery Error:", str(e))

        return None

# =========================================================
# FETCH BHAVCOPY
# =========================================================

def fetch_bhavcopy(date_obj):

    try:

        session = get_session()

        date_str = date_obj.strftime("%Y%m%d")

        url = (
            "https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
        )

        print("\nBHAVCOPY URL:")
        print(url)

        response = session.get(
            url,
            timeout=30
        )

        print(
            "Bhavcopy Status:",
            response.status_code
        )

        if response.status_code != 200:

            return None

        # =================================================
        # OPEN ZIP
        # =================================================

        with zipfile.ZipFile(
            io.BytesIO(response.content)
        ) as z:

            print(
                "ZIP FILES:",
                z.namelist()
            )

            csv_file = z.namelist()[0]

            with z.open(csv_file) as f:

                df = pd.read_csv(f)

        # =================================================
        # CLEAN COLUMN NAMES
        # =================================================

        df.columns = [
            str(c).strip()
            for c in df.columns
        ]

        print("\nBHAVCOPY COLUMNS:")

        print(df.columns.tolist())

        # =================================================
        # DYNAMIC COLUMN DETECTION
        # =================================================

        symbol_col = None
        series_col = None
        close_col = None
        turnover_col = None
        volume_col = None

        for c in df.columns:

            lc = c.lower()

            if (
                'symbol' in lc
                or 'tckrsymb' in lc
            ):

                symbol_col = c

            elif (
                'series' in lc
                or 'sctysrs' in lc
            ):

                series_col = c

            elif (
                'close' in lc
                or 'clspric' in lc
            ):

                close_col = c

            elif (
                'turnover' in lc
                or 'ttltrfval' in lc
                or 'ttltrdval' in lc
            ):

                turnover_col = c

            elif (
                'volume' in lc
                or 'ttltradgvol' in lc
            ):

                volume_col = c

        print("\nMAPPED COLUMNS:")

        print(
            "SYMBOL:", symbol_col,
            "| SERIES:", series_col,
            "| CLOSE:", close_col,
            "| TURNOVER:", turnover_col,
            "| VOLUME:", volume_col
        )

        # =================================================
        # VALIDATION
        # =================================================

        if not symbol_col:

            return None

        if not close_col:

            return None

        if not turnover_col:

            return None

        # =================================================
        # EQ ONLY
        # =================================================

        if series_col:

            df = df[
                df[series_col]
                .astype(str)
                .str.strip() == 'EQ'
            ]

        print(
            "Rows After EQ Filter:",
            len(df)
        )

        # =================================================
        # NUMERIC CONVERSION
        # =================================================

        df[turnover_col] = pd.to_numeric(
            df[turnover_col],
            errors='coerce'
        )

        df[close_col] = pd.to_numeric(
            df[close_col],
            errors='coerce'
        )

        if volume_col:

            df[volume_col] = pd.to_numeric(
                df[volume_col],
                errors='coerce'
            )

        # =================================================
        # DROP EMPTY ROWS
        # =================================================

        df = df.dropna(
            subset=[
                turnover_col,
                close_col
            ]
        )

        print(
            "Rows After Dropna:",
            len(df)
        )

        if len(df) == 0:

            return None

        # =================================================
        # SORT
        # =================================================

        df = df.sort_values(
            by=turnover_col,
            ascending=False
        )

        # =================================================
        # FETCH DELIVERY DATA
        # =================================================

        delivery_df = fetch_delivery(
            date_obj
        )

        # =================================================
        # MERGE DELIVERY
        # =================================================

        if delivery_df is not None:

            df[symbol_col] = (
                df[symbol_col]
                .astype(str)
                .str.strip()
            )

            delivery_df['SYMBOL'] = (
                delivery_df['SYMBOL']
                .astype(str)
                .str.strip()
            )

            df = df.merge(
                delivery_df,
                left_on=symbol_col,
                right_on='SYMBOL',
                how='left'
            )

            print(
                "Rows After Delivery Merge:",
                len(df)
            )

        # =================================================
        # FINAL DATAFRAME
        # =================================================

        final_df = pd.DataFrame()

        final_df['SYMBOL'] = df[symbol_col]

        final_df['TURNOVER'] = df[turnover_col]

        final_df['CLOSE_PRICE'] = df[close_col]

        if volume_col:

            final_df['VOLUME'] = df[volume_col]

        else:

            final_df['VOLUME'] = ""

        if 'DELIVERY_QTY' in df.columns:

            final_df['DELIVERY_QTY'] = (
                df['DELIVERY_QTY']
            )

        else:

            final_df['DELIVERY_QTY'] = ""

        if 'DELIVERY_PERCENT' in df.columns:

            final_df['DELIVERY_PERCENT'] = (
                df['DELIVERY_PERCENT']
            )

        else:

            final_df['DELIVERY_PERCENT'] = ""

        # =================================================
        # REMOVE EMPTY SYMBOLS
        # =================================================

        final_df = final_df.dropna(
            subset=['SYMBOL']
        )

        # =================================================
        # REPLACE NaN
        # =================================================

        final_df = final_df.fillna("")

        print("\nFINAL SHAPE:")

        print(final_df.shape)

        print("\nFINAL SAMPLE:")

        print(final_df.head())

        if len(final_df) == 0:

            return None

        # =================================================
        # CONVERT TO PURE PYTHON TYPES
        # =================================================

        clean_data = []

        for row in final_df.values.tolist():

            clean_row = []

            for val in row:

                if pd.isna(val):

                    clean_row.append("")

                elif hasattr(val, 'item'):

                    clean_row.append(val.item())

                else:

                    clean_row.append(val)

            clean_data.append(clean_row)

        print(
            "\nTOTAL CLEAN ROWS:",
            len(clean_data)
        )

        return clean_data

    except Exception as e:

        print("\nBHAVCOPY ERROR:")

        print(str(e))

        return None

# =========================================================
# FIND LATEST VALID DATA
# =========================================================

data_to_insert = None

fetched_date = ""

today = datetime.now()

for i in range(7):

    test_date = today - timedelta(days=i)

    # =====================================================
    # SKIP WEEKENDS
    # =====================================================

    if test_date.weekday() >= 5:

        continue

    print(
        "\n================================="
    )

    print(
        "TRYING DATE:",
        test_date.strftime("%d-%b-%Y")
    )

    print(
        "================================="
    )

    temp_data = fetch_bhavcopy(
        test_date
    )

    if (
        temp_data is not None
        and len(temp_data) > 0
    ):

        data_to_insert = temp_data

        fetched_date = test_date.strftime(
            "%d-%b-%Y"
        )

        print(
            f"VALID DATA FOUND: "
            f"{fetched_date}"
        )

        break

    else:

        print(
            "NO VALID DATA FOUND"
        )

# =========================================================
# UPDATE GOOGLE SHEET
# =========================================================

if (
    data_to_insert is not None
    and len(data_to_insert) > 0
):

    try:

        print(
            "\nUPLOADING ROWS:",
            len(data_to_insert)
        )

        # =================================================
        # PREPARE FINAL SHEET DATA
        # =================================================

        all_data = [[
            "SYMBOL",
            "TURNOVER",
            "CLOSE_PRICE",
            "VOLUME",
            "DELIVERY_QTY",
            "DELIVERY_PERCENT"
        ]]

        all_data.extend(data_to_insert)

        # =================================================
        # CLEAR ENTIRE SHEET
        # =================================================

        worksheet.clear()

        # =================================================
        # UPLOAD ALL DATA
        # =================================================

        worksheet.update(
            range_name='A1',
            values=all_data
        )

        # =================================================
        # STATUS MESSAGE
        # =================================================

        ist_now = (
            datetime.utcnow()
            + timedelta(hours=5, minutes=30)
        ).strftime('%d-%b %H:%M')

        status_msg = (
            f"Bhavcopy Date: {fetched_date} | "
            f"Updated: {ist_now} IST"
        )

        worksheet.update(
            range_name='H2',
            values=[[status_msg]]
        )

        print(
            "\nSUCCESS: SHEET UPDATED"
        )

    except Exception as e:

        print(
            "\nGOOGLE SHEET ERROR:"
        )

        print(str(e))

else:

    print(
        "\nNO VALID DATA FOUND."
    )

    print(
        "OLD SHEET DATA RETAINED."
    )
