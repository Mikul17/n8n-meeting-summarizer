from typing import Tuple
from playwright.async_api import async_playwright, Playwright, Page, Browser
import re

from app.utils import get_logger, PlaywrightWrapper

logger = get_logger("meeting-service")


async def create_browser() -> Tuple[Playwright, Browser]:
    playwright = await async_playwright().start()
    context = await playwright.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream",
            "--expose-all-device-ids",
            "--shm-size=1g",
            "--no-sandbox",
            "--autoplay-policy=no-user-gesture-required",
            f"--audio-output-channels=2"
        ],
    )
    return playwright, context


async def connect_meeting(meeting_url: str) -> Tuple[PlaywrightWrapper, Browser]:
    playwright, browser = await create_browser()
    logger.info("Starting browser")

    page: Page = await browser.new_page()
    pageWrapper = PlaywrightWrapper(page=page, default_timeout=5000)
    await page.goto(f"{meeting_url}?hl=en")
    logger.info(f"Entering {meeting_url}")
    await pageWrapper.wait(500)
    try:
        await pageWrapper.safe_click(text="Continue without microphone and camera")
        await pageWrapper.safe_click(text="Got it")
        await pageWrapper.safe_fill(value="N8N TranscribeBot", label="Your name")
        return pageWrapper, browser
    except Exception:
        await page.screenshot(path="app/logs/error.png")
        raise


async def ask_to_join(page: PlaywrightWrapper, connection_timeout: int = 5000):
    try:
        await page.safe_click(text="Ask to join")
        await page.wait(connection_timeout)
    except Exception:
        await page.screenshot(path="app/logs/error.png")
        logger.error("Error while attempting to join meeting")
        raise


async def select_recording_device(page: PlaywrightWrapper, device_name: str):
    try:
        safe_name = (device_name or "").strip().replace('"', '\\"')
        if not safe_name:
            raise ValueError("device_name is empty")

        await page.safe_click(selector='[aria-label*="Speaker:"]', force=True)
        await page.safe_wait_for(selector='[role="menu"]:visible, [role="listbox"]:visible', state='visible', timeout=5000)

        pattern = re.escape(safe_name)
        li_selector_prefix = (
            f'[role="menu"]:visible, [role="listbox"]:visible '
            f'>> span:text-matches("^{pattern}", "i") '
            f'>> xpath=ancestor::li[1]'
        )
        li_selector_contains = (
            f'[role="menu"]:visible, [role="listbox"]:visible '
            f'>> span:has-text("{safe_name}") '
            f'>> xpath=ancestor::li[1]'
        )

        clicked = await page.safe_click(selector=li_selector_prefix, state='attached', force=True, timeout=5000)
        if not clicked:
            clicked = await page.safe_click(selector=li_selector_contains, state='attached', force=True, timeout=5000)

        if not clicked:
            raise RuntimeError(f"Device option not found: {device_name}")

        # Prefer waiting for the popup to close.
        await page.safe_wait_for(selector='[role="menu"]:visible, [role="listbox"]:visible', state='hidden', timeout=3000)

        return page

    except Exception:
        await page.page.screenshot(path="app/logs/error.png")
        logger.error("Error while selecting recording device")
        raise
