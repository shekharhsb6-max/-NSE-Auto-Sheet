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
# ETF FILTERS
# =========================================================

# Include only ETF-type symbols

ETF_KEYWORDS = (
    "BEES|ETF|MON100|GOLD|SILVER|"
    "BANK|IT|PHARMA|AUTO|CPSE|"
    "INFRA|PSUBNK|NIFTY"
)

# Exclude debt / liquid ETFs

EXCLUDE_KEYWORDS = (
    "LIQUID|BOND|GILT|"
    "TREASURY|OVERNIGHT|"
    "MONEYMARKET|SDL|SHORTTERM"
)

# =========================================================
# NSE DATA FETCHER
# =========================================================

def fetch_bhavcopy_for_date(date_obj):

    date_str = date_obj.strftime("%Y%m%d")

    url = (
        f"https://nsearchives.nseindia.com/content/cm/"
        f"BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"
    )

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

        # Visit NSE first
        session.get(
            "https://www.nseindia.com",
            timeout=10
        )

        # Download Bhavcopy
        response = session.get(
            url,
            timeout=30
        )

        print(f"Trying Date: {date_str}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:

            with zipfile.ZipFile(
                io.BytesIO(response.content)
            ) as z:

                csv_filename = z.namelist()[0]

                with z.open(csv_filename) as f:

                    df = pd.read_csv(f)

                    df.columns = [
                        c.strip()
                        for c in df.columns
                    ]

                    # =================================================
                    # COLUMN DETECTION
                    # =================================================

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

                    # =================================================
                    # VALIDATION
                    # =================================================

                    if not all([
                        sym_col,
                        turnover_col,
                        close_col
                    ]):

                        print("Required columns missing.")

                        return None

                    # =================================================
                    # ONLY EQ SERIES
                    # =================================================

                    if series_col:

                        df = df[
                            df[series_col]
                            .astype(str)
                            .str.strip() == 'EQ'
                        ]

                    # =================================================
                    # ETF FILTER
                    # =================================================

                    df = df[
                        df[sym_col]
                        .astype(str)
                        .str.contains(
                            ETF_KEYWORDS,
                            case=False,
                            na=False
                        )
                    ]

                    # =================================================
                    # EXCLUDE DEBT ETFs
                    # =================================================

                    df = df[
                        ~df[sym_col]
                        .astype(str)
                        .str.contains(
                            EXCLUDE_KEYWORDS,
                            case=False,
                            na=False
                        )
                    ]

                    # =================================================
                    # NUMERIC CONVERSION
                    # =================================================

                    df[turnover_col] = pd.to_numeric(
                        df[turnover_col],
                        errors='coerce'
                    )

                    if volume_col:

                        df[volume_col] = pd.to_numeric(
                            df[volume_col],
                            errors='coerce'
                        )

                    df = df.dropna(
                        subset=[turnover_col]
                    )

                    # =================================================
                    # SORT BY TURNOVER
                    # =================================================

                    df_top = df.sort_values(
                        by=turnover_col,
                        ascending=False
                    ).head(50)

                    # =================================================
                    # FINAL COLUMNS
                    # =================================================

                    final_cols = [
                        sym_col,
                        turnover_col,
                        close_col
                    ]

                    if volume_col:

                        final_cols.append(volume_col)

                    return df_top[
                        final_cols
                    ].values.tolist()

        return None

    except Exception as e:

        print(f"ERROR: {str(e)}")

        return None

# =========================================================
# EXECUTION LOGIC
# =========================================================

date = datetime.now()

data_to_insert = None

fetched_date_str = ""

for i in range(7):

    test_date = date - timedelta(days=i)

    # Skip weekends
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

        # Clear old data
        worksheet.batch_clear([
            'A2:D100'
        ])

        # Upload new data
        worksheet.update(
            'A2',
            data_to_insert
        )

        # Status
        ist_now = (
            datetime.utcnow() +
            timedelta(hours=5, minutes=30)
        ).strftime('%d-%b %H:%M')

        status_msg = (
            f"ETF Data Date: {fetched_date_str} | "
            f"Updated: {ist_now} IST"
        )

        worksheet.update(
            'H2',
            [[status_msg]]
        )

        print(
            f"SUCCESS: Top 50 Non-Debt ETFs "
            f"Updated for {fetched_date_str}"
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
