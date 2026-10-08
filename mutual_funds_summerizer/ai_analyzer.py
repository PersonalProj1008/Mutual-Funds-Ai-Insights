import asyncio
import json
import os

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError


class AIAnalyzerError(Exception):
    """Raised when AI analysis fails."""
    pass


class RankingExplanation(BaseModel):
    """Validates one ranking explanation after the AI response."""

    preference: str
    rank: int
    scheme_name: str
    reason: str


class FlatAIAnalysis(BaseModel):
    """
    Depth-1 structured output.

    Every model-output field is a scalar. The only serialized structure is
    ranking_explanations_json, which is converted into the existing nested
    application structure after validation.
    """

    overall_summary: str

    defensive_winner: str
    defensive_summary: str

    balanced_winner: str
    balanced_summary: str

    growth_winner: str
    growth_summary: str

    capture_efficiency_winner: str
    capture_efficiency_summary: str

    historical_return_winner: str
    historical_return_summary: str

    ranking_explanations_json: str = Field(
        description=(
            "A valid JSON array encoded as a string. "
            'Each item must contain "preference", "rank", '
            '"scheme_name", and "reason".'
        )
    )

    important_notes: str = Field(
        description=(
            "Important methodological notes separated by newline. "
            "Do not use numbered prefixes."
        )
    )


class AIAnalyzer:
    SUPPORTED_PERIODS = {"1", "3", "5", "10"}

    PREFERENCES = {
        "defensive": "Protect my downside",
        "balanced": "Balance growth & protection",
        "growth": "Maximize upside",
        "capture_efficiency": "Maximize capture efficiency",
        "historical_return": "Maximize historical returns",
    }

    def __init__(
        self,
        api_key,
        base_url,
        model,
        app_name="Principle Wealth",
        app_url=None,
    ):
        if not api_key:
            raise ValueError("api_key is required.")

        if not base_url:
            raise ValueError("base_url is required.")

        if not model:
            raise ValueError("model is required.")

        self.model = model

        default_headers = {
            "X-Title": app_name,
        }

        if app_url:
            default_headers["HTTP-Referer"] = app_url

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            default_headers=default_headers,
            timeout=90.0,
            max_retries=2,
        )

    async def analyze(self, funds, rankings, period):
        """
        Call the model with a depth-1 Pydantic schema and return the
        same nested dictionary structure used by the report generator.
        """

        self._validate_inputs(funds, rankings, period)

        prompt = self._build_prompt(
            funds=funds,
            rankings=rankings,
            period=period,
        )

        ai_result = await self._call_model(prompt)

        return self._derive_current_structure(
            ai_result=ai_result,
            rankings=rankings,
        )

    def _build_prompt(self, funds, rankings, period):
        fund_data = self._prepare_fund_data(funds)
        ranking_data = self._prepare_ranking_data(rankings)

        return f"""
You are the AI explanation and report-writing layer of a mutual-fund
comparison application.

You are NOT the ranking engine.

Python has already calculated the exact rankings.
Treat those rankings as immutable facts.

Your job is to explain the supplied rankings and produce polished,
professional report language.

============================================================
ABSOLUTE RULES
============================================================

1. NEVER change a rank.
2. NEVER invent, estimate, or recalculate missing fund data.
3. NEVER substitute your own ranking logic for Python.
4. Every ranking explanation must match the supplied
   preference + rank + scheme_name exactly.
5. Preserve fund names exactly as supplied.
6. Use only the supplied metrics.
7. A higher rank does NOT mean a fund is universally better.
8. Do not provide personalized investment advice.
9. Scheme Return is historical/backward-looking and is not a forecast.
10. Capture Spread = Up Market Capture - Down Market Capture.
    It is an APP-DEFINED comparative heuristic, not an official
    AdvisorKhoj metric.
11. Capture Ratio is the supplied AdvisorKhoj metric.
12. Do not confuse Down Market Capture with a fund's actual loss.
13. Do not introduce unsupported metrics or qualitative claims.
14. The numerical ranking is immutable.

============================================================
INVESTOR LENSES
============================================================

defensive:
    Label: Protect my downside
    Primary rule: lower Down Market Capture is better.

balanced:
    Label: Balance growth & protection
    Primary rule: higher Capture Spread is better.
    Capture Spread is app-defined.
    Follow the supplied Python ranking criteria for tie-breakers.

growth:
    Label: Maximize upside
    Primary rule: higher Up Market Capture is better.

capture_efficiency:
    Label: Maximize capture efficiency
    Primary rule: higher Capture Ratio is better.

historical_return:
    Label: Maximize historical returns
    Primary rule: higher Scheme Return is better.
    This is backward-looking.

============================================================
TIE-BREAKING
============================================================

When multiple funds share the same primary metric, explicitly explain
the deterministic secondary criterion used by Python.

Never describe differently ranked funds as "tied for first".

Use only the supplied ranking basis and metric values when explaining
a tie-break.

============================================================
OVERALL SUMMARY
============================================================

Write 3-5 sentences describing the ACTUAL findings.

Identify:
- major cross-lens patterns,
- which funds lead which lenses,
- meaningful consistency or divergence,
- whether one fund dominates or different lenses favor different funds.

Do not write generic filler such as:
"This analysis evaluates four mutual funds..."

============================================================
PREFERENCE SUMMARIES
============================================================

For each preference:
- identify the actual rank #1 winner,
- explain what the lens reveals,
- mention the most meaningful metric comparison,
- use 2-4 sentences.

The winner must exactly match rank #1 in the supplied Python ranking.

============================================================
RANKING EXPLANATIONS
============================================================

Provide exactly one explanation for EVERY ranked fund under EVERY
preference.

Each explanation must:
- contain the exact preference,
- contain the exact rank,
- contain the exact scheme name,
- explain why that rank occurred,
- cite the relevant metric(s),
- explain a deterministic tie-break when applicable,
- be 1-3 sentences.

The ranking_explanations_json field must contain valid JSON encoded
as a STRING using exactly this internal structure:

[
  {{
    "preference": "defensive",
    "rank": 1,
    "scheme_name": "Exact Fund Name",
    "reason": "..."
  }}
]

============================================================
IMPORTANT NOTES
============================================================

Return useful methodological caveats as newline-delimited notes.

============================================================
STRUCTURED OUTPUT CONSTRAINT
============================================================

The response schema is DEPTH 1.

Every top-level field must be a scalar string.

Do NOT create top-level arrays or nested objects.

The only serialized structure is inside the scalar string field:
ranking_explanations_json

Period:
{period} years

============================================================
FUND DATA
============================================================

{json.dumps(fund_data, indent=2, ensure_ascii=False)}

============================================================
DETERMINISTIC RANKING DATA
============================================================

{json.dumps(ranking_data, indent=2, ensure_ascii=False)}

Return only the requested structured output.
""".strip()

    def _prepare_fund_data(self, funds):
        data = []

        for fund in funds:
            data.append({
                "scheme_name": fund.get("scheme_name"),
                "amc_name": fund.get("amc_name"),
                "benchmark_name": fund.get("benchmark_name"),
                "launch_date": fund.get("launch_date"),
                "scheme_return": fund.get("scheme_return"),
                "up_capture": fund.get("up_capture"),
                "down_capture": fund.get("down_capture"),
                "capture_ratio": fund.get("capture_ratio"),
            })

        return data

    def _prepare_ranking_data(self, rankings):
        data = {}

        for preference, ranked_funds in rankings.items():
            data[preference] = {
                "label": self.PREFERENCES[preference],
                "criteria": [],
                "ranking_order": [],
                "funds": [],
            }

            if ranked_funds:
                basis = ranked_funds[0].get("ranking_basis")

                if isinstance(basis, list):
                    data[preference]["criteria"] = basis
                elif basis:
                    data[preference]["criteria"] = [basis]

            for item in ranked_funds:
                data[preference]["ranking_order"].append({
                    "rank": item.get("rank"),
                    "scheme_name": item.get("scheme_name"),
                })

                data[preference]["funds"].append({
                    "rank": item.get("rank"),
                    "scheme_name": item.get("scheme_name"),
                    "ranking_basis": item.get("ranking_basis"),
                    "characteristics": item.get("characteristics"),
                    "up_capture": item.get("up_capture"),
                    "down_capture": item.get("down_capture"),
                    "capture_ratio": item.get("capture_ratio"),
                    "scheme_return": item.get("scheme_return"),
                    "capture_spread": item.get("capture_spread"),
                })

        return data

    async def _call_model(self, prompt):
        try:
            response = await self.client.chat.completions.parse(
                model=self.model,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a precise financial-analysis writer. "
                            "Follow deterministic Python rankings exactly "
                            "and never invent data."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                response_format=FlatAIAnalysis,
            )
        except Exception as exc:
            raise AIAnalyzerError(
                f"AI request failed: {exc}"
            ) from exc

        try:
            message = response.choices[0].message
        except (AttributeError, IndexError) as exc:
            raise AIAnalyzerError(
                "AI returned an unexpected response structure."
            ) from exc

        if getattr(message, "refusal", None):
            raise AIAnalyzerError(
                f"AI refused the request: {message.refusal}"
            )

        parsed = getattr(message, "parsed", None)

        if parsed is None:
            raise AIAnalyzerError(
                "AI response could not be parsed into the Pydantic schema."
            )

        return parsed

    def _derive_current_structure(self, ai_result, rankings):
        explanations = self._parse_ranking_explanations(
            ai_result.ranking_explanations_json
        )

        expected_pairs = set()

        for preference, ranked_funds in rankings.items():
            for ranked in ranked_funds:
                expected_pairs.add((
                    preference,
                    int(ranked.get("rank")),
                    ranked.get("scheme_name"),
                ))

        actual_pairs = set()

        for item in explanations:
            pair = (
                item.preference,
                item.rank,
                item.scheme_name,
            )

            if pair in actual_pairs:
                raise AIAnalyzerError(
                    f"Duplicate ranking explanation returned: {pair}"
                )

            actual_pairs.add(pair)

        if actual_pairs != expected_pairs:
            missing = expected_pairs - actual_pairs
            extra = actual_pairs - expected_pairs

            raise AIAnalyzerError(
                "AI ranking explanations do not exactly match the "
                f"deterministic rankings. Missing: {missing}; Extra: {extra}"
            )

        expected_winners = {
            preference: ranked_funds[0].get("scheme_name")
            for preference, ranked_funds in rankings.items()
        }

        ai_winners = {
            "defensive": ai_result.defensive_winner,
            "balanced": ai_result.balanced_winner,
            "growth": ai_result.growth_winner,
            "capture_efficiency": ai_result.capture_efficiency_winner,
            "historical_return": ai_result.historical_return_winner,
        }

        for preference, expected in expected_winners.items():
            actual = ai_winners[preference]

            if actual != expected:
                raise AIAnalyzerError(
                    f"AI winner mismatch for '{preference}': "
                    f"expected '{expected}', got '{actual}'"
                )

        return {
            "overall_summary": ai_result.overall_summary,
            "preference_summaries": [
                {
                    "preference": "defensive",
                    "winner": ai_result.defensive_winner,
                    "summary": ai_result.defensive_summary,
                },
                {
                    "preference": "balanced",
                    "winner": ai_result.balanced_winner,
                    "summary": ai_result.balanced_summary,
                },
                {
                    "preference": "growth",
                    "winner": ai_result.growth_winner,
                    "summary": ai_result.growth_summary,
                },
                {
                    "preference": "capture_efficiency",
                    "winner": ai_result.capture_efficiency_winner,
                    "summary": ai_result.capture_efficiency_summary,
                },
                {
                    "preference": "historical_return",
                    "winner": ai_result.historical_return_winner,
                    "summary": ai_result.historical_return_summary,
                },
            ],
            "ranking_explanations": [
                {
                    "preference": item.preference,
                    "rank": item.rank,
                    "scheme_name": item.scheme_name,
                    "reason": item.reason,
                }
                for item in explanations
            ],
            "important_notes": self._parse_notes(
                ai_result.important_notes
            ),
        }

    def _parse_ranking_explanations(self, value):
        try:
            raw_items = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AIAnalyzerError(
                "ranking_explanations_json was not valid JSON."
            ) from exc

        if not isinstance(raw_items, list):
            raise AIAnalyzerError(
                "ranking_explanations_json must contain a JSON array."
            )

        parsed_items = []

        for index, item in enumerate(raw_items, start=1):
            try:
                parsed_items.append(
                    RankingExplanation.model_validate(item)
                )
            except ValidationError as exc:
                raise AIAnalyzerError(
                    f"Invalid ranking explanation at item {index}: {exc}"
                ) from exc

        return parsed_items

    def _parse_notes(self, value):
        return [
            line.strip()
            for line in value.splitlines()
            if line.strip()
        ]

    def _validate_inputs(self, funds, rankings, period):
        if not isinstance(funds, list) or not funds:
            raise ValueError("funds must be a non-empty list.")

        if not isinstance(rankings, dict) or not rankings:
            raise ValueError("rankings must be a non-empty dictionary.")

        period = str(period).strip()

        if period not in self.SUPPORTED_PERIODS:
            raise ValueError(
                "period must be one of: 1, 3, 5, 10."
            )

        for fund in funds:
            if not isinstance(fund, dict):
                raise ValueError(
                    "Every fund must be a dictionary."
                )

            if not fund.get("scheme_name"):
                raise ValueError(
                    "Every fund must contain scheme_name."
                )

        for preference, ranked_funds in rankings.items():
            if preference not in self.PREFERENCES:
                raise ValueError(
                    f"Unsupported preference: {preference}"
                )

            if not isinstance(ranked_funds, list) or not ranked_funds:
                raise ValueError(
                    f"Ranking '{preference}' must contain funds."
                )


# async def main():
#     analyzer = AIAnalyzer(
#         api_key=os.getenv("OPENROUTER_API_KEY"),
#         base_url=os.getenv(
#             "OPENROUTER_BASE_URL",
#             "https://openrouter.ai/api/v1",
#         ),
#         model=os.getenv(
#             "OPENROUTER_MODEL",
#             "google/gemini-3.1-flash-lite",
#         ),
#         app_name="Principle Wealth",
#     )

#     print("AIAnalyzer initialized successfully.")
#     print(f"Model: {analyzer.model}")
#     print(f"Base URL: {analyzer.client.base_url}")

