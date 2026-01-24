from typing import Tuple
from playwright.async_api import async_playwright, Playwright, Page, Browser

from app.utils import get_logger, PlaywrightWrapper

logger = get_logger("meet-bot")


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


async def connect_meeting(meeting_url: str) -> None:
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
        await pageWrapper.safe_click(text="Ask to join")
        await pageWrapper.wait(5000)
    except Exception as e:
        await page.screenshot(path="app/logs/error.png")
        raise
