import io

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests import RequestException


class FundDataError(Exception):
    """Raised when AdvisorKhoj fund data cannot be retrieved."""

    pass


class MarketCaptureScraper:
    def __init__(self):
        self.url = (
            "https://www.advisorkhoj.com/"
            "mutual-funds-research/market-capture-ratio"
        )

        self.autocomplete_url = (
            "https://www.advisorkhoj.com/"
            "mutual-funds-research/"
            "autoSuggestAllMfSchemesShortNames"
        )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/154.0.0.0 Safari/537.36"
                )
            }
        )

        self.allowed_periods = {"1", "3", "5", "10"}
        self.timeout = 20

    # ============================================================
    # 1. VALIDATE PERIOD
    # ============================================================

    def validate_period(self, period):
        period = str(period).strip()

        if period not in self.allowed_periods:
            raise ValueError(
                f"Invalid period '{period}'. "
                "Allowed periods are: 1, 3, 5, 10."
            )

        return period

    # ============================================================
    # 2. VALIDATE FUND SELECTION
    # ============================================================

    def validate_fund_selection(self, funds):
        if not isinstance(funds, list):
            raise ValueError("Funds must be provided as a list.")

        if len(funds) < 2:
            raise ValueError("At least 2 funds must be selected.")

        if len(funds) > 10:
            raise ValueError("A maximum of 10 funds can be selected.")

        seen = set()

        for index, fund in enumerate(funds, start=1):
            if not isinstance(fund, dict):
                raise ValueError(
                    f"Fund #{index} must be a dictionary."
                )

            category = str(fund.get("category", "")).strip()
            scheme = str(fund.get("scheme", "")).strip()

            if not category:
                raise ValueError(
                    f"Fund #{index} is missing category."
                )

            if not scheme:
                raise ValueError(
                    f"Fund #{index} is missing scheme name."
                )

            duplicate_key = (
                category.lower(),
                scheme.lower(),
            )

            if duplicate_key in seen:
                raise ValueError(
                    f"Duplicate fund selected: '{scheme}'."
                )

            seen.add(duplicate_key)

        return True

    # ============================================================
    # 3. FETCH MULTIPLE FUNDS
    # ============================================================

    def fetch_multiple_ratios(self, funds, period="3"):
        self.validate_period(period)
        self.validate_fund_selection(funds)

        results = []

        for fund in funds:
            category = str(fund["category"]).strip()
            scheme = str(fund["scheme"]).strip()

            try:
                record = self.fetch_ratios(
                    category_value=category,
                    scheme_value=scheme,
                    period=period,
                )

                results.append(self.normalize_record(record))

            except FundDataError as exc:
                raise FundDataError(
                    f"Unable to retrieve '{scheme}' "
                    f"for the {period}-year period. "
                    f"Reason: {exc}"
                ) from exc

        return results

    # ============================================================
    # 4. NORMALIZE ONE RECORD
    # ============================================================

    def normalize_record(self, record):
        required_fields = {
            "Scheme Name",
            "AMC Name",
            "Benchmark Name",
            "Launch Date",
            "Scheme Return (%)",
            "Up Market Capture Ratio (%)",
            "Down Market Capture Ratio (%)",
            "Capture Ratio",
        }

        missing = required_fields - set(record.keys())

        if missing:
            raise FundDataError(
                "AdvisorKhoj returned incomplete data. "
                f"Missing fields: {sorted(missing)}"
            )

        try:
            return {
                "scheme_name": str(record["Scheme Name"]).strip(),
                "amc_name": str(record["AMC Name"]).strip(),
                "benchmark_name": str(record["Benchmark Name"]).strip(),
                "launch_date": str(record["Launch Date"]).strip(),
                "scheme_return": float(record["Scheme Return (%)"]),
                "up_capture": float(
                    record["Up Market Capture Ratio (%)"]
                ),
                "down_capture": float(
                    record["Down Market Capture Ratio (%)"]
                ),
                "capture_ratio": float(record["Capture Ratio"]),
            }
        except (TypeError, ValueError) as exc:
            raise FundDataError(
                "Invalid numeric data returned for "
                f"'{record.get('Scheme Name', 'Unknown Fund')}'."
            ) from exc

    # ============================================================
    # 5. NORMALIZE MULTIPLE RECORDS
    # ============================================================

    def normalize_records(self, records):
        if not isinstance(records, list):
            raise ValueError("Records must be provided as a list.")

        return [self.normalize_record(record) for record in records]

    # ============================================================
    # 6. FETCH MARKET CAPTURE DATA
    # ============================================================

    def fetch_ratios(
        self,
        category_value,
        scheme_value,
        period="3",
    ):
        """
        Fetch one fund's Market Capture Ratio from AdvisorKhoj.

        IMPORTANT:
        AdvisorKhoj expects the market-capture request as query
        parameters using the names:
            category
            period
            schemes

        The original implementation sent `scheme` in a POST body.
        That is why the site could return its default fund while the
        requested fund was ignored.
        """
        period = self.validate_period(period)
        category_value = str(category_value).strip()
        scheme_value = str(scheme_value).strip()

        if not category_value:
            raise ValueError("Category cannot be empty.")

        if not scheme_value:
            raise ValueError("Scheme name cannot be empty.")

        params = {
            "category": category_value,
            "period": period,
            "schemes": scheme_value,
        }

        try:
            response = self.session.get(
                self.url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise FundDataError(
                f"AdvisorKhoj request failed for '{scheme_value}'."
            ) from exc

        try:
            tables = pd.read_html(io.StringIO(response.text))
        except ValueError as exc:
            raise FundDataError(
                f"AdvisorKhoj did not return an HTML table for "
                f"'{scheme_value}'."
            ) from exc

        required_columns = {
            "Scheme Name",
            "AMC Name",
            "Benchmark Name",
            "Launch Date",
            "Scheme Return (%)",
            "Up Market Capture Ratio (%)",
            "Down Market Capture Ratio (%)",
            "Capture Ratio",
        }

        for dataframe in tables:
            columns = set(dataframe.columns)

            if not required_columns.issubset(columns):
                continue

            records = dataframe.to_dict(orient="records")

            # Exact scheme match first.
            target = scheme_value.casefold()

            for row in records:
                row_scheme = str(
                    row.get("Scheme Name", "")
                ).strip()

                if row_scheme.casefold() == target:
                    return row

            # Safe fallback for minor formatting differences.
            for row in records:
                row_scheme = str(
                    row.get("Scheme Name", "")
                ).strip()

                if target in row_scheme.casefold():
                    return row

            returned_schemes = [
                str(row.get("Scheme Name", "")).strip()
                for row in records
            ]

            raise FundDataError(
                f"AdvisorKhoj returned capture data, but the requested "
                f"scheme '{scheme_value}' was not present in the result. "
                f"Returned schemes: {returned_schemes}"
            )

        raise FundDataError(
            f"No Market Capture Ratio table was generated for "
            f"'{scheme_value}'."
        )

    # ============================================================
    # 7. GET CATEGORIES
    # ============================================================

    def get_categories(self):
        try:
            response = self.session.get(
                self.url,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except RequestException as exc:
            raise FundDataError(
                "Unable to retrieve AdvisorKhoj categories."
            ) from exc

        soup = BeautifulSoup(response.text, "html.parser")
        categories = []

        category_select = soup.find(
            "select",
            {"id": "sel_schemeCategories"},
        )

        if not category_select:
            return categories

        for option in category_select.find_all("option"):
            value = option.get("value")
            label = option.get_text(strip=True)

            if value and value.strip():
                categories.append(
                    {
                        "value": value.strip(),
                        "label": label,
                    }
                )

        return categories

    # ============================================================
    # 8. FUND AUTOCOMPLETE
    # ============================================================

    def suggest_funds(
        self,
        query,
        category="Equity: Large Cap",
    ):
        payload = {
            "query": str(query).strip(),
            "category": str(category).strip(),
        }

        try:
            response = self.session.post(
                self.autocomplete_url,
                data=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                return data

            return []

        except (RequestException, ValueError):
            return []

    # ============================================================
    # 9. RESOLVE USER ENTERED FUND NAME
    # ============================================================

    def resolve_scheme_name(self, query, category):
        """
        Resolve a typed fund name to the canonical AdvisorKhoj
        scheme name when autocomplete has a matching value.
        """
        query = str(query).strip()
        category = str(category).strip()

        if not query:
            raise ValueError("Fund name cannot be empty.")

        suggestions = self.suggest_funds(
            query=query,
            category=category,
        )

        cleaned = [
            str(item).strip()
            for item in suggestions
            if str(item).strip()
        ]

        target = query.casefold()

        for item in cleaned:
            if item.casefold() == target:
                return item

        if cleaned:
            return cleaned[0]

        return query


# ================================================================
# EXAMPLE USAGE
# ================================================================

# if __name__ == "__main__":
#     scraper = MarketCaptureScraper()

#     # 1. Categories
#     categories = scraper.get_categories()
#     print("First 3 categories:")
#     print(categories[:3])

#     # 2. Autocomplete
#     suggestions = scraper.suggest_funds(
#         query="Baroda BNP Paribas Multi Cap Reg Gr",
#         category="Equity: Multi Cap",
#     )
#     print("\nSuggestions:")
#     print(suggestions)

#     # 3. Fetch market capture data.
#     #    This now uses AdvisorKhoj parameters:
#     #    category + period + schemes
#     try:
#         data = scraper.fetch_ratios(
#             category_value="Equity: Multi Cap",
#             scheme_value="Baroda BNP Paribas Multi Cap Reg Gr",
#             period="10",
#         )
#         print("\nMarket Capture Data:")
#         print(data)

#     except FundDataError as exc:
#         print(f"\nERROR: {exc}")
