# shopee-cli

CLI tool to interact with [Shopee Malaysia](https://shopee.com.my) from the terminal.

Search products, view details, and check your orders — all without opening a browser.

## How it works

Shopee uses aggressive anti-bot measures (device fingerprinting, encrypted headers, CAPTCHAs). Instead of trying to reverse-engineer these, shopee-cli runs an off-screen Chrome browser via [undetected-chromedriver](https://github.com/ultrafunkula/undetected-chromedriver) and executes requests in a real browser context. The browser window is hidden — you just interact through the CLI.

For features that require login (orders), you authenticate once via `shopee login`, which opens a visible Chrome window for manual login. Session cookies are saved locally and reused until they expire.

## Installation

Requires Python 3.12+ and Chrome installed.

```bash
# Clone and install
git clone https://github.com/user/shopee-cli.git
cd shopee-cli
uv sync

# Or install with pip
pip install .
```

## Usage

### Search products

```bash
shopee search "mechanical keyboard"
shopee search "phone case" --limit 10 --sort price
```

### View product details

```bash
# By URL
shopee product "https://shopee.com.my/Product-Name-i.123456.789012"

# By shop_id.item_id
shopee product 123456.789012
```

### Log in (required for orders)

```bash
shopee login
```

Opens Chrome for manual login. Cookies are saved to `~/.config/shopee-cli/`.

### View orders

```bash
shopee orders
shopee orders --status "Shipping" --limit 10
```

## CAPTCHA handling

If Shopee triggers a CAPTCHA, shopee-cli will:

1. Attempt auto-solving via [2captcha](https://2captcha.com) (if `2CAPTCHA_API_KEY` is set)
2. Fall back to opening a visible browser for manual solving

To enable auto-solving, set the API key:

```bash
export 2CAPTCHA_API_KEY=your_key_here
```

## Configuration

All data is stored in `~/.config/shopee-cli/`:

| File | Purpose |
|------|---------|
| `cookies.json` | Session cookies (auto-expires after 24h) |
| `chrome-profile/` | Persistent Chrome profile |

## Development

```bash
# Install dependencies
uv sync

# Run from source
uv run shopee --help

# Scripts for API exploration
python scripts/explore_api.py /search/search_items keyword=phone limit=5
python scripts/capture_traffic.py
```

## License

MIT
