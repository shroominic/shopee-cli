"""Automatic CAPTCHA solving for Shopee using 2captcha.

Shopee uses a custom slider puzzle CAPTCHA (#NEW_CAPTCHA):
- Background image with a puzzle piece cutout
- A moveable puzzle piece (#puzzleImgComponent)
- A slider handle (#sliderContainer) to drag horizontally

We screenshot the CAPTCHA, send to 2captcha to find the target position,
then simulate dragging the slider.
"""

import base64
import json
import os
import time
import urllib.request
import urllib.error
from pathlib import Path

from rich.console import Console

console = Console()

API_BASE = "https://api.2captcha.com"
MAX_ATTEMPTS = 8
POLL_INTERVAL = 2
POLL_TIMEOUT = 60


def get_api_key() -> str | None:
    """Load 2CAPTCHA_API_KEY from environment or .env files."""
    key = os.environ.get("2CAPTCHA_API_KEY")
    if key:
        return key

    for env_path in (
        Path.cwd() / ".env",
        Path.cwd().parent / ".env",
        Path(__file__).resolve().parent.parent.parent.parent / ".env",
    ):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("2CAPTCHA_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# 2captcha API helpers
# ---------------------------------------------------------------------------

def _api_request(endpoint: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API_BASE}/{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _create_task(api_key: str, image_b64: str) -> str | None:
    result = _api_request("createTask", {
        "clientKey": api_key,
        "task": {
            "type": "CoordinatesTask",
            "body": image_b64,
            "comment": "Click on the position where the puzzle piece should be placed",
        },
    })
    if result.get("errorId", 1) != 0:
        console.print(f"[dim]2captcha error: {result.get('errorDescription', 'unknown')}[/dim]")
        return None
    return str(result.get("taskId", ""))


def _get_result(api_key: str, task_id: str, driver=None) -> list[dict] | None:
    """Poll for result. Sends keepalive events and checks CAPTCHA state.

    Returns coordinates if 2captcha solved it while CAPTCHA is still alive.
    Returns None if CAPTCHA expired or 2captcha failed.
    """
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)

        # Keep CAPTCHA alive by simulating mouse activity
        if driver:
            try:
                driver.execute_script(_KEEPALIVE_JS)
                # Early exit if CAPTCHA expired (don't waste time polling)
                alive = driver.execute_script(
                    "return !!document.querySelector('#sliderContainer')"
                )
                if not alive:
                    console.print("[dim]CAPTCHA expired while waiting for 2captcha[/dim]")
                    return None
            except Exception:
                pass

        result = _api_request("getTaskResult", {
            "clientKey": api_key,
            "taskId": task_id,
        })
        if result.get("errorId", 1) != 0:
            console.print(f"[dim]2captcha poll error: {result.get('errorDescription', 'unknown')}[/dim]")
            return None
        if result.get("status") == "ready":
            return result.get("solution", {}).get("coordinates", [])
    console.print("[dim]2captcha timeout[/dim]")
    return None


def _report(api_key: str, task_id: str, correct: bool) -> None:
    try:
        action = "reportCorrect" if correct else "reportIncorrect"
        _api_request(action, {"clientKey": api_key, "taskId": task_id})
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def solve_captcha(driver) -> bool:
    """Attempt to solve the Shopee CAPTCHA automatically.

    Returns True if CAPTCHA was solved, False if all attempts failed.
    """
    api_key = get_api_key()
    if not api_key:
        console.print("[dim]No 2CAPTCHA_API_KEY found, skipping auto-solve.[/dim]")
        return False

    _wait_for_captcha_widget(driver)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        console.print(f"[dim]Auto-solving CAPTCHA (attempt {attempt}/{MAX_ATTEMPTS})...[/dim]")

        try:
            # Dismiss any overlapping modals (e.g. language selection)
            _dismiss_modals(driver)

            # Verify slider is present and get the CAPTCHA area bounds
            captcha_bounds = driver.execute_script(_GET_CAPTCHA_BOUNDS_JS)
            if not captcha_bounds:
                console.print("[dim]No CAPTCHA elements found[/dim]")
                _refresh_captcha(driver)
                continue

            # Screenshot and crop to just the CAPTCHA area.
            # This gives 2captcha workers a clean view and simplifies
            # coordinate mapping (returned X is directly in image space).
            screenshot_png = driver.get_screenshot_as_png()
            cropped_b64, crop_info = _crop_captcha(
                screenshot_png, captcha_bounds
            )

            # Submit cropped image to 2captcha
            task_id = _create_task(api_key, cropped_b64)
            if not task_id:
                continue

            # Poll for result (keepalive events between polls)
            coords = _get_result(api_key, task_id, driver=driver)
            if not coords:
                continue

            target_x = coords[0]["x"]
            target_y = coords[0]["y"]
            console.print(f"[dim]2captcha target in crop: ({target_x}, {target_y})[/dim]")

            # Check if CAPTCHA is still alive
            slider_alive = driver.execute_script(
                "return !!document.querySelector('#sliderContainer')"
            )
            if not slider_alive:
                console.print("[dim]CAPTCHA expired, refreshing...[/dim]")
                _report(api_key, task_id, False)
                _refresh_captcha(driver)
                continue

            # Map 2captcha coordinates back to page coordinates
            page_x = target_x + crop_info["left"]

            # Re-fetch layout for current element positions
            layout = driver.execute_script(_GET_LAYOUT_JS)
            if not layout:
                _report(api_key, task_id, False)
                _refresh_captcha(driver)
                continue

            # Calculate drag distance
            img_left = layout["img_x"]
            piece_w = layout["piece_w"]
            slider_w = layout["slider_w"]
            track_w = layout["track_w"]

            # page_x is the CENTER of where the piece should go
            slot_in_image = page_x - img_left
            drag_distance = slot_in_image - piece_w / 2
            max_drag = track_w - slider_w
            drag_distance = max(0.0, min(drag_distance, max_drag))

            console.print(
                f"[dim]Drag: {drag_distance:.0f}px "
                f"(slot={slot_in_image:.0f}, piece_w={piece_w:.0f}, "
                f"max={max_drag:.0f})[/dim]"
            )

            # Execute the drag
            if _do_drag_and_check(driver, drag_distance):
                _report(api_key, task_id, True)
                return True

            console.print("[dim]Solution rejected[/dim]")
            _report(api_key, task_id, False)
            _refresh_captcha(driver)

        except Exception as e:
            console.print(f"[dim]Auto-solve error: {e}[/dim]")
            _refresh_captcha(driver)
            continue

    console.print("[yellow]Auto-solve failed after all attempts.[/yellow]")
    return False


def _crop_captcha(screenshot_png: bytes, bounds: dict) -> tuple[str, dict]:
    """Crop full-page screenshot to just the CAPTCHA area.

    Returns (base64_image, crop_info) where crop_info has the offset
    for mapping coordinates back to page space.
    """
    import io
    from PIL import Image

    img = Image.open(io.BytesIO(screenshot_png))

    # Use the CAPTCHA widget bounds with some margin
    left = max(0, int(bounds["x"]) - 10)
    top = max(0, int(bounds["y"]) - 10)
    right = min(img.width, int(bounds["x"] + bounds["width"]) + 10)
    bottom = min(img.height, int(bounds["y"] + bounds["height"]) + 10)

    cropped = img.crop((left, top, right, bottom))

    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    return b64, {"left": left, "top": top}


def _do_drag_and_check(driver, drag_distance: float) -> bool:
    """Drag the slider and check if CAPTCHA was solved."""
    success = driver.execute_script(_DRAG_SLIDER_JS, drag_distance)
    if not success:
        console.print("[dim]Slider drag failed[/dim]")
        return False
    time.sleep(3)
    h1 = driver.execute_script(
        "return document.querySelector('h1')?.innerText || ''"
    )
    if "verify" not in h1.lower():
        console.print("[green]CAPTCHA solved automatically![/green]")
        return True
    return False


def _dismiss_modals(driver) -> None:
    """Dismiss overlapping modals (like Shopee's language selector)."""
    driver.execute_script("""
        // Close language selection modal if present
        const modal = document.querySelector('.shopee-popup__close-btn');
        if (modal) modal.click();

        // Also try clicking away any overlay
        const overlay = document.querySelector('.shopee-modal__overlay');
        if (overlay) overlay.click();

        // Click "English" if language selector is showing
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            if (btn.textContent.trim() === 'English') {
                btn.click();
                break;
            }
        }
    """)
    time.sleep(0.5)


def _refresh_captcha(driver) -> None:
    """Get a fresh CAPTCHA by navigating to the current URL."""
    url = driver.current_url
    driver.get(url)
    time.sleep(4)
    _dismiss_modals(driver)
    _wait_for_captcha_widget(driver, timeout=20)


def _wait_for_captcha_widget(driver, timeout: float = 15) -> None:
    """Wait for the CAPTCHA slider widget to appear in the DOM."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = driver.execute_script(
            "return !!document.querySelector('#sliderContainer')"
        )
        if found:
            time.sleep(1)
            return
        time.sleep(1)
    console.print("[dim]CAPTCHA widget did not appear in time[/dim]")


# ---------------------------------------------------------------------------
# JavaScript constants
# ---------------------------------------------------------------------------

# Get the bounding box of the entire CAPTCHA widget (for screenshot cropping).
_GET_CAPTCHA_BOUNDS_JS = """
const captcha = document.querySelector('#NEW_CAPTCHA');
const slider = document.querySelector('#sliderContainer');
if (!captcha || !slider) return null;

const cr = captcha.getBoundingClientRect();
const sr = slider.getBoundingClientRect();

// Combine the captcha container and slider into one bounding box
const x = Math.min(cr.x, sr.x);
const y = Math.min(cr.y, sr.y);
const right = Math.max(cr.x + cr.width, sr.x + sr.width);
const bottom = Math.max(cr.y + cr.height, sr.y + sr.height);

return {x: x, y: y, width: right - x, height: bottom - y};
"""

# Get CAPTCHA element positions.
_GET_LAYOUT_JS = """
const slider = document.querySelector('#sliderContainer');
if (!slider) return null;
const captcha = document.querySelector('#NEW_CAPTCHA');
if (!captcha) return null;
const imgs = captcha.querySelectorAll('img');
let bgImg = null;
for (const img of imgs) {
    const r = img.getBoundingClientRect();
    if (r.width > 100) { bgImg = img; break; }
}
if (!bgImg) return null;
const piece = document.querySelector('#puzzleImgComponent');
const sr = slider.getBoundingClientRect();
const ir = bgImg.getBoundingClientRect();
const pr = piece ? piece.getBoundingClientRect() : {width: 44};
let track = slider.parentElement;
let tr = track.getBoundingClientRect();
if (tr.width < ir.width) { tr = {width: ir.width, x: ir.x}; }
return {
    slider_x: sr.x, slider_y: sr.y + sr.height / 2, slider_w: sr.width,
    img_x: ir.x, img_y: ir.y, img_w: ir.width,
    piece_w: pr.width, track_w: tr.width, track_x: tr.x,
};
"""

# Drag the slider handle by a given pixel distance using mouse events.
_DRAG_SLIDER_JS = """
const distance = arguments[0];
const slider = document.querySelector('#sliderContainer');
if (!slider) return false;

const rect = slider.getBoundingClientRect();
const startX = rect.x + rect.width / 2;
const startY = rect.y + rect.height / 2;

slider.dispatchEvent(new MouseEvent('mousedown', {
    clientX: startX, clientY: startY, bubbles: true, cancelable: true
}));

const steps = 30 + Math.floor(Math.random() * 15);
for (let i = 1; i <= steps; i++) {
    const progress = i / steps;
    const eased = 1 - Math.pow(1 - progress, 2);
    const currentX = startX + distance * eased;
    const wobbleY = startY + (Math.random() - 0.5) * 2;
    document.dispatchEvent(new MouseEvent('mousemove', {
        clientX: currentX, clientY: wobbleY, bubbles: true, cancelable: true
    }));
}

document.dispatchEvent(new MouseEvent('mouseup', {
    clientX: startX + distance, clientY: startY, bubbles: true, cancelable: true
}));
return true;
"""

# Keep CAPTCHA alive with mouse activity over the widget.
_KEEPALIVE_JS = """
const captcha = document.querySelector('#NEW_CAPTCHA');
const slider = document.querySelector('#sliderContainer');
if (!captcha) return;

// Move mouse over the captcha area
const rect = captcha.getBoundingClientRect();
const x = rect.x + rect.width / 2 + (Math.random() - 0.5) * 40;
const y = rect.y + rect.height / 2 + (Math.random() - 0.5) * 20;
document.dispatchEvent(new MouseEvent('mousemove', {
    clientX: x, clientY: y, bubbles: true, cancelable: true
}));

// Also hover over the slider specifically
if (slider) {
    const sr = slider.getBoundingClientRect();
    slider.dispatchEvent(new MouseEvent('mouseover', {
        clientX: sr.x + sr.width / 2, clientY: sr.y + sr.height / 2,
        bubbles: true, cancelable: true
    }));
}
"""
