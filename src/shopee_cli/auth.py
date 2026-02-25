"""Selenium-based login and cookie capture for Shopee."""

import time

import undetected_chromedriver as uc
from rich.console import Console

from shopee_cli.config import get_profile_dir, save_cookies

LOGIN_URL = "https://shopee.com.my/buyer/login"
POST_LOGIN_INDICATORS = ("shopee.com.my/user/", "shopee.com.my/?")
SESSION_COOKIE = "SPC_EC"

console = Console()


def login() -> list[dict]:
    """Open browser for manual Shopee login, capture and save cookies."""
    console.print("[bold]Opening Chrome for Shopee login...[/bold]")
    console.print("Please log in manually. The browser will close automatically once login is detected.\n")

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={get_profile_dir()}")

    driver = uc.Chrome(options=options)
    driver.get(LOGIN_URL)

    console.print("[dim]Waiting for login...[/dim]")
    try:
        while True:
            time.sleep(2)
            current_url = driver.current_url
            if any(indicator in current_url for indicator in POST_LOGIN_INDICATORS):
                break
            cookies = driver.get_cookies()
            if any(c["name"] == SESSION_COOKIE for c in cookies):
                break
    except Exception:
        console.print("[red]Browser was closed before login completed.[/red]")
        raise SystemExit(1)

    # Give a moment for all cookies to settle
    time.sleep(2)
    cookies = driver.get_cookies()
    driver.quit()

    if not any(c["name"] == SESSION_COOKIE for c in cookies):
        console.print("[red]Login failed - session cookie not found.[/red]")
        raise SystemExit(1)

    path = save_cookies(cookies)
    console.print(f"[green]Login successful! Cookies saved to {path}[/green]")
    return cookies
