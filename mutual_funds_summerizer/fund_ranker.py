# mutual_funds_summerizer/fund_ranker.py

from typing import Any, Dict, List, Sequence


class RankingError(Exception):
    """Raised when fund ranking cannot be performed."""
    pass


class FundRanker:
    """
    Mutual-fund ranking engine.
    The ranker uses transparent rules based on the data
    retrieved from AdvisorKhoj.

    Investor lenses:

        1. defensive
           Protect my downside
           LOWER Down Market Capture = BETTER

        2. balanced
           Balance growth & protection
           HIGHER (Up Capture - Down Capture) = BETTER

        3. growth
           Maximize upside
           HIGHER Up Market Capture = BETTER

        4. capture_efficiency
           Capture efficiency
           HIGHER Capture Ratio = BETTER

        5. historical_return
           Maximize historical returns
           HIGHER Scheme Return = BETTER

    This class determines the ranking.
    The LLM should later explain in humanly-words rather independently deciding which fund ranks first.
    """

    # ============================================================
    # SUPPORTED PREFERENCES
    # ============================================================

    PREFERENCES = [
        "defensive",
        "balanced",
        "growth",
        "capture_efficiency",
        "historical_return",
    ]

    PREFERENCE_LABELS = {
        "defensive": "Protect my downside",
        "balanced": "Balance growth & protection",
        "growth": "Maximize upside",
        "capture_efficiency": "Maximize capture efficiency",
        "historical_return": "Maximize historical returns",
    }

    PREFERENCE_DESCRIPTIONS = {
        "defensive": (
            "Prioritizes funds with lower historical participation "
            "in benchmark downturns."
        ),
        "balanced": (
            "Prioritizes funds with a stronger difference between "
            "upside participation and downside participation."
        ),
        "growth": (
            "Prioritizes funds with stronger historical participation "
            "during rising benchmark periods."
        ),
        "capture_efficiency": (
            "Prioritizes funds with a higher Capture Ratio, representing "
            "a stronger relationship between upside and downside capture."
        ),
        "historical_return": (
            "Prioritizes funds with higher reported Scheme Return "
            "over the selected analysis period."
        ),
    }

    # ============================================================
    # REQUIRED FUND FIELDS
    # ============================================================

    REQUIRED_FIELDS = {
        "scheme_name",
        "amc_name",
        "benchmark_name",
        "launch_date",
        "scheme_return",
        "up_capture",
        "down_capture",
        "capture_ratio",
    }

    # ============================================================
    # PUBLIC METHODS
    # ============================================================

    def get_supported_preferences(self) -> List[Dict[str, str]]:
        """
        Return all supported investor preferences.
        This can directly be used by the frontend/API.
        """

        preferences = []

        for preference in self.PREFERENCES:

            preferences.append(
                {
                    "value": preference,
                    "label": self.PREFERENCE_LABELS[preference],
                    "description": self.PREFERENCE_DESCRIPTIONS[
                        preference
                    ],
                }
            )

        return preferences

    # ============================================================

    def rank_funds(
        self,
        funds: Sequence[Dict[str, Any]],
        preference: str = "balanced",
    ) -> List[Dict[str, Any]]:
        """
        Rank 2 to 10 funds according to the selected preference.

        The returned list is ordered from Rank 1 to Rank N.
        """

        self.validate_preference(preference)
        self.validate_funds(funds)

        prepared_funds = self.prepare_funds(funds)

        # Capture spread is used by the balanced lens.
        for fund in prepared_funds:

            fund["capture_spread"] = round(
                fund["up_capture"] - fund["down_capture"],
                4,
            )

        # --------------------------------------------------------
        # Select ranking rule
        # --------------------------------------------------------

        if preference == "defensive":

            ranked = self.rank_defensive(
                prepared_funds
            )

        elif preference == "balanced":

            ranked = self.rank_balanced(
                prepared_funds
            )

        elif preference == "growth":

            ranked = self.rank_growth(
                prepared_funds
            )

        elif preference == "capture_efficiency":

            ranked = self.rank_capture_efficiency(
                prepared_funds
            )

        elif preference == "historical_return":

            ranked = self.rank_historical_return(
                prepared_funds
            )

        else:

            raise RankingError(
                f"Unsupported preference: {preference}"
            )

        # --------------------------------------------------------
        # Add ranking information
        # --------------------------------------------------------

        results = []

        for index, fund in enumerate(
            ranked,
            start=1,
        ):

            result = dict(fund)

            result["rank"] = index

            result["preference"] = preference

            result["preference_label"] = (
                self.PREFERENCE_LABELS[preference]
            )

            result["ranking_basis"] = (
                self.get_ranking_basis(
                    fund,
                    preference,
                )
            )

            result["characteristics"] = (
                self.get_fund_characteristics(fund)
            )

            results.append(result)

        return results

    # ============================================================

    def rank_all_preferences(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate rankings under every supported investor lens.

        This is useful for generating a single report that shows
        different ways of interpreting the same selected funds.
        """

        self.validate_funds(funds)

        rankings = {}

        for preference in self.PREFERENCES:

            rankings[preference] = self.rank_funds(
                funds=funds,
                preference=preference,
            )

        return rankings

    # ============================================================
    # INDIVIDUAL RANKING RULES
    # ============================================================

    def rank_defensive(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Defensive ranking.

        Rule:
            LOWER Down Market Capture = BETTER

        Example:
            Fund A = 80%
            Fund B = 110%
            Fund C = 70%

            C > A > B

        Tie breakers:
            1. Higher Capture Ratio
            2. Higher Up Market Capture
            3. Alphabetical scheme name
        """

        return sorted(
            funds,
            key=lambda fund: (
                fund["down_capture"],
                -fund["capture_ratio"],
                -fund["up_capture"],
                fund["scheme_name"].lower(),
            ),
        )

    # ============================================================

    def rank_balanced(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Balanced ranking.

        Rule:

            Capture Spread =
                Up Capture - Down Capture

            HIGHER Capture Spread = BETTER

        Example:

            Fund A:
                Up = 120
                Down = 80
                Spread = 40

            Fund B:
                Up = 130
                Down = 110
                Spread = 20

            Fund C:
                Up = 105
                Down = 70
                Spread = 35

            Result:

                A > C > B

        Tie breakers:
            1. Higher Capture Ratio
            2. Lower Down Market Capture
            3. Higher Up Market Capture
            4. Alphabetical scheme name
        """

        return sorted(
            funds,
            key=lambda fund: (
                -fund["capture_spread"],
                -fund["capture_ratio"],
                fund["down_capture"],
                -fund["up_capture"],
                fund["scheme_name"].lower(),
            ),
        )

    # ============================================================

    def rank_growth(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Growth ranking.

        Rule:
            HIGHER Up Market Capture = BETTER

        Tie breakers:
            1. Higher Capture Ratio
            2. Lower Down Market Capture
            3. Alphabetical scheme name
        """

        return sorted(
            funds,
            key=lambda fund: (
                -fund["up_capture"],
                -fund["capture_ratio"],
                fund["down_capture"],
                fund["scheme_name"].lower(),
            ),
        )

    # ============================================================

    def rank_capture_efficiency(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Capture Efficiency ranking.

        Rule:
            HIGHER Capture Ratio = BETTER

        Capture Ratio is taken directly from AdvisorKhoj.

        We do not independently recalculate the value.

        Tie breakers:
            1. Higher Up Market Capture
            2. Lower Down Market Capture
            3. Alphabetical scheme name
        """

        return sorted(
            funds,
            key=lambda fund: (
                -fund["capture_ratio"],
                -fund["up_capture"],
                fund["down_capture"],
                fund["scheme_name"].lower(),
            ),
        )

    # ============================================================

    def rank_historical_return(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Historical Return ranking.

        Rule:
            HIGHER Scheme Return = BETTER

        Important:
            This represents historical performance over the
            selected period. It is NOT a prediction of future
            returns.

        Tie breakers:
            1. Higher Capture Ratio
            2. Lower Down Market Capture
            3. Higher Up Market Capture
            4. Alphabetical scheme name
        """

        return sorted(
            funds,
            key=lambda fund: (
                -fund["scheme_return"],
                -fund["capture_ratio"],
                fund["down_capture"],
                -fund["up_capture"],
                fund["scheme_name"].lower(),
            ),
        )

    # ============================================================
    # VALIDATION
    # ============================================================

    def validate_preference(
        self,
        preference: str,
    ) -> None:
        """
        Validate investor preference.
        """

        if preference not in self.PREFERENCES:

            raise RankingError(
                f"Unsupported preference '{preference}'. "
                f"Supported preferences: "
                f"{', '.join(self.PREFERENCES)}"
            )

    # ============================================================

    def validate_funds(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> None:
        """
        Validate the complete comparison set.

        The assignment allows 2 to 10 funds.
        """

        if not isinstance(
            funds,
            (list, tuple),
        ):

            raise RankingError(
                "Funds must be provided as a list or tuple."
            )

        if len(funds) < 2:

            raise RankingError(
                "At least 2 funds are required for ranking."
            )

        if len(funds) > 10:

            raise RankingError(
                "A maximum of 10 funds can be ranked."
            )

        for fund in funds:

            self.validate_fund(fund)

        # --------------------------------------------------------
        # Duplicate detection
        # --------------------------------------------------------

        scheme_names = []

        for fund in funds:

            scheme_name = str(
                fund["scheme_name"]
            ).strip().lower()

            scheme_names.append(
                scheme_name
            )

        if len(scheme_names) != len(
            set(scheme_names)
        ):

            raise RankingError(
                "Duplicate funds detected in the comparison set."
            )

    # ============================================================

    def validate_fund(
        self,
        fund: Dict[str, Any],
    ) -> None:
        """
        Validate one normalized fund record.
        """

        if not isinstance(
            fund,
            dict,
        ):

            raise RankingError(
                "Every fund must be provided as a dictionary."
            )

        missing_fields = (
            self.REQUIRED_FIELDS
            - set(fund.keys())
        )

        if missing_fields:

            raise RankingError(
                "Fund data is missing required fields: "
                + ", ".join(
                    sorted(missing_fields)
                )
            )

        scheme_name = str(
            fund["scheme_name"]
        ).strip()

        if not scheme_name:

            raise RankingError(
                "Fund scheme name cannot be empty."
            )

        numeric_fields = [
            "scheme_return",
            "up_capture",
            "down_capture",
            "capture_ratio",
        ]

        for field in numeric_fields:

            value = fund[field]

            try:

                float(value)

            except (
                TypeError,
                ValueError,
            ) as exc:

                raise RankingError(
                    f"Fund '{scheme_name}' contains "
                    f"invalid value for '{field}': {value}"
                ) from exc

    # ============================================================
    # DATA PREPARATION
    # ============================================================

    def prepare_funds(
        self,
        funds: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Create clean copies of fund records.

        Numeric fields are converted to float.
        """

        prepared = []

        for fund in funds:

            self.validate_fund(fund)

            cleaned = dict(fund)

            cleaned["scheme_name"] = str(
                cleaned["scheme_name"]
            ).strip()

            cleaned["amc_name"] = str(
                cleaned["amc_name"]
            ).strip()

            cleaned["benchmark_name"] = str(
                cleaned["benchmark_name"]
            ).strip()

            cleaned["launch_date"] = str(
                cleaned["launch_date"]
            ).strip()

            cleaned["scheme_return"] = float(
                cleaned["scheme_return"]
            )

            cleaned["up_capture"] = float(
                cleaned["up_capture"]
            )

            cleaned["down_capture"] = float(
                cleaned["down_capture"]
            )

            cleaned["capture_ratio"] = float(
                cleaned["capture_ratio"]
            )

            prepared.append(cleaned)

        return prepared

    # ============================================================
    # RANKING BASIS
    # ============================================================

    def get_ranking_basis(
        self,
        fund: Dict[str, Any],
        preference: str,
    ) -> Dict[str, Any]:
        """
        Return structured information explaining the mathematical
        basis for the fund's ranking.

        This information can later be passed to the LLM.
        """

        self.validate_preference(preference)

        if preference == "defensive":

            return {
                "primary_metric": "down_capture",
                "direction": "lower_is_better",
                "value": fund["down_capture"],
                "display": (
                    "Down Market Capture: "
                    f"{fund['down_capture']:.2f}%"
                ),
                "logic": (
                    "Lower Down Market Capture indicates stronger "
                    "historical downside protection."
                ),
            }

        if preference == "balanced":

            return {
                "primary_metric": "capture_spread",
                "direction": "higher_is_better",
                "value": fund["capture_spread"],
                "display": (
                    "Capture Spread: "
                    f"{fund['capture_spread']:.2f}"
                ),
                "formula": (
                    "Up Market Capture - Down Market Capture"
                ),
                "up_capture": fund["up_capture"],
                "down_capture": fund["down_capture"],
                "logic": (
                    "Higher Capture Spread indicates a stronger "
                    "difference between upside participation and "
                    "downside participation."
                ),
            }

        if preference == "growth":

            return {
                "primary_metric": "up_capture",
                "direction": "higher_is_better",
                "value": fund["up_capture"],
                "display": (
                    "Up Market Capture: "
                    f"{fund['up_capture']:.2f}%"
                ),
                "logic": (
                    "Higher Up Market Capture indicates stronger "
                    "historical participation during rising "
                    "benchmark periods."
                ),
            }

        if preference == "capture_efficiency":

            return {
                "primary_metric": "capture_ratio",
                "direction": "higher_is_better",
                "value": fund["capture_ratio"],
                "display": (
                    "Capture Ratio: "
                    f"{fund['capture_ratio']:.2f}"
                ),
                "logic": (
                    "Higher Capture Ratio indicates stronger "
                    "upside participation relative to downside "
                    "participation."
                ),
            }

        if preference == "historical_return":

            return {
                "primary_metric": "scheme_return",
                "direction": "higher_is_better",
                "value": fund["scheme_return"],
                "display": (
                    "Scheme Return: "
                    f"{fund['scheme_return']:.2f}%"
                ),
                "logic": (
                    "Higher Scheme Return indicates higher reported "
                    "historical return over the selected period."
                ),
            }

        raise RankingError(
            f"Unsupported preference: {preference}"
        )

    # ============================================================
    # FUND CHARACTERISTICS
    # ============================================================

    def get_fund_characteristics(
        self,
        fund: Dict[str, Any],
    ) -> List[str]:
        """
        Produce rule-based observations about a fund.

        These are factual interpretations of the supplied metrics.

        The LLM can later turn these facts into polished prose.
        """

        self.validate_fund(fund)

        observations = []

        up_capture = float(
            fund["up_capture"]
        )

        down_capture = float(
            fund["down_capture"]
        )

        capture_ratio = float(
            fund["capture_ratio"]
        )

        scheme_return = float(
            fund["scheme_return"]
        )

        # --------------------------------------------------------
        # Upside
        # --------------------------------------------------------

        if up_capture > 100:

            observations.append(
                "Captured more than 100% of benchmark upside."
            )

        elif up_capture == 100:

            observations.append(
                "Captured approximately 100% of benchmark upside."
            )

        else:

            observations.append(
                "Captured less than 100% of benchmark upside."
            )

        # --------------------------------------------------------
        # Downside
        # --------------------------------------------------------

        if down_capture < 0:

            observations.append(
                "Has a negative Down Market Capture Ratio, "
                "indicating exceptionally favorable historical "
                "behavior during benchmark down periods."
            )

        elif down_capture < 100:

            observations.append(
                "Captured less than 100% of benchmark downside."
            )

        elif down_capture == 100:

            observations.append(
                "Captured approximately 100% of benchmark downside."
            )

        else:

            observations.append(
                "Captured more than 100% of benchmark downside."
            )

        # --------------------------------------------------------
        # Capture Ratio
        # --------------------------------------------------------

        if capture_ratio > 1:

            observations.append(
                "Has a Capture Ratio above 1."
            )

        elif capture_ratio == 1:

            observations.append(
                "Has a Capture Ratio of approximately 1."
            )

        else:

            observations.append(
                "Has a Capture Ratio below 1."
            )

        # --------------------------------------------------------
        # Scheme Return
        # --------------------------------------------------------

        if scheme_return > 0:

            observations.append(
                "Reported a positive historical Scheme Return "
                "for the selected analysis period."
            )

        elif scheme_return == 0:

            observations.append(
                "Reported a zero Scheme Return for the selected "
                "analysis period."
            )

        else:

            observations.append(
                "Reported a negative historical Scheme Return "
                "for the selected analysis period."
            )

        return observations

    # ============================================================
    # COMPARISON SUMMARY
    # ============================================================

    def build_comparison_summary(
        self,
        ranked_funds: Sequence[Dict[str, Any]],
        preference: str,
    ) -> Dict[str, Any]:
        """
        Build a compact summary of a ranking.

        Useful for:
            - AI analyzer
            - PDF generator
            - API response
        """

        self.validate_preference(preference)

        if not ranked_funds:

            raise RankingError(
                "Cannot build comparison summary from empty ranking."
            )

        top_fund = ranked_funds[0]

        bottom_fund = ranked_funds[-1]

        return {
            "preference": preference,
            "preference_label": self.PREFERENCE_LABELS[
                preference
            ],
            "preference_description": (
                self.PREFERENCE_DESCRIPTIONS[
                    preference
                ]
            ),
            "winner": {
                "scheme_name": top_fund["scheme_name"],
                "rank": top_fund["rank"],
                "ranking_basis": top_fund["ranking_basis"],
                "scheme_return": top_fund["scheme_return"],
                "up_capture": top_fund["up_capture"],
                "down_capture": top_fund["down_capture"],
                "capture_ratio": top_fund["capture_ratio"],
            },
            "last_ranked": {
                "scheme_name": bottom_fund["scheme_name"],
                "rank": bottom_fund["rank"],
            },
            "number_of_funds": len(ranked_funds),
        }


# ================================================================
# CONVENIENCE FUNCTIONS
# ================================================================

def rank_funds(
    funds: Sequence[Dict[str, Any]],
    preference: str = "balanced",
) -> List[Dict[str, Any]]:
    """
    Convenience function.

    Example:

        rank_funds(funds, "growth")
    """

    ranker = FundRanker()

    return ranker.rank_funds(
        funds=funds,
        preference=preference,
    )


def rank_all_preferences(
    funds: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate all five rankings.

    Example result:

        {
            "defensive": [...],
            "balanced": [...],
            "growth": [...],
            "capture_efficiency": [...],
            "historical_return": [...]
        }
    """

    ranker = FundRanker()

    return ranker.rank_all_preferences(
        funds=funds
    )


# ================================================================
# EXAMPLE SCENERIO
# ================================================================

if __name__ == "__main__":

    from advisorkhoj_scraper import MarketCaptureScraper

    scraper = MarketCaptureScraper()
    ranker = FundRanker()

    # ------------------------------------------------------------
    # Select real funds from AdvisorKhoj
    # ------------------------------------------------------------

    selected_funds = [
        {
            "category": "Equity: Large Cap",
            "scheme": "Mirae Asset Large Cap Gr",
        },
        {
            "category": "Equity: Multi Cap",
            "scheme": "Baroda Multi Cap Plan B Dir Gr",
        },
        {
            "category": "Equity: Multi Cap",
            "scheme": "ICICI Pru Multi Cap Fund Dir Gr",
        },
        {
            "category": "Equity: Flexi Cap",
            "scheme": "ABSL Flexi Cap Gr Reg",
        },
        {
            "category": "Hybrid: Equity SavIngs",
            "scheme": "PGIM India Equity SavIngs Dir Gr",
        },
        {
            "category": "Hybrid: Equity SavIngs",
            "scheme": "Axis Equity Savings Fund Reg Gr",
        },
        {
            "category": "Hybrid: Equity SavIngs",
            "scheme": "DSP Equity SavIngs Reg Gr",
        }
        ]

    period = "3"

    # ------------------------------------------------------------
    # Fetch REAL AdvisorKhoj data
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("FETCHING ADVISORKHOJ DATA")
    print("=" * 70)

    try:

        funds = scraper.fetch_multiple_ratios(
            funds=selected_funds,
            period=period,
        )

    except Exception as exc:

        print()
        print("ERROR:")
        print(exc)

        raise SystemExit(1)

    # ------------------------------------------------------------
    # Display fetched data
    # ------------------------------------------------------------

    print()

    for fund in funds:

        print(
            f"Scheme Name    : "
            f"{fund['scheme_name']}"
        )

        print(
            f"AMC Name       : "
            f"{fund['amc_name']}"
        )

        print(
            f"Benchmark      : "
            f"{fund['benchmark_name']}"
        )

        print(
            f"Scheme Return  : "
            f"{fund['scheme_return']:.2f}%"
        )

        print(
            f"Up Capture     : "
            f"{fund['up_capture']:.2f}%"
        )

        print(
            f"Down Capture   : "
            f"{fund['down_capture']:.2f}%"
        )

        print(
            f"Capture Ratio  : "
            f"{fund['capture_ratio']:.2f}"
        )

        print()

    # ------------------------------------------------------------
    # Generate rankings for ALL investor preferences
    # ------------------------------------------------------------

    print()
    print("=" * 70)
    print("GENERATING RANKINGS")
    print("=" * 70)

    all_rankings = ranker.rank_all_preferences(
        funds
    )

    # ------------------------------------------------------------
    # Display each ranking
    # ------------------------------------------------------------

    for preference in ranker.PREFERENCES:

        print()
        print("=" * 70)

        print(
            ranker.PREFERENCE_LABELS[
                preference
            ]
        )

        print("=" * 70)

        ranking = all_rankings[preference]

        for fund in ranking:

            print(
                f"{fund['rank']}. "
                f"{fund['scheme_name']}"
            )

            print(
                f"   Scheme Return  : "
                f"{fund['scheme_return']:.2f}%"
            )

            print(
                f"   Up Capture     : "
                f"{fund['up_capture']:.2f}%"
            )

            print(
                f"   Down Capture   : "
                f"{fund['down_capture']:.2f}%"
            )

            print(
                f"   Capture Ratio  : "
                f"{fund['capture_ratio']:.2f}"
            )

            print(
                f"   Capture Spread : "
                f"{fund['capture_spread']:.2f}"
            )

            print(
                f"   Ranking Basis  : "
                f"{fund['ranking_basis']['display']}"
            )

            print()