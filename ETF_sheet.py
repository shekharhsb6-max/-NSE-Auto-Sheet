# =========================================================
# NSE ETF BHAVCOPY DOWNLOADER → GOOGLE SHEETS
# =========================================================
#
# WHAT THIS SCRIPT DOES
# ---------------------------------------------------------
# 1. Downloads NSE Equity Bhavcopy
# 2. Downloads NSE Delivery Data
# 3. Filters ETF-like symbols
# 4. Excludes Liquid / Bond ETFs
# 5. Merges Delivery %
# 6. Uploads clean ETF data to Google Sheets
#
# =========================================================
# INSTALL REQUIRED LIBRARIES
# =========================================================
#
# pip install pandas requests gspread oauth2client
#
# =========================================================
# GOOGLE SHEETS SETUP
# =========================================================
#
# 1. Create Google Cloud Project
# 2. Enable:
#       - Google Sheets API
#       - Google Drive API
#
# 3. Create Service Account
# 4. Download credentials JSON
# 5. Rename JSON file to:
#       credentials.json
#
# 6. Share your Google Sheet with:
#       service-account-email
#
# =========================================================

import pandas as pd
import requests
import zipfile
import io
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =========================================================
# GOOGLE SHEET DETAILS
# =========================================================

SPREADSHEET_ID = "1D3E5lyH2QUq55AzsJqSbJj2tNkmOQht_8xUmt0mdvbk"

WORKSHEET_NAME = "RAW_DATA"

# =========================================================
# ETF EXCLUSION FILTER
# =========================================================

EXCLUDE_KEYWORDS = [
    "LIQUID",
    "BOND",
    "GILT",
    "TREASURY",
    "OVERNIGHT",
    "MONEYMARKET"
]

# =========================================================
# DATE
# =========================================================

today = datetime.now()

dd = today.strftime("%d")
mm = today.strftime("%m")
yyyy = today.strftime("%Y")

date_code = today.strftime("%d%m%Y")

# =========================================================
# NSE FILE URLS
# =========================================================

bhavcopy_url = (
    f"https://nsearchives.nseindia.com/content/cm/"
    f"BhavCopy_NSE_CM_0_0_0_{date_code}_F_0000.csv.zip"
)

delivery_url = (
    f"https://nsearchives.nseindia.com/products/content/"
    f"sec_bhavdata_full_{dd}{mm}{yyyy}.csv"
)

headers = {
    "User-Agent": "Mozilla/5.0"
}

# =========================================================
# DOWNLOAD BHAVCOPY
# =========================================================

print("Downloading Bhavcopy...")

bhav_response = requests.get(
    bhavcopy_url,
    headers=headers
)

if bhav_response.status_code != 200:
    raise Exception(
        "Bhavcopy not available for this date."
    )

z = zipfile.ZipFile(
    io.BytesIO(bhav_response.content)
)

csv_name = z.namelist()[0]

bhav_df = pd.read_csv(
    z.open(csv_name)
)

print("Bhavcopy Downloaded.")

# =========================================================
# DOWNLOAD DELIVERY FILE
# =========================================================

print("Downloading Delivery Data...")

delivery_response = requests.get(
    delivery_url,
    headers=headers
)

if delivery_response.status_code != 200:
    raise Exception(
        "Delivery data not available."
    )

delivery_df = pd.read_csv(
    io.StringIO(delivery_response.text)
)

print("Delivery Data Downloaded.")

# =========================================================
# CLEAN COLUMN NAMES
# =========================================================

bhav_df.columns = bhav_df.columns.str.strip()

delivery_df.columns = delivery_df.columns.str.strip()

# =========================================================
# KEEP REQUIRED COLUMNS
# =========================================================

bhav_df = bhav_df[
    [
        "SYMBOL",
        "OPEN_PRICE",
        "HIGH_PRICE",
        "LOW_PRICE",
        "CLOSE_PRICE",
        "TTL_TRD_QNTY",
        "TURNOVER_LACS"
    ]
]

delivery_df = delivery_df[
    [
        "SYMBOL",
        "DELIV_QTY",
        "DELIV_PER"
    ]
]

# =========================================================
# MERGE DATA
# =========================================================

df = pd.merge(
    bhav_df,
    delivery_df,
    on="SYMBOL",
    how="left"
)

# =========================================================
# ETF FILTER
# =========================================================

ETF_KEYWORDS = [
    "BEES",
    "ETF",
    "MON100",
    "GOLD",
    "SILVER",
    "BANK",
    "IT",
    "PHARMA",
    "AUTO",
    "CPSE",
    "CONSUM",
    "INFRA",
    "PSUBNK",
    "NIFTY"
]

etf_pattern = "|".join(ETF_KEYWORDS)

df = df[
    df["SYMBOL"].str.contains(
        etf_pattern,
        case=False,
        na=False
    )
]

# =========================================================
# EXCLUDE LIQUID / BOND ETFs
# =========================================================

exclude_pattern = "|".join(EXCLUDE_KEYWORDS)

df = df[
    ~df["SYMBOL"].str.contains(
        exclude_pattern,
        case=False,
        na=False
    )
]

# =========================================================
# SORT DATA
# =========================================================

df = df.sort_values(
    by=[
        "TURNOVER_LACS",
        "DELIV_PER"
    ],
    ascending=False
)

# =========================================================
# GOOGLE SHEETS AUTHENTICATION
# =========================================================

print("Connecting to Google Sheets...")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

client = gspread.authorize(creds)

# =========================================================
# OPEN GOOGLE SHEET
# =========================================================

spreadsheet = client.open_by_key(
    SPREADSHEET_ID
)

# =========================================================
# OPEN WORKSHEET
# =========================================================

try:
    worksheet = spreadsheet.worksheet(
        WORKSHEET_NAME
    )

except:
    worksheet = spreadsheet.add_worksheet(
        title=WORKSHEET_NAME,
        rows="5000",
        cols="20"
    )

# =========================================================
# CLEAR OLD DATA
# =========================================================

worksheet.clear()

# =========================================================
# PREPARE DATA
# =========================================================

data = [
    df.columns.values.tolist()
] + df.values.tolist()

# =========================================================
# UPLOAD DATA
# =========================================================

print("Uploading data to Google Sheets...")

worksheet.update(data)

print("Upload Complete.")

# =========================================================
# SUCCESS MESSAGE
# =========================================================

print("ETF RAW_DATA Sheet Updated Successfully.")
