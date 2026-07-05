"""
Train a churn-prediction model on Company A's telecom dataset and
precompute a lightweight, queryable customers table for the API to serve.

Run:
    python ml/train.py

Produces (all under backend/models/ and backend/data/):
    models/best_model.joblib       - the winning sklearn/xgboost pipeline
    models/metadata.json           - which model won, feature list, metrics
    models/metrics_comparison.json - metrics for every model tried
    models/feature_importance.json - top feature importances of the winner
    data/customers.db              - SQLite DB: one row per customer with
                                      precomputed risk_score + key display
                                      fields, used by the API at request time
                                      (avoids re-loading multi-million-cell
                                      CSVs on every request)
"""
import json
import sqlite3
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

try:
    from xgboost import XGBClassifier
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODELS_DIR = ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

RANDOM_STATE = 42
TARGET = "churn"
ID_COL = "Customer_ID"

# Columns that make a good, human-readable customer card in the UI.
# (subset picked from the two source tables — chosen for interpretability,
# not for model performance)
DISPLAY_COLS = [
    ID_COL, "months", "totrev", "avgrev", "avgmou", "eqpdays",
    "hnd_price", "actvsubs", "uniqsubs", "area", "marital",
    "income", "creditcd", "custcare_Mean", "change_mou", "change_rev",
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_and_merge():
    log("Loading Client.csv and Record.csv ...")
    client = pd.read_csv(DATA_DIR / "Client.csv")
    record = pd.read_csv(DATA_DIR / "Record.csv")
    log(f"Client: {client.shape}  Record: {record.shape}")

    df = record.merge(client, on=ID_COL, how="inner")
    log(f"Merged: {df.shape}")
    return df


def build_feature_lists(df):
    feature_cols = [c for c in df.columns if c not in (TARGET, ID_COL)]
    numeric_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in feature_cols if c not in numeric_cols]
    log(f"{len(numeric_cols)} numeric features, {len(categorical_cols)} categorical features")
    return numeric_cols, categorical_cols


def build_preprocessor(numeric_cols, categorical_cols):
    numeric_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("encode", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
    ])
    return ColumnTransformer([
        ("num", numeric_pipe, numeric_cols),
        ("cat", categorical_pipe, categorical_cols),
    ])


def evaluate(name, model, X_test, y_test):
    preds = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    cm = confusion_matrix(y_test, preds).tolist()
    metrics = {
        "model": name,
        "accuracy": round(accuracy_score(y_test, preds), 4),
        "precision": round(precision_score(y_test, preds), 4),
        "recall": round(recall_score(y_test, preds), 4),
        "f1": round(f1_score(y_test, preds), 4),
        "roc_auc": round(roc_auc_score(y_test, proba), 4),
        "confusion_matrix": {
            "labels": ["stayed(0)", "churned(1)"],
            "matrix": cm,
        },
    }
    log(f"{name}: acc={metrics['accuracy']} f1={metrics['f1']} roc_auc={metrics['roc_auc']}")
    return metrics


def main():
    df = load_and_merge()
    df = df.dropna(subset=[TARGET])
    df[TARGET] = df[TARGET].astype(int)

    numeric_cols, categorical_cols = build_feature_lists(df)
    X = df[numeric_cols + categorical_cols]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    log(f"Train: {X_train.shape}  Test: {X_test.shape}")

    preprocessor = build_preprocessor(numeric_cols, categorical_cols)

    candidates = {
        "logistic_regression": LogisticRegression(max_iter=1000, random_state=RANDOM_STATE),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, n_jobs=-1, random_state=RANDOM_STATE
        ),
    }
    if HAS_XGB:
        candidates["xgboost"] = XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.08,
            subsample=0.9, colsample_bytree=0.9,
            eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=-1,
        )
    else:
        log("xgboost not installed — skipping (this is flagged, not silently faked)")

    all_metrics = []
    fitted = {}
    for name, clf in candidates.items():
        log(f"Training {name} ...")
        pipe = Pipeline([("prep", preprocessor), ("clf", clf)])
        pipe.fit(X_train, y_train)
        fitted[name] = pipe
        all_metrics.append(evaluate(name, pipe, X_test, y_test))

    best = max(all_metrics, key=lambda m: m["roc_auc"])
    best_name = best["model"]
    best_pipe = fitted[best_name]
    log(f"Best model: {best_name} (roc_auc={best['roc_auc']})")

    joblib.dump(best_pipe, MODELS_DIR / "best_model.joblib")

    # Feature importance (best-effort: tree models expose it directly;
    # logistic regression uses absolute coefficient magnitude as a proxy)
    feat_names = numeric_cols + categorical_cols
    clf = best_pipe.named_steps["clf"]
    if hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        importances = np.abs(clf.coef_[0])
    else:
        importances = np.zeros(len(feat_names))
    imp_pairs = sorted(zip(feat_names, importances.tolist()), key=lambda p: -p[1])
    feature_importance = [{"feature": f, "importance": round(v, 6)} for f, v in imp_pairs[:25]]
    with open(MODELS_DIR / "feature_importance.json", "w") as f:
        json.dump(feature_importance, f, indent=2)

    with open(MODELS_DIR / "metrics_comparison.json", "w") as f:
        json.dump(all_metrics, f, indent=2)

    metadata = {
        "best_model": best_name,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "numeric_features": numeric_cols,
        "categorical_features": categorical_cols,
        "target": TARGET,
        "id_column": ID_COL,
        "test_metrics": best,
        "rows_trained_on": int(len(df)),
        "xgboost_available": HAS_XGB,
    }
    with open(MODELS_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # ---- Precompute risk scores for every customer & write to SQLite ----
    log("Scoring all customers for the API's customers table ...")
    all_proba = best_pipe.predict_proba(X)[:, 1]
    df["risk_score"] = all_proba

    display_df = df[[c for c in DISPLAY_COLS if c in df.columns] + ["risk_score", TARGET]].copy()
    display_df = display_df.rename(columns={ID_COL: "customer_id", TARGET: "actual_churn"})

    def bucket(p):
        if p >= 0.66:
            return "high"
        if p >= 0.33:
            return "medium"
        return "low"

    display_df["risk_band"] = display_df["risk_score"].apply(bucket)
    display_df["risk_score"] = display_df["risk_score"].round(4)

    db_path = DATA_DIR / "customers.db"
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    display_df.to_sql("customers", conn, index=False)
    conn.execute("CREATE INDEX idx_risk_score ON customers(risk_score DESC)")
    conn.execute("CREATE INDEX idx_customer_id ON customers(customer_id)")
    conn.commit()
    conn.close()
    log(f"Wrote {len(display_df)} rows to {db_path}")

    high = (display_df["risk_band"] == "high").sum()
    med = (display_df["risk_band"] == "medium").sum()
    low = (display_df["risk_band"] == "low").sum()
    log(f"Risk bands -> high: {high}  medium: {med}  low: {low}")

    log("Done.")


if __name__ == "__main__":
    main()
