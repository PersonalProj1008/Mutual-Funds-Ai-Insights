from typing import List, Union

from pydantic import BaseModel, Field, field_validator


class FundSelection(BaseModel):
    category: str = Field(..., min_length=1)
    scheme: str = Field(..., min_length=1)

    @field_validator("category", "scheme")
    @classmethod
    def strip_text(cls, value):
        value = str(value).strip()

        if not value:
            raise ValueError("Value cannot be empty.")

        return value


class AnalysisRequest(BaseModel):
    """
    Accepts either:

    1. Search & Select mode:
       [
           {
               "category": "Equity: Large Cap",
               "scheme": "Mirae Asset Large Cap Gr"
           }
       ]

    2. Paste List mode:
       [
           "Mirae Asset Large Cap Gr",
           "ICICI Pru Multi Cap Fund Dir Gr"
       ]
    """

    funds: List[Union[str, FundSelection]]
    period: str

    @field_validator("period")
    @classmethod
    def validate_period(cls, value):
        value = str(value).strip()

        if value not in {"1", "3", "5", "10"}:
            raise ValueError(
                "Invalid period. Allowed periods are: 1, 3, 5, 10."
            )

        return value

    @field_validator("funds")
    @classmethod
    def validate_funds(cls, value):
        if not isinstance(value, list):
            raise ValueError("Funds must be provided as a list.")

        if len(value) < 2:
            raise ValueError("At least 2 funds are required.")

        if len(value) > 10:
            raise ValueError("A maximum of 10 funds can be selected.")

        if not all(
            isinstance(item, (str, FundSelection))
            for item in value
        ):
            raise ValueError(
                "Each fund must be either a scheme name or a fund selection object."
            )

        return value