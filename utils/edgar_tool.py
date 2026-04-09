import logging

import requests


logger = logging.getLogger(__name__)

CIK_MAP = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "TSLA": "0001318605",
    "NVDA": "0001045810",
    "JPM": "0000019617",
    "BAC": "0000070858",
    "GS": "0000886982",
    "NFLX": "0001065280",
    "INTC": "0000050863",
    "AMD": "0000002488",
    "ORCL": "0001341439",
    "IBM": "0000051143",
    "WMT": "0000104169",
    "DIS": "0001001039",
    "PFE": "0000078003",
    "JNJ": "0000200406",
    "XOM": "0000034088",
}


def fetch_edgar_summary(ticker: str) -> dict | None:
    """Fetch basic company metadata from SEC EDGAR submissions API.

    Fetches company metadata from SEC EDGAR free API.
    No API key required.
    Returns dict with company_name, sic, fiscal_year_end
    or None if ticker not in map or request fails.

    Args:
        ticker: Public company ticker symbol.

    Returns:
        Metadata dict on success, else None.

    Raises:
        None.
    """
    cik = CIK_MAP.get(str(ticker).upper())
    if not cik:
        logger.debug("Ticker %s not found in CIK map.", ticker)
        return None

    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    headers = {"User-Agent": "EarningsLens research@example.com"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return {
            "company_name": data.get("name"),
            "sic": data.get("sic"),
            "fiscal_year_end": data.get("fiscalYearEnd"),
            "cik": cik,
        }
    except Exception as exc:
        logger.warning("EDGAR request failed for %s: %s", ticker, exc)
        return None
