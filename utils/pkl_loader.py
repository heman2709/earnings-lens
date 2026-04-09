"""Utilities for loading and querying earnings transcript pickle data.

This module provides helper functions for Layer 1 data access over a pickled
Pandas DataFrame containing earnings call transcripts. It supports loading and
validating the dataset schema, selecting a transcript by ticker and quarter,
deriving prior quarters, and listing available tickers and quarters.
"""

import logging
import os
import re

import pandas as pd


logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["date", "exchange", "q", "ticker", "transcript"]
QUARTER_PATTERN = re.compile(r"^\d{4}-Q[1-4]$")


def load_dataframe(path: str = "data/transcripts.pkl") -> pd.DataFrame:
    """Load and validate the transcripts DataFrame from a pickle file.

    Args:
        path: Relative or absolute path to the pickle file.

    Returns:
        A pandas DataFrame containing transcript records.

    Raises:
        FileNotFoundError: If the provided file path does not exist.
        ValueError: If required columns are missing from the DataFrame.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Transcript file not found: {path}")

    df = pd.read_pickle(path)
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(
            "Missing required columns in transcripts DataFrame: "
            f"{missing_columns}. Required columns are: {REQUIRED_COLUMNS}"
        )
    return df


def get_transcript(df: pd.DataFrame, ticker: str, quarter: str) -> str | None:
    """Return the transcript for a ticker and quarter combination.

    Filtering is done using a case-insensitive ticker comparison and exact
    quarter match on the `q` column.

    Args:
        df: Source DataFrame with transcript records.
        ticker: Company ticker symbol (case-insensitive).
        quarter: Quarter in `YYYY-QN` format.

    Returns:
        The transcript text if a matching row exists; otherwise None.

    Raises:
        ValueError: If required columns for this operation are missing.
    """
    required = {"ticker", "q", "transcript"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns for lookup: {sorted(missing)}"
        )

    filtered = df[
        (df["ticker"].astype(str).str.upper() == str(ticker).upper())
        & (df["q"] == quarter)
    ]

    if filtered.empty:
        return None

    if len(filtered) > 1:
        logger.warning(
            "Multiple transcripts found for ticker=%s quarter=%s; using first row.",
            ticker,
            quarter,
        )

    transcript_value = filtered.iloc[0]["transcript"]
    if pd.isna(transcript_value):
        return None
    return str(transcript_value)


def get_prior_quarter(quarter: str) -> str:
    """Compute the immediately prior quarter string.

    Examples:
        - `2020-Q3` -> `2020-Q2`
        - `2020-Q1` -> `2019-Q4`

    Args:
        quarter: Quarter in `YYYY-QN` format.

    Returns:
        The previous quarter in `YYYY-QN` format.

    Raises:
        ValueError: If the input does not match `YYYY-Q[1-4]`.
    """
    if not QUARTER_PATTERN.match(quarter):
        raise ValueError(
            "Invalid quarter format. Expected YYYY-Q[1-4], "
            f"received: {quarter}"
        )

    year_str, quarter_str = quarter.split("-Q")
    year = int(year_str)
    q_num = int(quarter_str)

    if q_num == 1:
        return f"{year - 1}-Q4"
    return f"{year}-Q{q_num - 1}"


def get_available_tickers(df: pd.DataFrame) -> list[str]:
    """Return a sorted list of unique ticker symbols in the dataset.

    Args:
        df: Source DataFrame containing a `ticker` column.

    Returns:
        Sorted unique ticker symbols as strings.

    Raises:
        ValueError: If the `ticker` column is missing.
    """
    if "ticker" not in df.columns:
        raise ValueError("DataFrame is missing required column: ticker")

    tickers = (
        df["ticker"]
        .dropna()
        .astype(str)
        .str.strip()
    )
    return sorted(tickers[tickers != ""].unique().tolist())


def get_available_quarters(df: pd.DataFrame, ticker: str) -> list[str]:
    """Return sorted unique quarters available for a specific ticker.

    Args:
        df: Source DataFrame containing `ticker` and `q` columns.
        ticker: Company ticker symbol to filter on (case-insensitive).

    Returns:
        Sorted list of quarter strings for the provided ticker.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"ticker", "q"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns for quarter lookup: {sorted(missing)}"
        )

    quarters = df.loc[
        df["ticker"].astype(str).str.upper() == str(ticker).upper(),
        "q",
    ].dropna().astype(str)

    return sorted(quarters.unique().tolist())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    data_path = "data/transcripts.pkl"
    print(f"Loading DataFrame from: {data_path}")
    dataframe = load_dataframe(data_path)
    print(f"DataFrame shape: {dataframe.shape}")
    print(f"DataFrame columns: {list(dataframe.columns)}")

    sample_ticker = "BILI"
    sample_quarter = "2020-Q2"
    sample_transcript = get_transcript(dataframe, sample_ticker, sample_quarter)
    print(
        f"Transcript found for {sample_ticker} {sample_quarter}: "
        f"{sample_transcript is not None}"
    )
    if sample_transcript:
        preview = sample_transcript[:200].replace("\n", " ")
        print(f"Transcript preview: {preview}...")

    print("Prior quarter tests:")
    test_quarters = ["2020-Q3", "2020-Q1", "2021-Q4"]
    for qtr in test_quarters:
        print(f"  {qtr} -> {get_prior_quarter(qtr)}")

    bili_quarters = get_available_quarters(dataframe, "BILI")
    print(f"Available quarters for BILI ({len(bili_quarters)}): {bili_quarters}")
