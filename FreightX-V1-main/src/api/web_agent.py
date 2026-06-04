"""
===========================================================
TRIMBLE MAPS API KEY AUTOMATION
FINAL STABLE PLAYWRIGHT VERSION
===========================================================

FLOW
-----------------------------------------------------------
1. Generate random names
2. Open temp-mail
3. Click random button
4. Read NEW email from top box
5. Open Trimble
6. Fill form
7. Submit form
8. Return to inbox
9. Refresh inbox
10. Wait for API email
11. Extract API key
12. Store latest key in .env
13. Close browser

===========================================================
INSTALL
-----------------------------------------------------------

pip install playwright python-dotenv

Then run:

playwright install

===========================================================
IMPORTANT
-----------------------------------------------------------

- CLOSE ALL CHROME WINDOWS before running
- First run may require manual Cloudflare verification
- Browser runs in visible mode
- Uses REAL Chrome profile

===========================================================
"""

import re
import random
import string
import time
from pathlib import Path

from dotenv import set_key
from playwright.sync_api import sync_playwright

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILE = _REPO_ROOT / ".env"
_PLAYWRIGHT_PROFILE = _REPO_ROOT / "playwright_profile"


def random_string(length=8):
    return "".join(random.choices(string.ascii_lowercase, k=length))


def refresh_trimble_api_key() -> bool:
    """Run Playwright flow to obtain a new Trimble API key and save it to .env."""
    api_key = None

    with sync_playwright() as p:
        first_name = random_string()
        last_name = random_string()

        print("\n===================================")
        print("GENERATED USER DETAILS")
        print("===================================\n")

        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(_PLAYWRIGHT_PROFILE),
            channel="chrome",
            headless=False,
            slow_mo=50,
        )

        page = browser.new_page()

        print("\n===================================")
        print("OPENING TEMP MAIL")
        print("===================================\n")

        page.goto(
            "https://temp-mail.io/en",
            wait_until="domcontentloaded",
            timeout=120000,
        )

        time.sleep(5)

        if "cloudflare" in page.title().lower():
            print("\nCLOUDFLARE DETECTED")
            print("Solve manually then press ENTER")
            input()

        print("\nGENERATING BRAND NEW EMAIL...\n")

        try:
            page.get_by_role("button", name="random").click()
            print("RANDOM BUTTON CLICKED")
        except Exception as e:
            print("RANDOM BUTTON ERROR:", e)

        print("\nWAITING FOR NEW EMAIL...\n")
        time.sleep(5)

        email = None
        email_selectors = [
            'input[type="email"]',
            'input[readonly]',
            'input[value*="@"]',
        ]

        for attempt in range(20):
            print(f"CHECKING EMAIL BOX... {attempt + 1}/20")
            try:
                for selector in email_selectors:
                    locator = page.locator(selector).first
                    if locator.count() > 0:
                        current_email = locator.input_value().strip()
                        if current_email and "@" in current_email:
                            email = current_email
                            break
                if email:
                    break
            except Exception as e:
                print("EMAIL EXTRACTION ERROR:", e)
            time.sleep(2)

        if not email:
            print("\nFAILED TO GET NEW EMAIL")
            browser.close()
            return False

        trimble_page = browser.new_page()

        print("\n===================================")
        print("OPENING TRIMBLE")
        print("===================================\n")

        trimble_page.goto(
            "https://developer.trimblemaps.com/get-an-api-key/na/",
            wait_until="domcontentloaded",
            timeout=120000,
        )

        time.sleep(2)

        try:
            trimble_page.get_by_text("Accept All", exact=False).click()
            print("COOKIES ACCEPTED")
        except Exception:
            pass

        print("\nFILLING FORM...\n")

        try:
            trimble_page.get_by_label("First Name", exact=False).fill(first_name)
            print("FIRST NAME FILLED")
        except Exception as e:
            print("FIRST NAME ERROR:", e)

        try:
            trimble_page.get_by_label("Last Name", exact=False).fill(last_name)
            print("LAST NAME FILLED")
        except Exception as e:
            print("LAST NAME ERROR:", e)

        try:
            trimble_page.get_by_label("Email", exact=False).fill(email)
            print("EMAIL FILLED")
        except Exception as e:
            print("EMAIL ERROR:", e)

        print("\nCHECKING TERMS...\n")

        try:
            trimble_page.locator('input[type="checkbox"]').first.check()
            print("CHECKBOX CHECKED")
        except Exception as e:
            print("CHECKBOX ERROR:", e)

        print("\nSUBMITTING FORM...\n")

        try:
            trimble_page.get_by_text("Email My API Key Now", exact=False).click()
            print("FORM SUBMITTED")
        except Exception as e:
            print("BUTTON ERROR:", e)

        page.bring_to_front()

        print("\nREFRESHING INBOX...\n")

        try:
            page.reload(wait_until="networkidle")
        except Exception:
            pass

        time.sleep(5)

        print("\n===================================")
        print("WAITING FOR API EMAIL")
        print("===================================\n")

        for attempt in range(40):
            print(f"CHECKING INBOX... {attempt + 1}/40")

            try:
                email_subject = page.get_by_text(
                    "Your Trial API Key is Here",
                    exact=False,
                )

                if email_subject.count() > 0:
                    print("\nEMAIL RECEIVED!")
                    email_subject.first.click()
                    time.sleep(5)

                    body_text = page.locator("body").inner_text()
                    api_matches = re.findall(r"\b[A-Z0-9]{20,}\b", body_text)

                    if api_matches:
                        api_key = api_matches[0]
                        break

                page.reload(wait_until="networkidle")

            except Exception as e:
                print("INBOX ERROR:", e)

            time.sleep(5)

        print("\n===================================")
        print("RESULT")
        print("===================================\n")

        if api_key:
            set_key(
                str(_ENV_FILE),
                "TRIMBLE_API_KEY",
                api_key,
                quote_mode="never",
            )
            print(f"\nAPI KEY SAVED TO {_ENV_FILE}")
        else:
            print("NO API KEY FOUND")

        print("\nCLOSING BROWSER...")
        time.sleep(2)
        browser.close()

    return api_key is not None


if __name__ == "__main__":
    success = refresh_trimble_api_key()
    raise SystemExit(0 if success else 1)
