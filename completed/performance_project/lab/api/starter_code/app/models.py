"""Request bodies. FastAPI validates incoming JSON against these before your
route runs, and answers 422 if it doesn't fit."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class NewPurchase(BaseModel):
    """The JSON body for Q15, POST /purchases."""

    customer_id: int
    card_id: int
    product_id: int
    department: str
    amount: float
    purchase_date: date
