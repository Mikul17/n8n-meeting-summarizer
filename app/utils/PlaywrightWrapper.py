from playwright.async_api import Page, Locator
from typing import Optional, Literal, Any
import logging

from pydantic import BaseModel, PrivateAttr

logger = logging.getLogger("Playwright")


class PlaywrightWrapper(BaseModel):
    _page: Page = PrivateAttr()
    default_timeout: int = 3000

    def __init__(self, page: Page, default_timeout, **data: Any):
        super().__init__(default_timeout=default_timeout, **data)
        self._page = page

    async def _get_locator(
            self,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            placeholder: Optional[str] = None,
            label: Optional[str] = None,
            exact: bool = False
    ) -> Optional[Locator]:
        try:
            if text:
                return self._page.get_by_text(text=text, exact=exact)
            elif selector:
                return self._page.locator(selector)
            elif role:
                return self._page.get_by_role(role)
            elif placeholder:
                return self._page.get_by_placeholder(placeholder)
            elif label:
                return self._page.get_by_label(label)
            else:
                logger.error("[ERROR]: No locator strategy provided")
                return None
        except Exception as e:
            logger.error(f"[ERROR]: Failed to create locator: {e}")
            return None

    async def wait(self, timeout: Optional[int] = None):
        timeout = timeout or self.default_timeout
        await self._page.wait_for_timeout(timeout=timeout)

    async def safe_click(
            self,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            placeholder: Optional[str] = None,
            label: Optional[str] = None,
            exact: bool = False,
            timeout: Optional[int] = None,
            state: Literal["attached", "detached", "visible", "hidden"] = "visible",
            force: bool = False,
    ) -> bool:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(
            text=text,
            selector=selector,
            role=role,
            placeholder=placeholder,
            label=label,
            exact=exact,
        )

        if not locator:
            return False

        try:
            await locator.wait_for(state=state, timeout=timeout)
            await locator.click(force=force, timeout=timeout)

            identifier = text or selector or role or placeholder or label
            logger.info(f"[AGENT]: Clicked element: {identifier}")
            return True

        except Exception as e:
            identifier = text or selector or role or placeholder or label
            logger.warning(f"[ERROR]: Element [{identifier}] not found or not clickable: {e}")
            return False

    async def safe_fill(
            self,
            value: str,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            placeholder: Optional[str] = None,
            label: Optional[str] = None,
            exact: bool = False,
            timeout: Optional[int] = None,
            clear_first: bool = True
    ) -> bool:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(text=text,selector= selector,role= role,placeholder= placeholder,label=label, exact= exact,)

        if not locator:
            return False

        try:
            await locator.wait_for(timeout=timeout)

            if clear_first:
                await locator.clear()

            await locator.fill(value)

            identifier = text or selector or role or placeholder
            logger.info(f"[AGENT]: Filled element [{identifier}] with value: {value}")
            return True

        except Exception as e:
            identifier = text or selector or role or placeholder
            logger.warning(f"[ERROR]: Element [{identifier}] not found or not fillable: {e}")
            return False

    async def safe_select(
            self,
            value: str,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            timeout: Optional[int] = None
    ) -> bool:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(text, selector)

        if not locator:
            return False

        try:
            await locator.wait_for(timeout=timeout)
            await locator.select_option(value)

            identifier = text or selector
            logger.info(f"[AGENT]: Selected option [{value}] in element: {identifier}")
            return True

        except Exception as e:
            identifier = text or selector
            logger.warning(f"[ERROR]: Failed to select option in [{identifier}]: {e}")
            return False

    async def safe_check(
            self,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            timeout: Optional[int] = None,
            checked: bool = True
    ) -> bool:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(text, selector, role)

        if not locator:
            return False

        try:
            await locator.wait_for(timeout=timeout)

            if checked:
                await locator.check()
            else:
                await locator.uncheck()

            identifier = text or selector or role
            action = "Checked" if checked else "Unchecked"
            logger.info(f"[AGENT]: {action} element: {identifier}")
            return True

        except Exception as e:
            identifier = text or selector or role
            logger.warning(f"[ERROR]: Failed to check/uncheck [{identifier}]: {e}")
            return False

    async def safe_wait_for(
            self,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            state: Literal["attached", "detached", "visible", "hidden"] = "visible",
            timeout: Optional[int] = None
    ) -> bool:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(text, selector, role)

        if not locator:
            return False

        try:
            await locator.wait_for(state=state, timeout=timeout)

            identifier = text or selector or role
            logger.info(f"[AGENT]: Element [{identifier}] reached state: {state}")
            return True

        except Exception as e:
            identifier = text or selector or role
            logger.warning(f"[ERROR]: Element [{identifier}] did not reach state [{state}]: {e}")
            return False

    async def safe_get_text(
            self,
            text: Optional[str] = None,
            selector: Optional[str] = None,
            role: Optional[str] = None,
            timeout: Optional[int] = None
    ) -> Optional[str]:
        timeout = timeout or self.default_timeout
        locator = await self._get_locator(text, selector, role)

        if not locator:
            return None

        try:
            await locator.wait_for(timeout=timeout)
            content = await locator.text_content()

            identifier = text or selector or role
            logger.info(f"[AGENT]: Got text from element [{identifier}]: {content}")
            return content

        except Exception as e:
            identifier = text or selector or role
            logger.warning(f"[ERROR]: Failed to get text from [{identifier}]: {e}")
            return None

    @property
    def page(self):
        return self._page
