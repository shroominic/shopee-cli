#!/usr/bin/env python3
"""Test the auto-solver against a Shopee CAPTCHA."""

import shutil
import time

import undetected_chromedriver as uc

from shopee_cli.captcha import solve_captcha
from shopee_cli.config import get_config_dir

profile = get_config_dir() / "chrome-profile-test4"
profile.mkdir(parents=True, exist_ok=True)

options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={profile}")
options.add_argument("--window-position=-2000,-2000")
options.add_argument("--window-size=1280,720")

driver = uc.Chrome(options=options)

# Hit pages rapidly to get flagged
for i in range(15):
    driver.get(f"https://shopee.com.my/search?keyword=test{i}")
    time.sleep(1)
    h1 = driver.execute_script("return document.querySelector('h1')?.innerText || ''")
    if "verify" in h1.lower():
        print(f"CAPTCHA triggered after {i+1} requests!")
        break
else:
    print("Could not trigger CAPTCHA after 15 attempts")
    driver.quit()
    shutil.rmtree(profile, ignore_errors=True)
    exit()

print("Attempting auto-solve...")
result = solve_captcha(driver)
print(f"Solve result: {result}")

h1_after = driver.execute_script("return document.querySelector('h1')?.innerText || document.title || ''")
print(f"H1 after: {h1_after}")

driver.quit()
shutil.rmtree(profile, ignore_errors=True)
