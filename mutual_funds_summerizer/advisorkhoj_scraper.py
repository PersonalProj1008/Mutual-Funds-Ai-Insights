import requests
from bs4 import BeautifulSoup
import pandas as pd
import io


class FundDataError(Exception):
    """Custom exception raised when fund data is unavailable."""
    pass


class MarketCaptureScraper:

    def __init__(self):
        self.url = (
            "https://www.advisorkhoj.com/"
            "mutual-funds-research/market-capture-ratio"
        )

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/154.0.0.0 Safari/537.36"
            )
        })

        self.allowed_periods = {"1", "3", "5", "10"}

    # ============================================================
    # 1. VALIDATE PERIOD
    # ============================================================

    def validate_period(self, period):
        """
        Validate that the requested analysis period is supported.

        Supported:
            1 year
            3 years
            5 years
            10 years
        """

        period = str(period).strip()

        if period not in self.allowed_periods:
            raise ValueError(
                f"Invalid period '{period}'. "
                f"Allowed periods are: 1, 3, 5, 10."
            )

        return period

    # ============================================================
    # 2. VALIDATE FUND SELECTION
    # ============================================================

    def validate_fund_selection(self, funds):
        """
        Validate a list of selected funds.

        Expected format:

        [
            {
                "category": "Equity: Large Cap",
                "scheme": "Mirae Asset Large Cap Gr"
            },
            {
                "category": "Equity: Flexi Cap",
                "scheme": "Parag Parikh Flexi Cap Gr"
            }
        ]
        """

        if not isinstance(funds, list):
            raise ValueError("Funds must be provided as a list.")

        if len(funds) < 2:
            raise ValueError(
                "At least 2 funds must be selected."
            )

        if len(funds) > 10:
            raise ValueError(
                "A maximum of 10 funds can be selected."
            )

        seen = set()

        for index, fund in enumerate(funds, start=1):

            if not isinstance(fund, dict):
                raise ValueError(
                    f"Fund #{index} must be a dictionary."
                )

            category = str(
                fund.get("category", "")
            ).strip()

            scheme = str(
                fund.get("scheme", "")
            ).strip()

            if not category:
                raise ValueError(
                    f"Fund #{index} is missing category."
                )

            if not scheme:
                raise ValueError(
                    f"Fund #{index} is missing scheme name."
                )

            # Prevent duplicate funds
            duplicate_key = (
                category.lower(),
                scheme.lower()
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
        """
        Fetch AdvisorKhoj Market Capture Ratio data
        for multiple selected funds.

        Returns a list of normalized fund dictionaries.
        """

        self.validate_period(period)
        self.validate_fund_selection(funds)

        results = []

        for fund in funds:

            category = fund["category"].strip()
            scheme = fund["scheme"].strip()

            try:
                record = self.fetch_ratios(
                    category_value=category,
                    scheme_value=scheme,
                    period=period
                )

                normalized = self.normalize_record(record)

                results.append(normalized)

            except FundDataError as exc:

                # Preserve which fund failed
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
        """
        Convert AdvisorKhoj column names into
        clean internal field names.
        """

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
            normalized = {
                "scheme_name": str(
                    record["Scheme Name"]
                ).strip(),

                "amc_name": str(
                    record["AMC Name"]
                ).strip(),

                "benchmark_name": str(
                    record["Benchmark Name"]
                ).strip(),

                "launch_date": str(
                    record["Launch Date"]
                ).strip(),

                "scheme_return": float(
                    record["Scheme Return (%)"]
                ),

                "up_capture": float(
                    record["Up Market Capture Ratio (%)"]
                ),

                "down_capture": float(
                    record["Down Market Capture Ratio (%)"]
                ),

                "capture_ratio": float(
                    record["Capture Ratio"]
                ),
            }

        except (TypeError, ValueError) as exc:
            raise FundDataError(
                f"Invalid numeric data returned for "
                f"'{record.get('Scheme Name', 'Unknown Fund')}'."
            ) from exc

        return normalized

    # ============================================================
    # 5. NORMALIZE MULTIPLE RECORDS
    # ============================================================

    def normalize_records(self, records):
        """
        Normalize a list of AdvisorKhoj records.
        """

        if not isinstance(records, list):
            raise ValueError("Records must be a list.")

        return [
            self.normalize_record(record)
            for record in records
        ]

    # ============================================================
    # EXISTING FUNCTIONS
    # ============================================================

    def fetch_ratios(
        self,
        category_value,
        scheme_value,
        period="3"
    ):

        self.validate_period(period)

        res = self.session.get(
            self.url,
            timeout=20
        )
        res.raise_for_status()

        soup = BeautifulSoup(
            res.text,
            "html.parser"
        )

        payload = {}

        form = soup.find("form")

        if form:
            for hidden in form.find_all(
                "input",
                type="hidden"
            ):
                name = hidden.get("name")

                if name:
                    payload[name] = hidden.get("value")

        payload["category"] = category_value
        payload["scheme"] = scheme_value
        payload["period"] = period

        post_res = self.session.post(
            self.url,
            data=payload,
            timeout=20
        )

        post_res.raise_for_status()

        try:

            tables = pd.read_html(
                io.StringIO(post_res.text)
            )

            required_columns = {
                "Scheme Name",
                "Up Market Capture Ratio (%)",
                "Down Market Capture Ratio (%)",
                "Capture Ratio",
            }

            for df in tables:

                if required_columns.issubset(
                    set(df.columns)
                ):

                    records = df.to_dict(
                        orient="records"
                    )

                    # Find the exact requested scheme
                    for row in records:

                        row_scheme_name = str(
                            row.get(
                                "Scheme Name",
                                ""
                            )
                        ).strip()

                        if (
                            row_scheme_name.lower()
                            == scheme_value.strip().lower()
                        ):
                            return row

                    # Fallback: partial matching
                    for row in records:

                        row_scheme_name = str(
                            row.get(
                                "Scheme Name",
                                ""
                            )
                        ).strip()

                        if (
                            scheme_value.lower()
                            in row_scheme_name.lower()
                        ):
                            return row

                    raise FundDataError(
                        f"'{scheme_value}' was found, "
                        f"but its market capture data "
                        f"is unavailable for the "
                        f"{period}-year period."
                    )

            raise FundDataError(
                f"No capture ratio table generated "
                f"for '{scheme_value}'."
            )

        except ValueError as exc:

            raise FundDataError(
                f"Failed to retrieve data for "
                f"'{scheme_value}'. "
                f"The fund may not have sufficient "
                f"{period}-year history."
            ) from exc

    def get_categories(self):

        res = self.session.get(
            self.url,
            timeout=20
        )
        res.raise_for_status()

        soup = BeautifulSoup(
            res.text,
            "html.parser"
        )

        categories = []

        category_select = soup.find(
            "select",
            {
                "id": "sel_schemeCategories"
            }
        )

        if category_select:

            for option in category_select.find_all(
                "option"
            ):

                val = option.get("value")
                label = option.text.strip()

                if val and val.strip():

                    categories.append({
                        "value": val.strip(),
                        "label": label
                    })

        return categories

    def suggest_funds(
        self,
        query,
        category="Equity: Large Cap"
    ):

        ajax_url = (
            "https://www.advisorkhoj.com/"
            "mutual-funds-research/"
            "autoSuggestAllMfSchemesShortNames"
        )

        payload = {
            "query": query,
            "category": category
        }

        try:

            res = self.session.post(
                ajax_url,
                data=payload,
                timeout=20
            )

            res.raise_for_status()

            return res.json()

        except Exception as exc:

            print(
                f"Error fetching suggestions "
                f"for '{query}': {exc}"
            )

            return []


#  --------- E X A M P L E   U S A G E ---------

if __name__ == "__main__":
    scraper = MarketCaptureScraper()
    
    # Get all categories available
    all_categories = scraper.get_categories()
    print(all_categories[:3])

    # Get Fund Scheme name suggestions
    results = scraper.suggest_funds(query="Mir", category="Equity: Large Cap")
    print(results)


    # Get the ratios
    data = scraper.fetch_ratios(
        category_value="Equity: Large Cap", 
        scheme_value="MiraE Asset Large Cap Gr", 
        period="5"
    )

    print(data)

# ########################################################
#  Output data formats are as follows:
# ########################################################

# [{'value': 'Equity: Contra', 'label': 'Equity: Contra'}, {'value': 'Equity: Dividend Yield', 'label': 'Equity: Dividend Yield'}, {'value': 'Equity: ELSS', 'label': 'Equity: ELSS'}]
# ['Mirae Asset Large Cap Dir Gr', 'Mirae Asset Large Cap Gr']
# [{'Scheme Name': 'Mirae Asset Large Cap Gr', 'AMC Name': 'MiraeMF', 'Benchmark Name': 'Nifty 100 TRI', 'Launch Date': '01-04-2008', 'Scheme Return (%)': 6.03, 'Up Market Capture Ratio (%)': 90.0, 'Down Market Capture Ratio (%)': 94.0, 'Capture Ratio': 0.96}]