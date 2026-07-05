import subprocess, time, sys, json, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = str(ROOT / "backend")
APP_DIST_DIR = str(ROOT / "mobile_app" / "dist")

def wait_http(url, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def api_post(path):
    req = urllib.request.Request(f"http://localhost:8000{path}", method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def api_post_json(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"http://localhost:8000{path}", data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def api_get(path):
    with urllib.request.urlopen(f"http://localhost:8000{path}") as r:
        return json.loads(r.read())

backend = subprocess.Popen(
    ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
    cwd=BACKEND_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)
appserver = subprocess.Popen(
    ["python3", "-m", "http.server", "8082"],
    cwd=APP_DIST_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
)

try:
    ok_backend = wait_http("http://localhost:8000/health")
    ok_app = wait_http("http://localhost:8082/index.html")
    print("backend up:", ok_backend, " app (web export) up:", ok_app)
    if not (ok_backend and ok_app):
        sys.exit(1)

    # pick a real high-risk customer id to test with
    demo = api_get("/customers?risk_band=high&limit=1")
    test_customer_id = demo["customers"][0]["customer_id"]
    print("Testing with customer:", test_customer_id)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 420, "height": 850})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))

        page.goto("http://localhost:8082/index.html")
        page.wait_for_timeout(2500)
        page.screenshot(path="/tmp/app_home_initial.png")

        # Point the app at our backend (default placeholder IP won't resolve here)
        api_input = page.locator("input[placeholder='http://192.168.1.23:8000']")
        api_input.fill("http://localhost:8000")
        page.get_by_text("Save", exact=True).click()
        page.wait_for_timeout(1500)

        # Switch demo account to our test customer via the pill row
        pill = page.get_by_text(f"#{test_customer_id}", exact=True)
        pill.click()
        page.wait_for_timeout(1000)
        page.screenshot(path="/tmp/app_home_connected.png")

        body_text = page.inner_text("body")
        print("Home shows customer name:", f"Customer #{test_customer_id}" in body_text)

        # Go to Offers tab
        page.get_by_text("Offers", exact=True).click()
        page.wait_for_timeout(1000)
        page.screenshot(path="/tmp/app_offers_empty_or_initial.png")

        # Simulate the COMPANY sending an offer via the website's API, while the app is open
        offer = api_post_json("/offers", {
            "customer_id": test_customer_id,
            "offer_type": "$10 redeem voucher",
            "message": "Mobile E2E test offer — redeem me!",
            "discount_value": "$10",
        })
        print("Offer created via API:", offer["id"])

        # Wait for the app's poll cycle (every 4s) to pick it up WITHOUT manual refresh
        page.wait_for_timeout(6000)
        offers_body = page.inner_text("body")
        offer_appeared = "Mobile E2E test offer" in offers_body
        print("New offer appeared in app via polling (no manual refresh):", offer_appeared)
        page.screenshot(path="/tmp/app_offers_new_arrived.png")

        # Tap Redeem voucher
        redeem_btn = page.get_by_text("Redeem voucher", exact=True).first
        redeem_btn.click()
        page.wait_for_timeout(1500)
        page.screenshot(path="/tmp/app_offers_after_redeem.png")

        redeemed_body = page.inner_text("body")
        print("UI shows Redeemed after tap:", "Redeemed" in redeemed_body)

        # Verify with the REAL backend that redemption actually happened (not just UI-local)
        server_state = api_get(f"/offers/customer/{test_customer_id}")
        this_offer = next(o for o in server_state if o["id"] == offer["id"])
        print("Backend confirms status:", this_offer["status"])
        assert this_offer["status"] == "redeemed", "Backend was not actually updated by the app's redeem tap"

        print("\nConsole errors:", console_errors if console_errors else "NONE")
        browser.close()

    print("\nMOBILE APP E2E TEST PASSED")

finally:
    backend.terminate(); appserver.terminate()
    time.sleep(1)
    backend.kill(); appserver.kill()
