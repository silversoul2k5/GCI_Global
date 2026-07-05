"""
FastAPI backend for the churn-risk dashboard + customer offers demo.

Run from the backend/ directory:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Swagger docs: http://localhost:8000/docs

Architecture (single source of truth, both clients hit this one API):

    Website (company)  ──REST──▶  FastAPI  ──▶  customers.db (risk scores)
    Expo app (customer) ──REST──▶     │      ──▶  offers table (sent/redeemed)
                                       ▼
                                 best_model.joblib (loaded once at startup)
"""
import json
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.schemas import (
    CustomerDetail,
    CustomerListResponse,
    CustomerSummary,
    Offer,
    OfferCreate,
    PredictRequest,
    PredictResponse,
    RedeemResponse,
)

ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ROOT / "models"

app = FastAPI(
    title="Churn Risk & Offers API",
    description="Serves customer churn-risk scores to a company dashboard, "
                "and lets the company send retention offers that appear "
                "live in the customer's mobile app.",
    version="1.0.0",
)

# Wide-open CORS for a demo project: the website (served from any local
# port/tool) and the Expo Go app (served from the Metro bundler, a
# different origin every time) both need to reach this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL = None
METADATA = None
FEATURE_IMPORTANCE = None
METRICS_COMPARISON = None


@app.on_event("startup")
def load_artifacts():
    global MODEL, METADATA, FEATURE_IMPORTANCE, METRICS_COMPARISON
    model_path = MODELS_DIR / "best_model.joblib"
    if model_path.exists():
        MODEL = joblib.load(model_path)
    else:
        MODEL = None  # /predict will 503 until `python ml/train.py` has run

    for attr, fname in [
        ("METADATA", "metadata.json"),
        ("FEATURE_IMPORTANCE", "feature_importance.json"),
        ("METRICS_COMPARISON", "metrics_comparison.json"),
    ]:
        fpath = MODELS_DIR / fname
        globals()[attr] = json.loads(fpath.read_text()) if fpath.exists() else None

    db.init_offers_table()


@app.get("/")
def root():
    return {
        "name": "Churn Risk & Offers API",
        "status": "ok",
        "model_loaded": MODEL is not None,
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": MODEL is not None,
        "customers_table_ready": db.customers_table_exists(),
    }


@app.get("/metrics")
def metrics():
    if METRICS_COMPARISON is None:
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    return {"metadata": METADATA, "model_comparison": METRICS_COMPARISON}


@app.get("/feature-importance")
def feature_importance():
    if FEATURE_IMPORTANCE is None:
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    return {"top_features": FEATURE_IMPORTANCE}


@app.get("/charts")
def charts():
    """Pre-aggregated data for the website's charts (risk-band counts +
    a revenue-vs-risk bucket breakdown), computed on the fly from the
    lightweight customers table — cheap because it's one indexed table,
    not the raw multi-million-cell source CSVs."""
    if not db.customers_table_exists():
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    conn = db.get_conn()
    band_rows = conn.execute(
        "SELECT risk_band, COUNT(*) as count FROM customers GROUP BY risk_band"
    ).fetchall()
    revenue_rows = conn.execute(
        "SELECT risk_band, AVG(totrev) as avg_revenue FROM customers GROUP BY risk_band"
    ).fetchall()
    conn.close()
    return {
        "risk_band_counts": {r["risk_band"]: r["count"] for r in band_rows},
        "avg_revenue_by_band": {r["risk_band"]: round(r["avg_revenue"] or 0, 2) for r in revenue_rows},
    }


@app.get("/customers", response_model=CustomerListResponse)
def list_customers(
    risk_band: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    search: Optional[str] = Query(None, description="Search by exact or partial customer_id"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if not db.customers_table_exists():
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    conn = db.get_conn()
    where = []
    params = []
    if risk_band:
        where.append("risk_band = ?")
        params.append(risk_band)
    if search:
        where.append("CAST(customer_id AS TEXT) LIKE ?")
        params.append(f"%{search}%")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = conn.execute(f"SELECT COUNT(*) FROM customers {where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"""SELECT customer_id, risk_score, risk_band, months, totrev, avgrev,
                   avgmou, eqpdays, area
            FROM customers {where_sql}
            ORDER BY risk_score DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "customers": [CustomerSummary(**dict(r)) for r in rows],
    }


@app.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: int):
    if not db.customers_table_exists():
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    conn = db.get_conn()
    row = conn.execute(
        "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(404, f"No customer with id {customer_id}")
    return CustomerDetail(**dict(row))


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Ad-hoc what-if prediction. Any subset of the model's expected
    features can be passed; anything missing is imputed by the trained
    pipeline (median for numeric, most-frequent for categorical) exactly
    as it was during training — so partial payloads are safe."""
    if MODEL is None or METADATA is None:
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")

    all_features = METADATA["numeric_features"] + METADATA["categorical_features"]
    row = {f: req.features.get(f, None) for f in all_features}
    X = pd.DataFrame([row])
    proba = float(MODEL.predict_proba(X)[0, 1])
    band = "high" if proba >= 0.66 else "medium" if proba >= 0.33 else "low"
    return PredictResponse(churn_probability=round(proba, 4), risk_band=band)


# ---------------------------------------------------------------------
# Offers: this is the shared state between the company website and the
# customer's Expo app. POST /offers is called by the website. The Expo
# app polls GET /offers/customer/{id} to see new offers, and calls
# POST /offers/{id}/redeem when the customer taps "Redeem".
# ---------------------------------------------------------------------

@app.post("/offers", response_model=Offer, status_code=201)
def send_offer(offer: OfferCreate):
    if not db.customers_table_exists():
        raise HTTPException(503, "Model not trained yet. Run: python ml/train.py")
    conn = db.get_conn()
    exists = conn.execute(
        "SELECT 1 FROM customers WHERE customer_id = ?", (offer.customer_id,)
    ).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(404, f"No customer with id {offer.customer_id}")

    created_at = db.now_iso()
    cur = conn.execute(
        """INSERT INTO offers (customer_id, offer_type, message, discount_value, status, created_at)
           VALUES (?, ?, ?, ?, 'sent', ?)""",
        (offer.customer_id, offer.offer_type, offer.message, offer.discount_value, created_at),
    )
    conn.commit()
    offer_id = cur.lastrowid
    row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
    conn.close()
    return Offer(**dict(row))


@app.get("/offers", response_model=list[Offer])
def list_all_offers(limit: int = Query(100, ge=1, le=1000)):
    """Admin view for the website: every offer ever sent, most recent first."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM offers ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [Offer(**dict(r)) for r in rows]


@app.get("/offers/customer/{customer_id}", response_model=list[Offer])
def list_offers_for_customer(customer_id: int):
    """Polled by the Expo app to discover new offers for the logged-in
    (demo) customer."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM offers WHERE customer_id = ? ORDER BY id DESC", (customer_id,)
    ).fetchall()
    conn.close()
    return [Offer(**dict(r)) for r in rows]


@app.post("/offers/{offer_id}/redeem", response_model=RedeemResponse)
def redeem_offer(offer_id: int):
    """Called by the Expo app when the customer taps 'Redeem voucher'."""
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(404, f"No offer with id {offer_id}")
    if row["status"] == "redeemed":
        conn.close()
        return RedeemResponse(id=offer_id, status="redeemed", redeemed_at=row["redeemed_at"])

    redeemed_at = db.now_iso()
    conn.execute(
        "UPDATE offers SET status = 'redeemed', redeemed_at = ? WHERE id = ?",
        (redeemed_at, offer_id),
    )
    conn.commit()
    conn.close()
    return RedeemResponse(id=offer_id, status="redeemed", redeemed_at=redeemed_at)
