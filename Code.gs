/**
 * NSE Auto Breakout System — Apps Script backend
 * Bind this script to your Google Sheet (Extensions > Apps Script).
 * Tabs expected: "Top 250 Stocks" (filled daily by GitHub Action python script)
 *                "Final List" (auto-filtered breakout stocks)
 */

// ---------- CONFIG ----------
const SHEET_TOP250 = "Top 250 Stocks";
const SHEET_FINAL = "Final List";
// Simple shared secret so random people can't hit your web app URL.
// Change this, then use the SAME value in index.html (API_KEY constant).
const API_KEY = "himadri-nse-8k3f2m9x";
// -----------------------------

/**
 * You maintain all formulas in "Top 250 Stocks" and "Final List" by hand —
 * this script does NOT write or overwrite any sheet formulas.
 * refreshFinalList() below just forces a recalculation (SpreadsheetApp.flush)
 * so GOOGLEFINANCE-based formulas pick up fresh data after the daily
 * Python/GitHub Action update.
 */

/**
 * Time-based trigger target. Run this ~30–45 min AFTER your GitHub Action
 * updates "Top 250 Stocks" (Action runs 8:15 PM IST -> schedule this ~9:00 PM IST)
 * so GOOGLEFINANCE formulas have time to recalculate on fresh data.
 * Set up in Apps Script editor: Triggers (clock icon) > Add Trigger >
 *   Function: refreshFinalList | Event source: Time-driven | Day timer > 9pm-10pm
 */
function refreshFinalList() {
  SpreadsheetApp.flush();
}

/**
 * Web App entry point — deploy via Deploy > New deployment > Web app
 *   Execute as: Me
 *   Who has access: Anyone
 * Copy the resulting /exec URL into index.html (API_URL constant).
 * Call as: https://script.google.com/macros/s/XXXX/exec?key=YOUR_API_KEY
 */
function doGet(e) {
  const key = e && e.parameter && e.parameter.key;
  if (key !== API_KEY) {
    return jsonOutput({ error: "Unauthorized" });
  }

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const topSheet = ss.getSheetByName(SHEET_TOP250);
  const finalSheet = ss.getSheetByName(SHEET_FINAL);

  const statusMsg = topSheet ? String(topSheet.getRange("N1").getValue() || "") : "";

  // Final List sheet layout: row 1 = title, row 2 = headers, data from row 3
  // Columns: A NSE Code, B Turnover, C Previous Close, D CMP,
  // E Difference from 200DMA, F CAR (Signal), G Rating
  let finalRows = [];
  if (finalSheet) {
    const lastRow = finalSheet.getLastRow();
    const lastCol = finalSheet.getLastColumn();
    if (lastRow >= 3 && lastCol >= 7) {
      const values = finalSheet.getRange(3, 1, lastRow - 2, 7).getValues();
      finalRows = values
        .filter(r => r[0] !== "" && r[0] !== "कोई स्टॉक नहीं मिला")
        .map(r => ({
          symbol: r[0],
          turnover: r[1],
          prevClose: r[2],
          cmp: r[3],
          diff200: r[4],
          signal: r[5],
          rating: r[6]
        }));
    }
  }

  return jsonOutput({
    status: statusMsg,
    count: finalRows.length,
    stocks: finalRows,
    generatedAt: new Date().toISOString()
  });
}

function jsonOutput(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
