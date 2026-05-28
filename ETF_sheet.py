# =========================================================
# NSE ETF BHAVCOPY DOWNLOADER → GOOGLE SHEETS
# =========================================================
#
# FILE NAME:
#     ETF_sheet.py
#
# =========================================================
# INSTALL REQUIRED LIBRARIES
# =========================================================
#
# pip install pandas requests gspread oauth2client
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
# NSE URLS
# =========================================================

bhavcopy_url = (
    f"https://nsearchives.nseindia.com/content/cm/"
    f"BhavCopy_NSE_CM_0_0_0_{date_code}_F_0000.csv.zip"
)

delivery_url = (
    f"https://nsearchives.nseindia.com/products/content/"
    f"sec_bhavdata_full_{dd}{mm}{yyyy}.csv"
)

# =========================================================
# NSE SESSION
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive"
})

# =========================================================
# VISIT NSE HOME PAGE FIRST
# =========================================================

print("Connecting to NSE...")

session.get(
    "https://www.nseindia.com",
    timeout=10
)

# =========================================================
# DOWNLOAD BHAVCOPY
# =========================================================

print("Downloading Bhavcopy...")

bhav_response = session.get(
    bhavcopy_url,
    timeout=30
)

print("Bhavcopy Status Code :", bhav_response.status_code)

if bhav_response.status_code != 200:

    raise Exception(
        f"Bhavcopy download failed. "
        f"Status Code: {bhav_response.status_code}"
    )

# =========================================================
# READ ZIP FILE
# =========================================================

z = zipfile.ZipFile(
    io.BytesIO(bhav_response.content)
)

csv_name = z.namelist()[0]

bhav_df = pd.read_csv(
    z.open(csv_name)
)

print("Bhavcopy Downloaded Successfully.")

# =========================================================
# DOWNLOAD DELIVERY FILE
# =========================================================

print("Downloading Delivery Data...")

delivery_response = session.get(
    delivery_url,
    timeout=30
)

print("Delivery Status Code :", delivery_response.status_code)

if delivery_response.status_code != 200:

    raise Exception(
        f"Delivery download failed. "
        f"Status Code: {delivery_response.status_code}"
    )

delivery_df = pd.read_csv(
    io.StringIO(delivery_response.text)
)

print("Delivery Data Downloaded Successfully.")

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
# GOOGLE SHEETS AUTH
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

print("Uploading Data To Google Sheets...")

worksheet.update(data)

print("Upload Complete.")

# =========================================================
# SUCCESS
# =========================================================

print("ETF RAW_DATA Sheet Updated Successfully.")
