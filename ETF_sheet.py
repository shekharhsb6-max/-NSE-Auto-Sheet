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

# First visit homepage
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

print("Bhavcopy Status Code:", bhav_response.status_code)

if bhav_response.status_code != 200:

    raise Exception(
        f"Bhavcopy download failed. "
        f"Status Code: {bhav_response.status_code}"
    )
