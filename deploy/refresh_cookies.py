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
import sqlite3
import tempfile
import json

PROFILE_DIR = Path("/home/streamforge/.mozilla/firefox/streamforge-profile")
LOG_FILE = Path("/home/streamforge/playwright-refresh.log")
OUTPUT_COOKIES = Path("/home/streamforge/firefox-cookies.txt")


def read_firefox_cookies(sqlite_path: Path):
    if not sqlite_path.exists():
        return []
    con = sqlite3.connect(str(sqlite_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    try:
        cur.execute("SELECT name, value, host, path, expiry, isSecure, isHttpOnly FROM moz_cookies")
        rows = cur.fetchall()
    except Exception:
        return []
    finally:
        con.close()
    cookies = []
    for r in rows:
        cookies.append({
            "name": r["name"],
            "value": r["value"],
            "domain": r["host"],
            "path": r["path"],
            "expires": int(r["expiry"]) if r["expiry"] else None,
            "secure": bool(r["isSecure"]),
            "httpOnly": bool(r["isHttpOnly"]),
        })
    return cookies


def write_netscape_cookies(cookies, out_path: Path):
    # Netscape format: domain \t include_subdomains(T/F) \t path \t secure(T/F) \t expiry \t name \t value
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure") else "FALSE"
            expires = str(int(c.get("expires") or 0))
            name = c.get("name", "")
            value = c.get("value", "")
            f.write("\t".join([domain, include_subdomains, path, secure, expires, name, value]) + "\n")


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Playwright refresh started")

    # Try to read Firefox cookies.sqlite from profile (non-locking read)
    cookies_db = PROFILE_DIR / "cookies.sqlite"
    ff_cookies = read_firefox_cookies(cookies_db)
    logging.info("Read %d cookies from firefox sqlite", len(ff_cookies))

    try:
        with sync_playwright() as p:
            # create a temporary profile for Playwright to avoid locking the real profile
            with tempfile.TemporaryDirectory(prefix="pw-profile-") as tmpdir:
                browser = p.firefox.launch_persistent_context(user_data_dir=tmpdir, headless=True)
                try:
                    # import cookies into the new context
                    context = browser
                    to_add = []
                    for c in ff_cookies:
                        # Playwright expects 'domain' without leading dot for add_cookies
                        domain = c["domain"]
                        # Build Playwright cookie dict
                        cookie = {
                            "name": c["name"],
                            "value": c["value"],
                            "domain": domain,
                            "path": c.get("path", "/"),
                            "expires": c.get("expires") or None,
                            "httpOnly": c.get("httpOnly", False),
                            "secure": c.get("secure", False),
                        }
                        to_add.append(cookie)
                    if to_add:
                        # Playwright requires a page to set cookies for some browsers
                        page = context.new_page()
                        page.goto("https://www.youtube.com/", timeout=60000)
                        context.add_cookies(to_add)
                    else:
                        page = context.new_page()
                        page.goto("https://www.youtube.com/", timeout=60000)

                    # visit account page to refresh session
                    time.sleep(2)
                    page.goto("https://www.youtube.com/account", timeout=60000)
                    time.sleep(4)

                    # export cookies from context and write netscape file for yt-dlp
                    exported = context.cookies()
                    write_netscape_cookies(exported, OUTPUT_COOKIES)
                    logging.info("Exported %d cookies to %s", len(exported), OUTPUT_COOKIES)
                finally:
                    browser.close()
    except Exception:
        logging.exception("Playwright refresh failed")
        return 1

    logging.info("Playwright refresh finished")
    return 0


if __name__ == "__main__":
    sys.exit(main())
