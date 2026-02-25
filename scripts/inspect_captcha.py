#!/usr/bin/env python3
"""Trigger and inspect Shopee CAPTCHA by rapid page loads."""

import json
import shutil
import time

import undetected_chromedriver as uc

from shopee_cli.config import get_config_dir

profile = get_config_dir() / "chrome-profile-test"
profile.mkdir(parents=True, exist_ok=True)

options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={profile}")
options.add_argument("--window-position=-2000,-2000")
options.add_argument("--window-size=1280,720")

driver = uc.Chrome(options=options)

# Hit search pages rapidly to trigger CAPTCHA
for i in range(10):
    url = f"https://shopee.com.my/search?keyword=test{i}&by=relevancy"
    driver.get(url)
    time.sleep(2)

    h1 = driver.execute_script("return document.querySelector('h1')?.innerText || document.title || ''")
    print(f"  [{i}] H1: {h1[:60]}")

    if "verify" in h1.lower():
        print("  CAPTCHA triggered!")
        driver.save_screenshot("/tmp/shopee_captcha_unauth.png")
        print("  Screenshot: /tmp/shopee_captcha_unauth.png")

        tree = driver.execute_script("""
            const captcha = document.querySelector('#NEW_CAPTCHA');
            if (!captcha) return 'no #NEW_CAPTCHA found';
            return captcha.innerHTML;
        """)
        print(f"\n  #NEW_CAPTCHA innerHTML ({len(tree)} chars):")
        print(tree[:4000])
        break

driver.quit()
shutil.rmtree(profile, ignore_errors=True)
