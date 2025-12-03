"""Browser automation for unsubscribe using browser-use and AI.

Supports multiple LLM providers for browser automation:
- Browser-Use's optimized model (fastest, recommended)
- Google Gemini 2.5 Computer Use (specialized for UI automation)
- Anthropic Claude 4.5 (excellent vision capabilities)
- OpenAI GPT-5 (good general purpose)

See:
- https://browser-use.com/posts/speed-matters
- https://ai.google.dev/gemini-api/docs/computer-use
"""

import os
from typing import Any

from browser_use import Agent

from gmail_ai_unsub.config import Config


def create_browser_llm(config: Config) -> Any:
    """Create LLM for browser automation.

    Uses browser-use's native LLM wrappers which are optimized for the Agent.
    Supports a separate browser model configuration for specialized use.

    Args:
        config: Application configuration

    Returns:
        browser-use compatible LLM instance
    """
    # Check for browser-specific model config first
    provider = config.browser_provider or config.llm_provider
    model = config.browser_model or config.llm_model
    api_key = config.browser_api_key or config.llm_api_key

    # Browser-Use's own optimized model (fastest option)
    # See: https://browser-use.com/posts/speed-matters
    if provider == "browser-use":
        from browser_use import ChatBrowserUse

        os.environ["BROWSER_USE_API_KEY"] = api_key
        return ChatBrowserUse()

    # Google Gemini - use Computer Use model for best results
    # See: https://ai.google.dev/gemini-api/docs/computer-use
    if provider == "google":
        from browser_use import ChatGoogle

        os.environ["GOOGLE_API_KEY"] = api_key

        # Map to appropriate browser automation model
        # Gemini 2.5 Computer Use is specifically designed for this
        if "computer-use" in model.lower():
            browser_model = model  # Use as-is
        elif "2.5" in model:
            # Gemini 2.5 models work well for vision tasks
            browser_model = model
        elif "flash" in model.lower():
            # Default to 2.5 flash for speed
            browser_model = "gemini-2.5-flash-preview-05-20"
        elif "pro" in model.lower():
            # Use 2.5 pro for better accuracy
            browser_model = "gemini-2.5-pro-preview-05-06"
        else:
            # For browser automation, prefer the computer use model
            browser_model = "gemini-2.5-computer-use-preview-10-2025"

        return ChatGoogle(model=browser_model)

    # Anthropic Claude 4.5 - excellent vision capabilities
    if provider == "anthropic":
        from browser_use import ChatAnthropic

        os.environ["ANTHROPIC_API_KEY"] = api_key

        # Map to Claude 4.5 models (latest with best vision)
        if "4.5" in model or "4-5" in model:
            browser_model = model  # Use as-is
        elif "sonnet" in model.lower():
            browser_model = "claude-4-5-sonnet"
        elif "haiku" in model.lower():
            browser_model = "claude-4-5-haiku"
        elif "opus" in model.lower():
            browser_model = "claude-4-5-opus"
        else:
            # Default to sonnet for good balance of speed/quality
            browser_model = "claude-4-5-sonnet"

        return ChatAnthropic(model=browser_model)

    # OpenAI GPT-5
    if provider == "openai":
        from browser_use import ChatOpenAI

        os.environ["OPENAI_API_KEY"] = api_key

        # GPT-5 models with vision
        if "5" in model:
            browser_model = model
        elif "4o" in model.lower():
            browser_model = model  # GPT-4o still good for vision
        else:
            browser_model = "gpt-5"

        return ChatOpenAI(model=browser_model)

    # Fallback - try to use the model as-is with OpenAI wrapper
    from browser_use import ChatOpenAI

    os.environ["OPENAI_API_KEY"] = api_key
    return ChatOpenAI(model=model)


async def unsubscribe_via_browser(
    url: str,
    config: Config,
    headless: bool = True,
    timeout: int = 60,
    incognito: bool = True,
) -> tuple[bool, str | None]:
    """Unsubscribe from a URL using browser automation.

    Args:
        url: Unsubscribe URL
        config: Application configuration
        headless: Whether to run browser in headless mode
        timeout: Timeout in seconds
        incognito: Whether to use incognito/private mode (no saved data)

    Returns:
        Tuple of (success: bool, error_message: str | None)
    """
    from browser_use import Browser, BrowserProfile

    browser = None
    try:
        llm = create_browser_llm(config)

        # Configure browser with profile
        # Not setting user_data_dir means fresh/incognito-like session
        browser_profile = BrowserProfile(
            headless=headless,
            minimum_wait_page_load_time=0.5,
            wait_between_actions=0.3,
            # Don't persist any data - fresh session each time
            # This is effectively incognito mode
        )

        # Set fixed window size (not full screen)
        # 1280x720 is a good standard size that works well for screenshots
        # and doesn't take over the entire screen
        browser = Browser(
            browser_profile=browser_profile,
            window_size={"width": 1280, "height": 720},
        )

        # Create browser agent with task
        agent: Agent = Agent(
            task=f"""Navigate to {url} and unsubscribe from this mailing list.

CRITICAL RULES:
1. **Success Detection**: If the page shows "OK", "Success", "Unsubscribed", "You have been unsubscribed", or any similar success message, the task is COMPLETE. Do not take any further actions.

2. **Options and Checkboxes**:
   - If there are multiple options (checkboxes, radio buttons, dropdowns), ALWAYS select the MOST BROAD option
   - Look for: "Unsubscribe from all", "All emails", "Everything", "All newsletters"
   - AVOID selecting specific categories - choose the option that unsubscribes from everything
   - Be VERY CAREFUL with affirmative language - some sites trick you into resubscribing
   - If unsure, choose the option that says "all" or "everything"

3. **DO NOT**:
   - Try to login to any website (if login is required, the unsubscribe link didn't work)
   - Search for "how to unsubscribe" or navigate away from the page
   - Click on links that take you away from the unsubscribe page
   - Fill out forms asking for your email or password

4. **Redirects After Success**:
   - If you see a success message and then the page redirects to a home page or other page, that's fine
   - The task is complete once you see the success message - don't follow redirects

5. **If Unsubscribe is Not Obvious**:
   - If you can't immediately see how to unsubscribe on the page, assume either:
     a) The unsubscribe link didn't work properly, OR
     b) You're already unsubscribed
   - Do NOT try to search or navigate to find unsubscribe options
   - Mark the task as complete if you see any indication you're already unsubscribed

6. **Dark Patterns to Watch For**:
   - Some sites have "Stay subscribed" buttons that look like unsubscribe buttons
   - Read button text carefully - look for words like "unsubscribe", "remove", "opt out"
   - Avoid buttons that say "Keep me subscribed", "Stay subscribed", "Continue receiving"

INSTRUCTIONS:
1. Navigate to the URL
2. Look for unsubscribe buttons, checkboxes, or forms
3. If there are options, select the most broad one (unsubscribe from all)
4. Click "Unsubscribe", "Confirm", or similar buttons
5. If you see a success message (including just "OK"), the task is complete
6. If the page redirects after showing success, that's fine - task is complete

The goal is to unsubscribe from ALL emails from this sender, not just specific categories.""",
            llm=llm,
            browser=browser,
            use_vision=True,  # Enable screenshot-based vision for better UI understanding
            max_steps=15,  # Limit steps to avoid infinite loops
            step_timeout=timeout,
            max_failures=3,
        )

        # Run the agent
        result = await agent.run()

        # Check if task was completed successfully
        # browser-use returns an AgentHistoryList with all_results
        # We need to check if the final result has is_done=True and success=True
        success = False
        final_message = None

        if result is not None:
            # Check for all_results attribute (AgentHistoryList)
            all_results = getattr(result, "all_results", None)
            if all_results:
                # Find the final "done" action
                for action_result in reversed(all_results):
                    if getattr(action_result, "is_done", False):
                        # Check multiple success indicators
                        action_success = getattr(action_result, "success", None)
                        if action_success is True:
                            success = True
                        elif action_success is None:
                            # If success is None, check judgement.verdict
                            judgement = getattr(action_result, "judgement", None)
                            if judgement:
                                verdict = getattr(judgement, "verdict", None)
                                if verdict is True:
                                    success = True

                        # Get final message content
                        final_message = getattr(action_result, "extracted_content", None)
                        if not final_message:
                            # Try to get text from the action result
                            final_message = getattr(action_result, "text", None)

                        # Check message content for success indicators
                        if final_message:
                            msg_lower = str(final_message).lower()
                            success_phrases = [
                                "already unsubscribed",
                                "successfully unsubscribed",
                                "unsubscribed",
                                "task completed successfully",
                                "no further action is needed",
                                "you have been unsubscribed",
                            ]
                            if any(phrase in msg_lower for phrase in success_phrases):
                                success = True

                        break

            # Also check for direct success attribute on result
            if not success:
                result_success = getattr(result, "success", None)
                if result_success is True:
                    success = True
                    # Try to get message from result
                    if not final_message:
                        final_message = getattr(result, "text", None) or str(result)

            # Fallback: Check if result string contains success indicators
            if not success:
                result_str = str(result)
                result_lower = result_str.lower()
                success_phrases = [
                    "task completed successfully",
                    "successfully unsubscribed",
                    "already unsubscribed",
                    "unsubscribed",
                    "no further action is needed",
                ]
                if any(phrase in result_lower for phrase in success_phrases):
                    success = True
                    if not final_message:
                        final_message = result_str

        if success:
            return (True, final_message)
        else:
            # Try to extract error message
            error_msg = "Browser automation did not complete successfully"
            if result and hasattr(result, "all_results"):
                for action_result in reversed(result.all_results):
                    if getattr(action_result, "error", None):
                        error_msg = f"Browser error: {action_result.error}"
                        break
                    # Also check if there's a message that might indicate what happened
                    msg = getattr(action_result, "extracted_content", None) or getattr(
                        action_result, "text", None
                    )
                    if msg and not success:
                        error_msg = f"Browser automation did not complete successfully: {msg}"
            return (False, error_msg)

    except Exception as e:
        return (False, f"Browser automation failed: {str(e)}")

    finally:
        if browser:
            try:
                # Browser object may be a context manager or have different cleanup
                if hasattr(browser, "close"):
                    await browser.close()
                elif hasattr(browser, "__aexit__"):
                    await browser.__aexit__(None, None, None)
            except Exception:
                pass


def unsubscribe_via_browser_sync(
    url: str,
    config: Config,
    headless: bool = True,
    timeout: int = 60,
    incognito: bool = True,
) -> tuple[bool, str | None]:
    """Synchronous wrapper for browser unsubscribe.

    Args:
        url: Unsubscribe URL
        config: Application configuration
        headless: Whether to run browser in headless mode
        timeout: Timeout in seconds
        incognito: Whether to use incognito/private mode

    Returns:
        Tuple of (success: bool, error_message: str | None)
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(
        unsubscribe_via_browser(url, config, headless, timeout, incognito)
    )
