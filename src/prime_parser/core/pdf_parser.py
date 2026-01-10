"""PDF parser for hydropower plant reports."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pdfplumber
import structlog

from prime_parser.models.domain_models import HydropowerReport, ParsedData, StationData
from prime_parser.utils.exceptions import DataExtractionError, PDFParsingError

logger = structlog.get_logger()


class PDFParser:
    """Parser for hydropower plant PDF reports."""

    # Identifier for the summary row with total energy
    # Using key parts to match, accounting for newlines and formatting variations
    SUMMARY_ROW_KEYWORDS = ["Ўзбекгидроэнерго", "АЖ", "бўйича"]

    # Date pattern: "8.01.2026 й."
    DATE_PATTERN = r"(\d{1,2})\.(\d{2})\.(\d{4})\s*й\."

    def parse_pdf(self, pdf_path: Path) -> HydropowerReport:
        """Parse PDF file and extract hydropower data.

        Args:
            pdf_path: Path to PDF file

        Returns:
            HydropowerReport with parsed data

        Raises:
            PDFParsingError: If PDF cannot be parsed
            DataExtractionError: If required data cannot be extracted
        """
        logger.info("parsing_pdf_started", file_path=str(pdf_path))

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # 1. Extract date from first page
                report_date = self._extract_date(pdf.pages[0])
                logger.info("date_extracted", date=report_date.isoformat())

                # 2. Extract all tables from all pages
                tables = []
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()
                    tables.extend(page_tables)
                    logger.debug(
                        "tables_extracted_from_page",
                        page=page_num,
                        table_count=len(page_tables),
                    )

                # 3. Find summary row with total energy
                total_energy = self._find_total_energy(tables)
                logger.info("total_energy_extracted", energy=str(total_energy))

                # 4. Extract all station data (for future use)
                stations = self._extract_stations(tables)
                logger.debug("stations_extracted", count=len(stations))

                report = HydropowerReport(
                    report_date=report_date,
                    total_daily_energy_million_kwh=total_energy,
                    stations=stations,
                )

                logger.info(
                    "parsing_pdf_completed",
                    date=report_date.isoformat(),
                    total_energy=str(total_energy),
                    stations_count=len(stations),
                )

                return report

        except PDFParsingError:
            raise
        except DataExtractionError:
            raise
        except Exception as e:
            logger.error("pdf_parsing_failed", error=str(e), error_type=type(e).__name__)
            raise PDFParsingError(f"Failed to parse PDF: {e}") from e

    def _extract_date(self, page: Any) -> date:
        """Extract report date from page text.

        Args:
            page: pdfplumber page object

        Returns:
            Extracted date

        Raises:
            DataExtractionError: If date cannot be found or parsed
        """
        try:
            text = page.extract_text()
            if not text:
                raise DataExtractionError("No text found in PDF page")

            # Search for date pattern: "8.01.2026 й."
            match = re.search(self.DATE_PATTERN, text)
            if match:
                day, month, year = match.groups()
                extracted_date = datetime(int(year), int(month), int(day)).date()
                logger.debug(
                    "date_pattern_matched",
                    day=day,
                    month=month,
                    year=year,
                    date=extracted_date.isoformat(),
                )
                return extracted_date

            raise DataExtractionError(
                f"Date pattern not found in PDF. Expected format: '8.01.2026 й.'"
            )

        except ValueError as e:
            raise DataExtractionError(f"Invalid date values extracted: {e}") from e

    def _find_total_energy(self, tables: list[list[list[Any]]]) -> Decimal:
        """Find total energy production from summary row.

        Args:
            tables: List of tables extracted from PDF

        Returns:
            Total daily energy production in million kWh

        Raises:
            DataExtractionError: If summary row not found or energy cannot be parsed
        """
        # Find all GES rows and summary row
        ges_rows = []
        summary_row = None
        summary_row_idx = None

        for table_idx, table in enumerate(tables):
            for row_idx, row in enumerate(table):
                if not row or not row[0]:
                    continue

                first_cell = str(row[0])

                # Collect GES rows (stations)
                if ("ГЭС" in first_cell or "КГЭС" in first_cell) and "Ўзбекгидроэнерго" not in first_cell:
                    ges_rows.append(row)

                # Find summary row
                if all(keyword in first_cell for keyword in self.SUMMARY_ROW_KEYWORDS):
                    summary_row = row
                    summary_row_idx = row_idx
                    logger.debug(
                        "summary_row_found",
                        table_index=table_idx,
                        row_index=row_idx,
                        row_length=len(row),
                    )

        if not summary_row:
            raise DataExtractionError(
                f"Summary row '{' '.join(self.SUMMARY_ROW_KEYWORDS)}' not found in PDF tables"
            )

        # Find the target column by checking which one is the sum of GES rows
        target_col_idx = self._find_sum_column(ges_rows, summary_row)

        if target_col_idx is not None:
            val = self._parse_decimal(summary_row[target_col_idx])
            if val is not None:
                logger.info(
                    "energy_extracted_from_sum_column",
                    col_index=target_col_idx,
                    value=str(val),
                )
                return val

        # Fallback: Scan row for reasonable energy value
        logger.warning("falling_back_to_row_scan")
        energy = self._extract_energy_from_row(summary_row)
        return energy

    def _find_sum_column(self, ges_rows: list[list[Any]], summary_row: list[Any]) -> int | None:
        """Find column where summary value equals sum of GES rows.

        Args:
            ges_rows: List of GES station rows
            summary_row: Summary row with totals

        Returns:
            Column index where sum matches, or None if not found
        """
        # Check columns that might contain energy values (typically 15-25)
        # Energy should be in reasonable range: 0.1 to 1000 million kWh
        MIN_ENERGY = Decimal("0.1")
        MAX_ENERGY = Decimal("1000")

        candidates = []

        for col_idx in range(15, min(26, len(summary_row))):
            cell_raw = str(summary_row[col_idx]).strip() if summary_row[col_idx] else ""

            # Skip columns that are deltas (start with + or -)
            # Energy production is always positive without explicit sign
            if cell_raw.startswith('+') or cell_raw.startswith('-'):
                continue

            summary_val = self._parse_decimal(summary_row[col_idx])
            if summary_val is None:
                continue

            # Check if value is in reasonable range for energy
            if not (MIN_ENERGY <= abs(summary_val) <= MAX_ENERGY):
                continue

            # Skip columns with large integer values (likely aggregates count, not energy)
            # Energy values are typically decimal numbers < 100
            if summary_val == summary_val.to_integral_value() and summary_val > Decimal("50"):
                logger.debug(
                    "skipping_large_integer_column",
                    col_index=col_idx,
                    value=str(summary_val),
                    reason="likely_aggregates_count",
                )
                continue

            # Sum all GES rows for this column
            total = Decimal("0")
            valid_count = 0

            for ges_row in ges_rows:
                if col_idx < len(ges_row):
                    val = self._parse_decimal(ges_row[col_idx])
                    if val is not None:
                        total += val
                        valid_count += 1

            # Check if sum matches (allow small difference for rounding)
            difference = abs(summary_val - total)

            if difference < Decimal("1.0") and valid_count > 0:
                candidates.append({
                    "col_idx": col_idx,
                    "summary_val": summary_val,
                    "total": total,
                    "difference": difference,
                    "valid_count": valid_count,
                })

                logger.debug(
                    "sum_column_candidate",
                    col_index=col_idx,
                    summary_value=str(summary_val),
                    ges_sum=str(total),
                    difference=str(difference),
                    ges_count=valid_count,
                )

        # If we have candidates, pick the one with the smallest difference
        # and value in typical energy range (5-50 million kWh for daily production)
        if candidates:
            # Prefer values in typical range
            typical_candidates = [
                c for c in candidates
                if Decimal("5") <= c["summary_val"] <= Decimal("50")
            ]

            if typical_candidates:
                best = min(typical_candidates, key=lambda x: x["difference"])
            else:
                best = min(candidates, key=lambda x: x["difference"])

            logger.info(
                "sum_column_found",
                col_index=best["col_idx"],
                summary_value=str(best["summary_val"]),
                ges_sum=str(best["total"]),
                difference=str(best["difference"]),
            )
            return best["col_idx"]

        logger.warning("sum_column_not_found")
        return None

    def _parse_decimal(self, value: Any) -> Decimal | None:
        """Parse decimal from string, handling commmas and whitespace."""
        if value is None:
            return None
        
        s = str(value).strip()
        if not s or s in ["-", "—", ""]:
            return None
            
        try:
            # Replace comma with dot
            normalized = s.replace(",", ".")
            # Remove non-numeric chars except dot and minus
            cleaned = re.sub(r"[^\d\.\-]", "", normalized)
            if not cleaned:
                return None
            return Decimal(cleaned)
        except (ValueError, InvalidOperation):
            return None

    def _extract_energy_from_row(self, row: list[Any]) -> Decimal:
        """Extract energy value from summary row.

        Args:
            row: Table row containing summary data

        Returns:
            Energy value as Decimal

        Raises:
            DataExtractionError: If energy value cannot be found
        """
        # Try to find energy value in the row
        # Energy is typically in format: "81.03" or "81,03"
        for cell_idx, cell in enumerate(row):
            val = self._parse_decimal(cell)
            if val is None:
                continue

            # Energy values are typically between 0.01 and 1000 million kWh
            # Check if this looks like a reasonable energy value
            if Decimal("0.01") <= abs(val) <= Decimal("1000"):
                # Additional check: for summary row, energy should be in a specific range
                # Total for Uzbekgidroenergo is typically 20-200 million kWh per day
                if Decimal("10") <= abs(val) <= Decimal("200"):
                    logger.debug(
                        "energy_value_extracted_fallback",
                        cell_index=cell_idx,
                        raw_value=str(cell),
                        parsed_value=str(val),
                    )
                    return val

        raise DataExtractionError(
            f"Could not extract energy value from summary row. Row data: {row}"
        )

    def _extract_stations(self, tables: list[list[list[Any]]]) -> list[StationData]:
        """Extract all station data from tables.

        Args:
            tables: List of tables extracted from PDF

        Returns:
            List of station data (currently returns empty list - for future implementation)
        """
        # TODO: Implement full station data extraction
        # For now, we only extract total energy, so return empty list
        return []

    def to_parsed_data(self, report: HydropowerReport) -> ParsedData:
        """Convert HydropowerReport to ParsedData for API response.

        Args:
            report: Full hydropower report

        Returns:
            Simplified parsed data for API
        """
        return ParsedData(
            date=report.report_date,
            total_energy_production=report.total_daily_energy_million_kwh,
        )
