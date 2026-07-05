from typing import Optional
from pydantic import BaseModel, Field


class CustomerSummary(BaseModel):
    customer_id: int
    risk_score: float
    risk_band: str
    months: Optional[float] = None
    totrev: Optional[float] = None
    avgrev: Optional[float] = None
    avgmou: Optional[float] = None
    eqpdays: Optional[float] = None
    area: Optional[str] = None


class CustomerDetail(CustomerSummary):
    hnd_price: Optional[float] = None
    actvsubs: Optional[float] = None
    uniqsubs: Optional[float] = None
    marital: Optional[str] = None
    income: Optional[float] = None
    creditcd: Optional[str] = None
    custcare_Mean: Optional[float] = None
    change_mou: Optional[float] = None
    change_rev: Optional[float] = None
    actual_churn: Optional[int] = None


class CustomerListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    customers: list[CustomerSummary]


class PredictRequest(BaseModel):
    """Ad-hoc prediction request for a customer not in the stored table
    (or to test what-if feature changes). Any subset of model features can
    be supplied; missing ones are median/mode-imputed by the pipeline."""
    features: dict = Field(default_factory=dict)


class PredictResponse(BaseModel):
    churn_probability: float
    risk_band: str


class OfferCreate(BaseModel):
    customer_id: int
    offer_type: str = Field(..., examples=["10% off next bill", "Free 5GB data boost", "$10 redeem voucher"])
    message: str = Field(..., examples=["We'd hate to see you go — here's 10% off your next bill."])
    discount_value: Optional[str] = None


class Offer(BaseModel):
    id: int
    customer_id: int
    offer_type: str
    message: str
    discount_value: Optional[str]
    status: str  # "sent" | "redeemed"
    created_at: str
    redeemed_at: Optional[str] = None


class RedeemResponse(BaseModel):
    id: int
    status: str
    redeemed_at: str
