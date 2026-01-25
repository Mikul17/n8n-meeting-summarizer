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
        await page.safe_wait_for(selector='[role="menu"]:visible, [role="listbox"]:visible', state='visible',
                                 timeout=5000)

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
        await page.safe_wait_for(selector='[role="menu"]:visible, [role="listbox"]:visible', state='hidden',
                                 timeout=3000)

        return page

    except Exception:
        await page.page.screenshot(path="app/logs/error.png")
        logger.error("Error while selecting recording device")
        raise


async def wait_for_approve(page: PlaywrightWrapper, *, timeout_s: int = 120, poll_ms:int = 1000) -> bool:
    elapsed = 0
    deadline = timeout_s * 1000
    text = "Please wait until a meeting host brings you into the call"

    while elapsed < deadline:
        try:
            still_waiting = False
            try:
                if await page.page.get_by_text(text).first.is_visible():
                    still_waiting = True
                    break
            except Exception:
                pass

            if not still_waiting:
                return True

        except Exception:
            pass

        await page.wait(poll_ms)
        elapsed += poll_ms
    return False


async def wait_for_meeting_end(page: PlaywrightWrapper, *, timeout_s: int, poll_ms: int = 1000) -> bool:
    end_selectors = [
        'text="You left the meeting"',
        'text="You left the call"',
        'text="Rejoin"',
        'text="Call ended"',
        'text="Meeting ended"',
        'text="You have been removed"',
        'text="Return to home screen"',
        'text="Back to home"',
    ]

    in_call_selectors = [
        '[aria-label*="Leave call"]',
        '[aria-label*="Hang up"]',
        '[aria-label*="End call"]',
    ]

    deadline = timeout_s * 1000
    elapsed = 0

    while elapsed < deadline:
        for sel in end_selectors:
            try:
                if await page.page.locator(sel).first.is_visible():
                    return True
            except Exception:
                pass

        any_in_call_visible = False
        for sel in in_call_selectors:
            try:
                if await page.page.locator(sel).first.is_visible():
                    any_in_call_visible = True
                    break
            except Exception:
                pass

        if not any_in_call_visible:
            if elapsed >= 2 * poll_ms:
                return True

        await page.wait(poll_ms)
        elapsed += poll_ms

    return False
