# Verification

These are the actual scripts used to test this project before it was
handed over — not aspirational docs, the real thing. Rerun them yourself
if you want to confirm the claims in the top-level README.

- `e2e_test_website.py` — starts the backend and serves the website,
  drives a real headless Chromium browser (Playwright) through: loading
  the dashboard, filtering by risk, opening a customer, sending an offer,
  confirming it landed in the backend, redeeming it via the API (standing
  in for the customer's phone), and confirming the website's "Sent
  offers" tab reflects the redemption.

- `e2e_test_mobile_web.py` — starts the backend and serves the mobile
  app's web export (`npx expo export --platform web`, which runs the same
  React/JS code through `react-native-web` instead of the native
  renderer), then: connects the app to the backend, switches the demo
  customer, has the "company" send an offer via a direct API call while
  the app is sitting open, confirms the offer **appears through the
  app's own polling — no manual refresh** — taps Redeem, and confirms the
  backend was actually updated by that tap (not just the UI).

## What these do NOT prove

Neither script runs the app natively inside Expo Go on a real phone —
this environment doesn't have one attached. The web-export path exercises
the same JavaScript logic (API calls, state management, polling), but
native-only concerns (actual push permissions, native gestures, on-device
performance, the real QR-scan pairing flow) are only as trustworthy as
Expo's `react-native-web` compatibility layer, not independently confirmed
here. If you want that last mile of confidence, run
`npx expo start` and scan the QR code with a real phone — see
`HOW_TO_RUN.md`.

## Requirements to rerun

```bash
pip install playwright
playwright install chromium
```
