import subprocess, time, sys, json, urllib.request, os
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = str(ROOT / "backend")
WEBSITE_DIR = str(ROOT / "website")

def wait_http(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

backend = subprocess.Popen(
    ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=BACKEND_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
website = subprocess.Popen(
    ["python3", "-m", "http.server", "8080"],
    cwd=WEBSITE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)

try:
    ok_backend = wait_http("http://localhost:8000/health")
    ok_website = wait_http("http://localhost:8080/index.html")
    print("backend up:", ok_backend, " website up:", ok_website)
    if not (ok_backend and ok_website):
        print("ABORT: servers did not come up")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

        page.goto("http://localhost:8080/index.html")
        page.wait_for_timeout(2500)

        status_text = page.inner_text("#statusText")
        print("Status pill says:", status_text)

        kpi_total = page.inner_text("#kpiTotal")
        kpi_high = page.inner_text("#kpiHigh")
        print("KPI total:", kpi_total, " KPI high risk:", kpi_high)

        rows = page.query_selector_all("#customerRows tr")
        print("Customer rows rendered:", len(rows))

        page.screenshot(path="/tmp/screenshot_dashboard.png", full_page=True)

        # Click "High risk" filter and confirm the table updates
        page.click(".filter-btn[data-band='high']")
        page.wait_for_timeout(800)
        first_row_risk = page.inner_text("#customerRows tr:first-child .risk-pct")
        print("Top row risk % after High filter:", first_row_risk)

        # Open the first customer's drawer
        first_id_text = page.inner_text("#customerRows tr:first-child .cid")
        customer_id = first_id_text.replace("#", "").strip()
        print("Opening drawer for customer:", customer_id)
        page.click("#customerRows tr:first-child")
        page.wait_for_timeout(600)
        drawer_open = page.eval_on_selector("#drawerOverlay", "el => el.classList.contains('open')")
        print("Drawer open:", drawer_open)
        drawer_id_text = page.inner_text("#drawerId")
        print("Drawer shows customer:", drawer_id_text)

        # Pick a preset offer and send it
        page.click(".preset[data-i='2']")  # "$10 redeem voucher"
        page.wait_for_timeout(200)
        msg_value = page.input_value("#offerMessage")
        print("Prefilled offer message:", msg_value)

        page.click("#sendOfferBtn")
        page.wait_for_timeout(1200)
        toast_text = page.inner_text("#toast")
        print("Toast after sending:", toast_text)

        page.screenshot(path="/tmp/screenshot_drawer_sent.png", full_page=True)

        # Verify via the real API (not just UI) that the offer actually exists
        with urllib.request.urlopen(f"http://localhost:8000/offers/customer/{customer_id}") as r:
            offers = json.loads(r.read())
        print("Offers for customer via API:", offers)
        assert len(offers) >= 1, "Offer was not actually created in the backend"
        assert offers[0]["status"] == "sent"

        offer_id = offers[0]["id"]

        # Simulate the Expo app redeeming it, via the same API the app would call
        req = urllib.request.Request(f"http://localhost:8000/offers/{offer_id}/redeem", method="POST")
        with urllib.request.urlopen(req) as r:
            redeem_result = json.loads(r.read())
        print("Redeem result:", redeem_result)
        assert redeem_result["status"] == "redeemed"

        # Close the modal drawer first (background is intentionally non-interactive while it's open)
        page.click("#closeDrawer")
        page.wait_for_timeout(400)

        # Go to Sent offers tab in the website and confirm it now shows redeemed
        page.click(".tab[data-tab='offers']")
        page.wait_for_timeout(1000)
        offers_tab_html = page.inner_html("#offerRows")
        print("Redeemed badge visible in Sent Offers tab:", "redeemed" in offers_tab_html)
        page.screenshot(path="/tmp/screenshot_offers_tab.png", full_page=True)

        print("\nConsole errors captured:", console_errors if console_errors else "NONE")

        browser.close()

    print("\nE2E TEST PASSED")

finally:
    backend.terminate()
    website.terminate()
    time.sleep(1)
    backend.kill()
    website.kill()
