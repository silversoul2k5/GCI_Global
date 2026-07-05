<img width="1581" height="656" alt="wmremove-transformed" src="https://github.com/user-attachments/assets/36e50ec3-8041-4bbb-998c-24f09e17eb42" /># Signal — Churn Retention Platform

A working end-to-end demo: a company dashboard that shows which customers
are at high risk of churning, and a customer-facing mobile app that
receives retention offers the company sends — live, no manual refresh.

Built on the telecom churn dataset (`Client.csv` + `Record.csv`, ~100,000
customers) from the Final Assignment package.

```
┌────────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│   Website (company) │ ──────▶│                      │◀────── │  Expo Go app         │
│   "Who's at risk,   │  REST  │   FastAPI backend    │  REST  │  (the customer)      │
│    send them a      │◀───────│                      │───────▶│  polls for new       │
│    voucher"         │        │  best_model.joblib   │        │  offers, redeems     │
└────────────────────┘         │  customers.db        │        │  them                │
                                │  offers table         │        └─────────────────────┘
                                └──────────────────────┘
```

<img width="1581" height="656" alt="wmremove-transformed" src="https://github.com/user-attachments/assets/90dd7d45-2e75-4914-a88f-ad93ff5cce42" />


<img width="637" height="468" alt="image" src="https://github.com/user-attachments/assets/542cdee1-5bd1-4c2e-bb1e-3d52981cbe08" />


Both clients are just callers of the same API. Sending an offer on the
website inserts a row in the `offers` table; the phone app polls
`GET /offers/customer/{id}` every few seconds and picks it up automatically.
Tapping "Redeem" in the app calls `POST /offers/{id}/redeem`, and the
website's "Sent offers" tab reflects that within seconds too.

## What's in here

```
backend/        FastAPI app + ML training pipeline (Python)
website/        Company dashboard — single static HTML file, no build step
mobile_app/     Expo Go app the customer uses (React Native)
verification/   The actual scripts used to test this end-to-end (see below)
```

## What was actually verified before this was handed to you

Being upfront about this, in the spirit of "don't claim things you haven't
run":

| Component | How it was tested | Result |
|---|---|---|
| ML pipeline | Ran `ml/train.py` on the real 100k-row dataset | Trained Logistic Regression, Random Forest, XGBoost; XGBoost won (ROC AUC 0.693); metrics/artifacts saved |
| Backend | Started uvicorn, hit every endpoint with `curl`, including the full send→poll→redeem→re-poll offer cycle | All endpoints returned correct data; offer status transitions verified; 404s verified for bad IDs |
| Website | Loaded in a real headless Chromium browser (Playwright), clicked through filters, opened a customer, sent a real offer, confirmed it in the backend, redeemed it via the API, confirmed the UI updated | Passed, no console errors |
| Mobile app | Bundled with `expo export --platform web` (507 modules, zero errors) and driven in a real browser via Playwright: switched demo customer, had the "company" send an offer via the API while the app was open, confirmed it appeared **through polling alone, no manual refresh**, tapped Redeem, confirmed the backend was actually updated | Passed, no console errors |
| Native Expo Go run on a physical phone | **Not done** — this environment has no phone or emulator attached | Not verified; the app was only proven correct via the web-export path above, which exercises the same React/JS logic but through `react-native-web` rather than the real native renderer |

The `verification/` folder has the exact test scripts, so you (or anyone
grading this) can rerun them.

## Quick start

See `HOW_TO_RUN.md` for exact commands. Short version:

1. `pip install -r backend/requirements.txt`
2. `python backend/ml/train.py` (already run once — `backend/models/` and
   `backend/data/customers.db` are included, so you can skip this and go
   straight to step 3, then rerun it later if you want to retrain)
3. `uvicorn app.main:app --reload` (from inside `backend/`)
4. Open `website/index.html` in a browser
5. `cd mobile_app && npm install && npx expo start` → scan the QR code
   with Expo Go on your phone (see `HOW_TO_RUN.md` for the LAN IP gotcha)

## Design decisions worth knowing about

- **Risk scores are precomputed**, not computed live per request. Training
  scores every customer once and writes the result to a small SQLite table
  (`customers.db`) with an index on `risk_score`. The API just queries that
  table, so listing/filtering/sorting 100,000 customers stays fast without
  re-loading the multi-million-cell source CSVs on every request.
- **Offers are polled, not pushed.** True push notifications need Expo
  push credentials and a project set up on Expo's servers — more moving
  parts and another account to configure. Polling every 4 seconds is
  simple, works the moment you open the project, and for a demo the
  difference is imperceptible. If you want true push later, the
  `/offers/customer/{id}` endpoint is already the right shape to swap in
  `expo-notifications` on top of.
- **Chart.js is vendored locally** (`website/chart.umd.min.js`) instead of
  loaded from a CDN, so the dashboard works even with no internet access
  and so it could actually be tested in a sandboxed environment with
  restricted network access. Fonts are still loaded from Google Fonts and
  fall back to system fonts if unreachable — that's a cosmetic-only
  dependency, unlike the charts.
- **The website is a single static HTML file** — open it directly in a
  browser, no `npm install` or build step. This was a deliberate choice to
  minimize what can go wrong when you first open the project.
- **The mobile app doesn't show the customer their own churn-risk score.**
  Real products wouldn't tell a customer "we think you're 87% likely to
  leave" — it would feel invasive and could backfire. The demo customer
  IDs you can switch between on the Home tab are chosen from the
  model's actual high-risk list, but the app frames it as a normal account
  screen with a rewards/offers tab.

## Known limitations / what's next

- No authentication — anyone with the API URL can list customers or send
  offers. Fine for a local demo, not for production.
- The `/predict` endpoint accepts a partial feature dict and imputes the
  rest, which is convenient for testing but means a caller could get very
  different predictions depending on which features they omit — worth
  tightening if this becomes more than a demo.
- Offer "redemption" doesn't currently do anything on the telecom side
  (e.g. actually applying a bill credit) — it just flips a status flag.
  That's the natural next integration point.
- The model's ROC AUC (0.693) is real but modest — realistic for this
  dataset's signal-to-noise ratio, not something to oversell in a business
  pitch built on top of this.
