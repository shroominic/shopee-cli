"""Browser-based HTTP client for Shopee API.

Uses undetected-chromedriver to execute fetch() calls in a real browser context,
bypassing Shopee's anti-bot measures (af-ac-enc-dat, TLS fingerprinting, etc.).

Runs with the browser hidden off-screen. If a CAPTCHA appears, tries 2captcha
auto-solve first. Only moves the browser on-screen as a last resort for human solving.
"""

import json
import time
from typing import Any
from urllib.parse import urlencode

import undetected_chromedriver as uc
from rich.console import Console

from shopee_cli.captcha import solve_captcha
from shopee_cli.config import get_profile_dir, load_cookies

BASE_URL = "https://shopee.com.my/api/v4"

console = Console()


class SessionExpired(Exception):
    pass


def _make_driver(*, visible: bool = False) -> uc.Chrome:
    """Create an undetected Chrome driver.

    By default the window is positioned off-screen so the user doesn't see it.
    Set visible=True to place it on-screen (for manual CAPTCHA solving).
    """
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={get_profile_dir()}")
    if not visible:
        options.add_argument("--window-position=-2000,-2000")
    options.add_argument("--window-size=1280,720")
    return uc.Chrome(options=options)


def _inject_cookies(driver: uc.Chrome, cookies: list[dict]) -> None:
    """Load Shopee and inject session cookies."""
    driver.get("https://shopee.com.my")
    time.sleep(2)
    for c in cookies:
        cookie = {"name": c["name"], "value": c["value"]}
        if "domain" in c:
            cookie["domain"] = c["domain"]
        if "path" in c:
            cookie["path"] = c["path"]
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass
    driver.get("https://shopee.com.my")
    time.sleep(3)


class ShopeeClient:
    """Browser-backed client that makes API calls via off-screen Chrome.

    Pass require_auth=False for unauthenticated browsing (search, products).
    Authenticated features (orders, cart) need require_auth=True (default).
    """

    def __init__(self, *, require_auth: bool = True) -> None:
        self._cookies = load_cookies()

        if require_auth and self._cookies is None:
            console.print("[red]No valid session found. Run 'shopee login' first.[/red]")
            raise SystemExit(1)

        self._driver = _make_driver(visible=False)
        if self._cookies:
            _inject_cookies(self._driver, self._cookies)
        else:
            # Just navigate to Shopee for an unauthenticated session
            self._driver.get("https://shopee.com.my")
            time.sleep(3)

    def get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        """Make a GET request via browser fetch()."""
        url = BASE_URL + path
        if params:
            url += "?" + urlencode(params)
        return self._fetch(url)

    def post(self, path: str, json_data: dict | None = None) -> dict[str, Any]:
        """Make a POST request via browser fetch()."""
        url = BASE_URL + path
        body = json.dumps(json_data) if json_data else "null"
        return self._fetch(url, method="POST", body=body)

    def navigate(self, url: str, wait: float = 5.0) -> None:
        """Navigate the browser to a URL and wait for page load."""
        self._driver.get(url)
        time.sleep(wait)
        self._handle_captcha(url)

    def run_js(self, script: str) -> Any:
        """Execute JavaScript in the browser and return the result."""
        return self._driver.execute_script(script)

    def _fetch(self, url: str, method: str = "GET", body: str | None = None) -> dict[str, Any]:
        """Execute a fetch() call inside the browser and return parsed JSON."""
        if method == "GET":
            js = f"""
                const resp = await fetch("{url}");
                const text = await resp.text();
                return {{status: resp.status, body: text}};
            """
        else:
            js = f"""
                const resp = await fetch("{url}", {{
                    method: "{method}",
                    headers: {{"Content-Type": "application/json"}},
                    body: {body}
                }});
                const text = await resp.text();
                return {{status: resp.status, body: text}};
            """

        result = self._driver.execute_script(js)
        status = result["status"]
        raw = result["body"]

        if status in (401, 403):
            try:
                data = json.loads(raw)
                if data.get("error") == 90309999:
                    console.print("[red]Anti-bot challenge triggered. Try again or re-login.[/red]")
                    raise SessionExpired("Anti-bot block.")
            except (json.JSONDecodeError, TypeError):
                pass
            raise SessionExpired("Session expired. Run 'shopee login' to re-authenticate.")

        data = json.loads(raw)
        if data.get("error") and data["error"] != 0:
            if data["error"] == 90309999:
                console.print("[red]Anti-bot challenge triggered. Try again or re-login.[/red]")
            else:
                error_msg = data.get("error_msg", f"API error code: {data['error']}")
                console.print(f"[red]API Error: {error_msg}[/red]")
        return data

    def _is_captcha_page(self) -> bool:
        """Check if current page is a CAPTCHA/verification page."""
        try:
            result = self._driver.execute_script(
                "return document.querySelector('h1')?.innerText || document.title || ''"
            )
            return "verify" in (result or "").lower()
        except Exception:
            return False

    def _handle_captcha(self, original_url: str) -> None:
        """Handle CAPTCHA: try 2captcha (off-screen), fall back to visible browser for human."""
        if not self._is_captcha_page():
            return

        console.print("[yellow]CAPTCHA detected![/yellow]")

        # Try auto-solve (browser stays off-screen)
        if solve_captcha(self._driver):
            time.sleep(2)
            return

        # Auto-solve failed — bring browser on-screen for human
        console.print("[yellow]Opening browser for manual CAPTCHA solve...[/yellow]")
        self._driver.quit()

        visible = _make_driver(visible=True)
        if self._cookies:
            _inject_cookies(visible, self._cookies)
        else:
            visible.get("https://shopee.com.my")
            time.sleep(2)
        visible.get(original_url)
        time.sleep(3)

        input("Press Enter once you've solved the CAPTCHA...")
        visible.quit()
        time.sleep(1)

        # Reopen off-screen and retry
        self._driver = _make_driver(visible=False)
        if self._cookies:
            _inject_cookies(self._driver, self._cookies)
        else:
            self._driver.get("https://shopee.com.my")
            time.sleep(2)
        self._driver.get(original_url)
        time.sleep(5)

    def close(self) -> None:
        try:
            self._driver.quit()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
