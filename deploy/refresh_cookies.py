#!/usr/bin/env python3
"""
Refresh Firefox session using Playwright persistent context.

Run this as the `streamforge` user. It opens a headful Firefox using the
existing profile directory so the browser updates session cookies.
"""
import logging
import time
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_DIR = Path("/home/streamforge/.mozilla/firefox/streamforge-profile")
LOG_FILE = Path("/home/streamforge/playwright-refresh.log")


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Playwright refresh started")

    if not PROFILE_DIR.exists():
        logging.error("Firefox profile dir does not exist: %s", PROFILE_DIR)
        return 2

    try:
        with sync_playwright() as p:
            browser = p.firefox.launch_persistent_context(user_data_dir=str(PROFILE_DIR), headless=False, args=["--no-sandbox"]) 
            try:
                page = browser.new_page()
                # Visit YouTube home and account page to refresh session/cookies
                page.goto("https://www.youtube.com/", timeout=60000)
                time.sleep(6)
                page.goto("https://www.youtube.com/account", timeout=60000)
                time.sleep(4)
                logging.info("Visited YouTube; cookies refreshed")
            finally:
                browser.close()
    except Exception:
        logging.exception("Playwright refresh failed")
        return 1

    logging.info("Playwright refresh finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
