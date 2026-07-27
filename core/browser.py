"""Browser automation helper — fetches cookies and rendered page source via Selenium."""
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _make_driver(headless=True, performance_logging=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    if performance_logging:
        opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def fetch_page(url, headless=True, wait_seconds=8, wait_selector=None):
    """Open a URL, wait for load, return (cookies_list, page_source, driver).

    Caller MUST call driver.quit() when done.
    """
    driver = _make_driver(headless=headless)
    driver.get(url)

    if wait_selector:
        try:
            WebDriverWait(driver, wait_seconds).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        except Exception:
            pass
    else:
        time.sleep(wait_seconds)

    cookies = driver.get_cookies()
    html = driver.page_source
    return cookies, html, driver


def cookies_to_header(cookies):
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies)
