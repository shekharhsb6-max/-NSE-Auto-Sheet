import gspread
from oauth2client.service_account import ServiceAccountCredentials

import pandas as pd
import requests
import zipfile
import io

from datetime import datetime, timedelta
import os
import json

# =====================================================
# GOOGLE SHEETS AUTH
# =====================================================

creds_json = os.environ.get('GCP_CREDENTIALS')

if not creds_json:

    print("GCP_CREDENTIALS missing")
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

# =====================================================
# SHEET
# =====================================================

spreadsheet_id = "1D3E5lyH2QUq55AzsJqSbJj2tNkmOQht_8xUmt0mdvbk"

worksheet = client.open_by_key(
    spreadsheet_id
).worksheet("RAW_DATA")

# =====================================================
# NSE SESSION
# =====================================================

def get_session():

    s = requests.Session()

    s.headers.update({

        "User-Agent":
        "Mozilla/5.0",

        "Referer":
        "https://www.nseindia.com/"
    })

    try:

        s.get(
            "https://www.nseindia.com",
            timeout=10
        )

    except:
        pass

    return s

# =====================================================
# FETCH DELIVERY DATA
# =====================================================

def fetch_delivery(date_obj):

    try:

        session = get_session()

        date_str = date_obj.strftime("%d%m%Y")

        url = (
            "https://archives.nseindia.com/products/content/"
            f"sec_bhavdata_full_{date_str}.csv"
        )

        r = session.get(url, timeout=30)

        print("Delivery:", r.status_code)

        if r.status_code != 200:

            return None

        from io import StringIO

        df = pd.read_csv(
            StringIO(r.text)
        )

        # CLEAN COLUMNS

        df.columns = [
            c.strip()
            for c in df.columns
        ]

        # CLEAN VALUES

        for col in df.columns:

            if df[col].dtype == object:

                df[col] = (
                    df[col]
                    .astype(str)
                    .str.strip()
                )

        print(df.columns.tolist())

        # REQUIRED COLUMNS

        needed = [
            'SYMBOL',
            'SERIES',
            'DELIV_QTY',
            'DELIV_PER'
        ]

        for n in needed:

            if n not in df.columns:

                print(f"Missing {n}")
                return None

        # EQ ONLY

        df = df[
            df['SERIES'] == 'EQ'
        ]

        # FINAL

        df = df[[
            'SYMBOL',
            'DELIV_QTY',
            'DELIV_PER'
        ]]

        df.columns = [
            'SYMBOL',
            'DELIVERY_QTY',
            'DELIVERY_PERCENT'
        ]

        return df

    except Exception as e:

        print("Delivery Error:", e)

        return None

# =====================================================
# FETCH BHAVCOPY
# =====================================================

def fetch_bhavcopy(date_obj):

    try:

        session = get_session()

        date_str = date_obj.strftime("%Y%m%d")

        url = (
            "https://nsearchives.nseindia.com/content/cm/"
            f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
        )

        r = session.get(url, timeout=30)

        print("Bhavcopy:", r.status_code)

        if r.status_code != 200:

            return None

        with zipfile.ZipFile(
            io.BytesIO(r.content)
        ) as z:

            fname = z.namelist()[0]

            with z.open(fname) as f:

                df = pd.read_csv(f)

        # CLEAN COLUMN NAMES

        df.columns = [
            c.strip()
            for c in df.columns
        ]

        print(df.columns.tolist())

        # DYNAMIC COLUMN DETECTION

        symbol_col = None
        close_col = None
        turnover_col = None
        volume_col = None
        series_col = None

        for c in df.columns:

            lc = c.lower()

            if (
                'symbol' in lc
                or 'tckrsymb' in lc
            ):
                symbol_col = c

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

            elif (
                'series' in lc
                or 'sctysrs' in lc
            ):
                series_col = c

        print(
            symbol_col,
            close_col,
            turnover_col,
            volume_col,
            series_col
        )

        # VALIDATION

        if not symbol_col:

            return None

        if not turnover_col:

            return None

        if not close_col:

            return None

        # EQ FILTER

        if series_col:

            df = df[
                df[series_col]
                .astype(str)
                .str.strip() == 'EQ'
            ]

        # NUMERIC

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

        # REMOVE EMPTY

        df = df.dropna(
            subset=[
                turnover_col,
                close_col
            ]
        )

        # SORT

        df = df.sort_values(
            by=turnover_col,
            ascending=False
        )

        # FETCH DELIVERY

        delivery_df = fetch_delivery(date_obj)

        # MERGE

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

        # FINAL OUTPUT

        final = pd.DataFrame()

        final['SYMBOL'] = df[symbol_col]

        final['TURNOVER'] = df[turnover_col]

        final['CLOSE_PRICE'] = df[close_col]

        if volume_col:

            final['VOLUME'] = df[volume_col]

        else:

            final['VOLUME'] = ""

        if 'DELIVERY_QTY' in df.columns:

            final['DELIVERY_QTY'] = df[
                'DELIVERY_QTY'
            ]

        else:

            final['DELIVERY_QTY'] = ""

        if 'DELIVERY_PERCENT' in df.columns:

            final['DELIVERY_PERCENT'] = df[
                'DELIVERY_PERCENT'
            ]

        else:

            final['DELIVERY_PERCENT'] = ""

        # REMOVE EMPTY SYMBOLS

        final = final.dropna(
            subset=['SYMBOL']
        )

        print(final.head())

        print(final.shape)

        if len(final) == 0:

            return None

        return final.values.tolist()

    except Exception as e:

        print("Bhavcopy Error:", e)

        return None

# =====================================================
# FIND LATEST VALID DATA
# =====================================================

data_to_insert = None

fetched_date = ""

today = datetime.now()

for i in range(7):

    d = today - timedelta(days=i)

    # SKIP WEEKEND

    if d.weekday() >= 5:

        continue

    print(
        "\nTrying:",
        d.strftime("%d-%b-%Y")
    )

    temp = fetch_bhavcopy(d)

    if temp and len(temp) > 0:

        data_to_insert = temp

        fetched_date = d.strftime(
            "%d-%b-%Y"
        )

        print("SUCCESS")

        break

# =====================================================
# UPDATE SHEET
# =====================================================

if data_to_insert:

    try:

        print(
            "Uploading Rows:",
            len(data_to_insert)
        )

        # CLEAR OLD DATA

        worksheet.batch_clear([
            'A2:F5000'
        ])

        # HEADERS

        headers = [[
            "SYMBOL",
            "TURNOVER",
            "CLOSE_PRICE",
            "VOLUME",
            "DELIVERY_QTY",
            "DELIVERY_PERCENT"
        ]]

        worksheet.update(
            'A1',
            headers
        )

        # UPLOAD

        worksheet.update(
            'A2',
            data_to_insert
        )

        # STATUS

        ist_now = (
            datetime.utcnow() +
            timedelta(hours=5, minutes=30)
        ).strftime('%d-%b %H:%M')

        status = (
            f"Bhavcopy Date: {fetched_date} | "
            f"Updated: {ist_now} IST"
        )

        worksheet.update(
            'H2',
            [[status]]
        )

        print("DONE")

    except Exception as e:

        print("Sheet Error:", e)

else:

    print(
        "NO VALID DATA FOUND. "
        "OLD DATA RETAINED."
    )
