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

    print("CRITICAL: GCP_CREDENTIALS secret missing!")
    exit(1)

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
# COMMON NSE SESSION
# =========================================================

def create_nse_session():

    session = requests.Session()

    session.headers.update({

        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0 Safari/537.36'
        ),

        'Accept': (
            'text/html,application/xhtml+xml,'
            'application/xml;q=0.9,*/*;q=0.8'
        ),

        'Accept-Language': 'en-US,en;q=0.9',

        'Referer': 'https://www.nseindia.com/'
    })

    try:

        session.get(
            "https://www.nseindia.com",
            timeout=10
        )

    except:
        pass

    return session

# =========================================================
# NSE DELIVERY DATA FETCHER
# =========================================================

def fetch_delivery_data(date_obj):

    date_str = date_obj.strftime("%d%m%Y")

    url = (
        f"https://archives.nseindia.com/products/content/"
        f"sec_bhavdata_full_{date_str}.csv"
    )

    session = create_nse_session()

    try:

        response = session.get(
            url,
            timeout=30
        )

        print(f"Delivery URL: {url}")
        print(f"Delivery Status: {response.status_code}")

        if response.status_code == 200:

            from io import StringIO

            df = pd.read_csv(
                StringIO(response.text)
            )

            # =====================================
            # CLEAN COLUMN NAMES
            # =====================================

            df.columns = [
                c.strip()
                for c in df.columns
            ]

            # =====================================
            # CLEAN STRING VALUES
            # =====================================

            for col in df.columns:

                if df[col].dtype == "object":

                    df[col] = (
                        df[col]
                        .astype(str)
                        .str.strip()
                    )

            # =====================================
            # COLUMN VALIDATION
            # =====================================

            required_cols = [
                'SYMBOL',
                'SERIES',
                'DELIV_QTY',
                'DELIV_PER'
            ]

            missing_cols = [
                c for c in required_cols
                if c not in df.columns
            ]

            if missing_cols:

                print(
                    f"Missing Delivery Columns: "
                    f"{missing_cols}"
                )

                return None

            # =====================================
            # EQ ONLY
            # =====================================

            df = df[
                df['SERIES'] == 'EQ'
            ]

            # =====================================
            # NUMERIC CONVERSION
            # =====================================

            df['DELIV_QTY'] = pd.to_numeric(
                df['DELIV_QTY'],
                errors='coerce'
            )

            df['DELIV_PER'] = pd.to_numeric(
                df['DELIV_PER'],
                errors='coerce'
            )

            # =====================================
            # FINAL DELIVERY DATAFRAME
            # =====================================

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

            return delivery_df

        return None

    except Exception as e:

        print(f"Delivery Error: {str(e)}")

        return None

# =========================================================
# NSE BHAVCOPY FETCHER
# =========================================================

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = (
        f"https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

    session = create_nse_session()

    try:

        # =================================================
        # DOWNLOAD BHAVCOPY
        # =================================================

        response = session.get(
            url,
            timeout=30
        )

        print(f"Trying Date: {date_str}")
        print(f"Bhavcopy Status: {response.status_code}")

        if response.status_code == 200:

            with zipfile.ZipFile(
                io.BytesIO(response.content)
            ) as z:

                csv_filename = z.namelist()[0]

                with z.open(csv_filename) as f:

                    df = pd.read_csv(f)

                    # =====================================
                    # FETCH DELIVERY DATA
                    # =====================================

                    delivery_df = fetch_delivery_data(
                        date_obj
                    )

                    # =====================================
                    # CLEAN COLUMN NAMES
                    # =====================================

                    df.columns = [
                        c.strip()
                        for c in df.columns
                    ]

                    # =====================================
                    # COLUMN DETECTION
                    # =====================================

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
                                'CLOSE_PRICE',
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

                    volume_col = next(
                        (
                            c for c in [
                                'TtlTradgVol',
                                'TTL_TRD_QNTY',
                                'VOLUME'
                            ]
                            if c in df.columns
                        ),
                        None
                    )

                    # =====================================
                    # VALIDATION
                    # =====================================

                    if not all([
                        sym_col,
                        turnover_col,
                        close_col
                    ]):

                        print(
                            "Required Bhavcopy "
                            "columns missing."
                        )

                        return None

                    # =====================================
                    # EQ ONLY
                    # =====================================

                    if series_col:

                        df = df[
                            df[series_col]
                            .astype(str)
                            .str.strip() == 'EQ'
                        ]

                    # =====================================
                    # NUMERIC CONVERSION
                    # =====================================

                    df[turnover_col] = pd.to_numeric(
                        df[turnover_col],
                        errors='coerce'
                    )

                    if volume_col:

                        df[volume_col] = pd.to_numeric(
                            df[volume_col],
                            errors='coerce'
                        )

                    # =====================================
                    # REMOVE EMPTY TURNOVER
                    # =====================================

                    df = df.dropna(
                        subset=[turnover_col]
                    )

                    # =====================================
                    # SORT BY TURNOVER
                    # =====================================

                    df = df.sort_values(
                        by=turnover_col,
                        ascending=False
                    )

                    # =====================================
                    # MERGE DELIVERY DATA
                    # =====================================

                    if delivery_df is not None:

                        df = df.merge(
                            delivery_df,
                            left_on=sym_col,
                            right_on='SYMBOL',
                            how='left'
                        )

                    # =====================================
                    # FINAL COLUMNS
                    # =====================================

                    final_cols = [
                        sym_col,
                        turnover_col,
                        close_col
                    ]

                    if volume_col:

                        final_cols.append(
                            volume_col
                        )

                    if 'DELIVERY_QTY' in df.columns:

                        final_cols.append(
                            'DELIVERY_QTY'
                        )

                    if 'DELIVERY_PERCENT' in df.columns:

                        final_cols.append(
                            'DELIVERY_PERCENT'
                        )

                    # =====================================
                    # FINAL DATAFRAME
                    # =====================================

                    final_df = df[
                        final_cols
                    ].copy()

                    # =====================================
                    # ROUND DELIVERY %
                    # =====================================

                    if 'DELIVERY_PERCENT' in final_df.columns:

                        final_df['DELIVERY_PERCENT'] = (
                            final_df[
                                'DELIVERY_PERCENT'
                            ].round(2)
                        )

                    return final_df.values.tolist()

        return None

    except Exception as e:

        print(f"Bhavcopy Error: {str(e)}")

        return None

# =========================================================
# EXECUTION LOGIC
# =========================================================

date = datetime.now()

data_to_insert = None

fetched_date_str = ""

for i in range(7):

    test_date = date - timedelta(days=i)

    # =============================================
    # SKIP WEEKENDS
    # =============================================

    if test_date.weekday() >= 5:

        continue

    data_to_insert = fetch_bhavcopy_for_date(
        test_date
    )

    if data_to_insert:

        fetched_date_str = test_date.strftime(
            '%d-%b-%Y'
        )

        break

# =========================================================
# UPDATE GOOGLE SHEET
# =========================================================

if data_to_insert:

    try:

        # =============================================
        # CLEAR OLD DATA
        # =============================================

        worksheet.batch_clear([
            'A2:F5000'
        ])

        # =============================================
        # HEADERS
        # =============================================

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

        # =============================================
        # UPLOAD DATA
        # =============================================

        worksheet.update(
            'A2',
            data_to_insert
        )

        # =============================================
        # STATUS MESSAGE
        # =============================================

        ist_now = (
            datetime.utcnow() +
            timedelta(hours=5, minutes=30)
        ).strftime('%d-%b %H:%M')

        status_msg = (
            f"Bhavcopy Date: {fetched_date_str} | "
            f"Updated: {ist_now} IST"
        )

        worksheet.update(
            'H2',
            [[status_msg]]
        )

        print(
            f"SUCCESS: RAW_DATA Updated "
            f"for {fetched_date_str}"
        )

    except Exception as e:

        print(
            f"Google Sheet Error: {str(e)}"
        )

else:

    print(
        "FAILED: No Bhavcopy found "
        "in last 7 trading days."
    )
