#!/usr/bin/env python3
"""Helper to capture and log Shopee API calls from a browser session.

Uses Selenium with Chrome DevTools Protocol to log network requests
to shopee.com.my/api/v4/ endpoints.
"""

import json
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def main():
    options = webdriver.ChromeOptions()
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_argument("--disable-blink-features=AutomationControlled")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    print("Browser opened. Browse Shopee normally.")
    print("API calls to /api/v4/ will be logged here.")
    print("Press Ctrl+C to stop.\n")

    driver.get("https://shopee.com.my")
    seen = set()

    try:
        while True:
            time.sleep(2)
            logs = driver.get_log("performance")
            for entry in logs:
                try:
                    msg = json.loads(entry["message"])["message"]
                    if msg["method"] == "Network.requestWillBeSent":
                        url = msg["params"]["request"]["url"]
                        if "/api/v4/" in url and url not in seen:
                            seen.add(url)
                            method = msg["params"]["request"]["method"]
                            print(f"[{method}] {url}")
                except (KeyError, json.JSONDecodeError):
                    pass
    except KeyboardInterrupt:
        print(f"\nCaptured {len(seen)} unique API calls.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
