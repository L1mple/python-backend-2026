from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT = Path(__file__).parent / "docs" / "grafana-dashboard.png"
URL = "http://localhost:3000/d/shop-api/shop-api-monitoring?orgId=1&from=now-5m&to=now&refresh=5s&kiosk"


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(URL, wait_until="networkidle")
        page.wait_for_timeout(15_000)
        page.screenshot(path=OUTPUT, full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
