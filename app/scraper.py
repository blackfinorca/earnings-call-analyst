"""
Scraper utilities for Yahoo Finance earnings calendar.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, List

from playwright.async_api import Browser, Error as PlaywrightError, Page, TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from .utils import choose_user_agent, date_sequence

LOGGER = logging.getLogger("app.scraper")

EARNINGS_URL = "https://finance.yahoo.com/calendar/earnings"


@dataclass(slots=True)
class DayResult:
    """Structured result for a single day's earnings rows."""

    day: str
    url: str
    count: int
    rows: list[dict[str, Any]]
    error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "url": self.url,
            "count": self.count,
            "rows": self.rows,
            "error": self.error,
        }


class YahooEarningsScraper:
    """Scrape Yahoo Finance earnings calendar for a set of days."""

    def __init__(
        self,
        delay_range: tuple[float, float] = (1.2, 2.0),
        max_retries: int = 3,
    ) -> None:
        self.delay_range = delay_range
        self.max_retries = max_retries

    async def fetch_window(self, start: date, days: int) -> List[dict[str, Any]]:
        """Fetch earnings data for [start, start+days)."""
        target_dates = date_sequence(start, days)

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                results: list[DayResult] = []
                for index, target in enumerate(target_dates):
                    ua = choose_user_agent(seed=index)
                    context = await browser.new_context(user_agent=ua, locale="en-US")
                    page = await context.new_page()
                    try:
                        day_result = await self._fetch_day(page, target, attempt_seed=index)
                    finally:
                        await context.close()

                    results.append(day_result)
                    # Gentle pacing between days
                    await asyncio.sleep(random.uniform(*self.delay_range))
            finally:
                await browser.close()

        return [res.to_dict() for res in results]

    async def _fetch_day(self, page: Page, target: date, attempt_seed: int) -> DayResult:
        day_iso = target.isoformat()
        start_param = (target - timedelta(days=5)).isoformat()
        end_param = (target + timedelta(days=5)).isoformat()
        url = f"{EARNINGS_URL}?from={start_param}&to={end_param}&day={day_iso}"

        for attempt in range(1, self.max_retries + 1):
            try:
                await page.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.8"})
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_selector("table tbody tr", timeout=12_000)
                except PlaywrightTimeout:
                    LOGGER.warning("No rows found for %s (attempt %s)", day_iso, attempt)
                    return DayResult(day=day_iso, url=url, count=0, rows=[], error="No rows available")

                rows_locator = page.locator("table tbody tr")
                row_count = await rows_locator.count()
                rows: list[dict[str, Any]] = []
                for idx in range(row_count):
                    row = rows_locator.nth(idx)
                    cells = row.locator("td")
                    cell_texts = []
                    for cell_index in range(6):
                        try:
                            cell_text = await cells.nth(cell_index).inner_text()
                        except PlaywrightError:
                            cell_text = ""
                        cell_texts.append(cell_text.strip())

                    symbol = cell_texts[0] or None
                    company = cell_texts[1] or None
                    eps_estimate = cell_texts[2] or None
                    eps_reported = cell_texts[3] or None
                    surprise_pct = cell_texts[4] or None
                    time_label = (cell_texts[5] or "Time Not Supplied").replace("Before Market Open", "Before Open").replace("After Market Close", "After Close")

                    quote_link = None
                    try:
                        anchor = row.locator("td:nth-child(1) a[href^='/quote/']").first
                        href = await anchor.get_attribute("href")
                        if href:
                            quote_link = f"https://finance.yahoo.com{href}"
                    except PlaywrightError:
                        quote_link = None

                    rows.append(
                        {
                            "symbol": symbol,
                            "company": company,
                            "eps_estimate": eps_estimate,
                            "eps_reported": eps_reported,
                            "surprise_pct": surprise_pct,
                            "time": time_label or "Time Not Supplied",
                            "quote_url": quote_link,
                        }
                    )

                return DayResult(day=day_iso, url=url, count=len(rows), rows=rows, error=None)
            except PlaywrightError as exc:
                wait_time = 2 ** (attempt - 1)
                LOGGER.warning(
                    "Error fetching %s (attempt %s/%s): %s. Retrying in %ss",
                    day_iso,
                    attempt,
                    self.max_retries,
                    exc,
                    wait_time,
                )
                if attempt == self.max_retries:
                    return DayResult(day=day_iso, url=url, count=0, rows=[], error=str(exc))
                await asyncio.sleep(wait_time)

        return DayResult(day=day_iso, url=url, count=0, rows=[], error="Unknown error")
