from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT_DIR = Path(__file__).parent / "docs"
DASHBOARDS = {
    "grafana-dashboard.png": "shop-api/shop-api-monitoring",
    "grafana-business-dashboard.png": "shop-business/shop-business-metrics",
}


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        for filename, dashboard_path in DASHBOARDS.items():
            url = (
                f"http://localhost:3000/d/{dashboard_path}"
                "?orgId=1&from=now-5m&to=now&refresh=5s&kiosk"
            )
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(10_000)
            page.screenshot(path=OUTPUT_DIR / filename, full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
