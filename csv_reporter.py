"""
InboxIQ — CSV Reporter Module
Writes classified email records to a structured CSV file using pandas.
"""

import logging
import os
from pathlib import Path

import pandas as pd

logger = logging.getLogger("InboxIQ")

COLUMNS = ["sender", "subject", "date", "tag"]


class CSVReporter:
    """Handles CSV output for InboxIQ classification results."""

    def __init__(self, output_path: str = "results.csv"):
        self.output_path = output_path

    def append_to_report(self, records: list, filepath: str = None) -> None:
        """
        Append classified email records to the CSV report.

        Creates the file with headers if it doesn't exist.
        Appends cleanly if it does.

        Args:
            records: List of dicts with keys: sender, subject, date, tag
            filepath: Override output path (optional)
        """
        path = filepath or self.output_path

        if not records:
            logger.warning("No records to write to CSV.")
            return

        df_new = pd.DataFrame(records)

        # Ensure all expected columns exist
        for col in COLUMNS:
            if col not in df_new.columns:
                df_new[col] = ""

        # Reorder to match schema
        df_new = df_new[COLUMNS]

        file_exists = os.path.isfile(path)

        if file_exists:
            # Append without writing headers again
            try:
                df_new.to_csv(path, mode="a", header=False, index=False, encoding="utf-8")
                logger.info(f"Appended {len(records)} records to existing '{path}'.")
            except OSError as e:
                logger.error(f"Failed to append to '{path}': {e}")
        else:
            # Create new file with headers
            try:
                # Ensure parent directory exists
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                df_new.to_csv(path, mode="w", header=True, index=False, encoding="utf-8")
                logger.info(f"Created '{path}' with {len(records)} records.")
            except OSError as e:
                logger.error(f"Failed to create '{path}': {e}")
