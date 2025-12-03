"""Email classification using LangChain and LLMs."""

import re
from collections.abc import Callable
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Result of email classification."""

    is_marketing: bool = Field(..., description="Whether the email is marketing/promotional")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    reason: str = Field(..., description="Brief explanation of the classification")


# Debug callback type for logging tool calls
ToolCallLogger = Callable[[str, dict[str, Any], str], None]


class EmailClassifier:
    """Classify emails as marketing using LLMs."""

    def __init__(
        self,
        llm: BaseChatModel,
        system_prompt: str,
        marketing_criteria: str,
        exclusions: str,
        user_preferences: str = "",
        debug_callback: ToolCallLogger | None = None,
    ) -> None:
        """Initialize email classifier.

        Args:
            llm: LangChain chat model instance
            system_prompt: System prompt for the classifier
            marketing_criteria: Description of what constitutes marketing emails
            exclusions: What to exclude from marketing classification
            user_preferences: Free-form user preferences for what emails to keep or avoid
            debug_callback: Optional callback for logging tool calls (name, args, result)
        """
        self.llm = llm
        self.system_prompt = system_prompt
        self.marketing_criteria = marketing_criteria
        self.exclusions = exclusions
        self.user_preferences = user_preferences
        self.debug_callback = debug_callback
        # Build static prompt parts (cacheable) - only truly static content
        self._static_prompt = self._build_static_prompt(system_prompt)

    def _build_exclusions_text(self) -> str:
        """Build the complete exclusions text with user preferences."""
        exclusions_text = self.exclusions

        # Add user preferences if provided - make them prominent
        if self.user_preferences.strip():
            exclusions_text += "\n\n" + "=" * 60
            exclusions_text += "\nIMPORTANT USER PREFERENCES (MUST BE FOLLOWED):"
            exclusions_text += "\n" + "=" * 60
            exclusions_text += "\n" + self.user_preferences
            exclusions_text += "\n" + "=" * 60
            exclusions_text += (
                "\n\nThese preferences override the general marketing criteria above."
            )
            exclusions_text += (
                "\nIf an email matches a user preference to KEEP, it is NOT marketing."
            )

        return exclusions_text

    def _build_static_prompt(self, system_prompt: str) -> str:
        """Build the static (cacheable) part of the prompt.

        IMPORTANT: This contains ONLY static content that is identical across all
        classification requests. Variable content (marketing criteria, exclusions,
        user preferences) is added later in the human message.

        Order matters for prompt caching:
        1. System prompt (static)
        2. Task description (static)
        3. Tool descriptions (static)
        4. Response format (static)
        5. Rules (static)
        """
        return f"""{system_prompt}

## Your Task

You are an email classifier. Analyze emails to determine if they are marketing/promotional emails that the user might want to unsubscribe from.

## Pre-Analysis Provided

Each email includes a "Pre-Analysis" section with automated scanning results:
- **Unsubscribe content**: Lines containing unsubscribe/opt-out text (NO NEED to search for this)
- **Promotional language**: Detected discount/sale/offer keywords
- **Transactional language**: Detected order/shipping/receipt keywords
- **Body stats**: Size, line count, link count

This pre-analysis eliminates the need for most tool calls.

## Available Tools (use sparingly)

Only use tools if the pre-analysis and email preview are insufficient:

1. **get_headers** - Get specific email headers by name
   - Input: list of header names (e.g., ["X-Mailer", "X-Campaign-ID", "Precedence"])
   - Use for: Checking bulk mail indicators, mailer software, campaign IDs

2. **search_body** - Search the email body for specific terms
   - Input: list of search terms/patterns (case-insensitive)
   - Returns: Matching lines with context
   - NOTE: Unsubscribe/promo/transactional terms are already in Pre-Analysis

3. **read_body_chunk** - Read a specific portion of the email body
   - Input: start line, number of lines (default: 50 lines)
   - Use for: Reading specific sections when you know where to look

4. **get_body_stats** - Get statistics about the email body
   - NOTE: Basic stats are already in Pre-Analysis

## Response Format

Respond with:
- is_marketing: true or false
- confidence: 0.0 to 1.0
- reason: Brief explanation (reference user preferences if applicable)

## Important Rules

1. **User preferences ALWAYS override general criteria** - If user says "keep Oakland Zoo emails" and this is from Oakland Zoo, it is NOT marketing.
2. **Check sender against user preferences first** - Before analyzing content.
3. **Use Pre-Analysis first** - It contains the most commonly needed information.
4. **Avoid unnecessary tool calls** - The pre-analysis already searched for unsubscribe content.
"""

    def _pre_analyze_body(self, full_body: str) -> dict[str, Any]:
        """Pre-analyze the email body to provide useful signals upfront.

        This reduces tool calls by giving the model common information it would
        otherwise need to search for.
        """
        body_lines = full_body.split("\n")
        body_lower = full_body.lower()

        # Count links
        link_count = len(re.findall(r"https?://", full_body, re.IGNORECASE))

        # Find unsubscribe-related content (most common search)
        unsubscribe_lines: list[str] = []
        unsubscribe_keywords = [
            "unsubscribe",
            "opt out",
            "opt-out",
            "manage preferences",
            "email preferences",
            "stop receiving",
            "remove from list",
        ]
        for i, line in enumerate(body_lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in unsubscribe_keywords):
                # Include line number and truncated content
                truncated = line[:100] + "..." if len(line) > 100 else line
                unsubscribe_lines.append(f"L{i + 1}: {truncated}")

        # Detect promotional language
        promo_keywords = [
            "% off",
            "discount",
            "sale",
            "deal",
            "offer",
            "coupon",
            "promo",
            "limited time",
            "act now",
            "don't miss",
            "exclusive",
            "free shipping",
            "buy now",
            "shop now",
            "order now",
        ]
        promo_signals: list[str] = []
        for kw in promo_keywords:
            if kw in body_lower:
                promo_signals.append(kw)

        # Detect transactional signals
        transactional_keywords = [
            "order confirmation",
            "shipping confirmation",
            "tracking number",
            "receipt",
            "invoice",
            "payment received",
            "your order",
            "has shipped",
            "delivery",
            "account activity",
            "password reset",
            "verification code",
            "security alert",
        ]
        transactional_signals: list[str] = []
        for kw in transactional_keywords:
            if kw in body_lower:
                transactional_signals.append(kw)

        return {
            "line_count": len(body_lines),
            "char_count": len(full_body),
            "link_count": link_count,
            "unsubscribe_lines": unsubscribe_lines[:5],  # Limit to 5
            "promo_signals": promo_signals[:10],
            "transactional_signals": transactional_signals[:5],
            "has_unsubscribe": len(unsubscribe_lines) > 0,
            "has_promo_language": len(promo_signals) > 0,
            "has_transactional_language": len(transactional_signals) > 0,
        }

    def _build_email_message(
        self,
        subject: str,
        from_address: str,
        body_preview: str,
        to_address: str,
        reply_to: str,
        sender: str,
        list_unsubscribe: str,
        list_unsubscribe_post: str,
        list_headers: str,
        body_analysis: dict[str, Any],
    ) -> str:
        """Build the dynamic email-specific part of the prompt.

        This includes:
        1. Classification criteria (variable per user config)
        2. Exclusions and user preferences (variable per user)
        3. The actual email to classify (variable per email)

        Note: Static content (task, tools, rules) is in the system message.
        """
        # Build exclusions text with user preferences
        exclusions_text = self._build_exclusions_text()

        # Build pre-analysis section
        analysis_lines = []
        analysis_lines.append(
            f"- **Size:** {body_analysis['char_count']} chars, "
            f"{body_analysis['line_count']} lines, {body_analysis['link_count']} links"
        )

        if body_analysis["has_unsubscribe"]:
            analysis_lines.append("- **Unsubscribe content found:**")
            for line in body_analysis["unsubscribe_lines"]:
                analysis_lines.append(f"  - {line}")
        else:
            analysis_lines.append("- **No unsubscribe links/text detected**")

        if body_analysis["has_promo_language"]:
            signals = ", ".join(body_analysis["promo_signals"])
            analysis_lines.append(f"- **Promotional language detected:** {signals}")

        if body_analysis["has_transactional_language"]:
            signals = ", ".join(body_analysis["transactional_signals"])
            analysis_lines.append(f"- **Transactional language detected:** {signals}")

        analysis_section = "\n".join(analysis_lines)

        return f"""## Classification Criteria

### What IS Marketing:
{self.marketing_criteria}

### What is NOT Marketing (Exclusions):
{exclusions_text}

---

## Email to Classify

**Subject:** {subject}
**From:** {from_address}
**To:** {to_address or "(not provided)"}
**Reply-To:** {reply_to or "(not provided)"}
**Sender:** {sender or "(not provided)"}

### Unsubscribe Headers
- List-Unsubscribe: {list_unsubscribe or "(none)"}
- List-Unsubscribe-Post: {list_unsubscribe_post or "(none)"}
- Other List-* Headers: {list_headers or "(none)"}

### Pre-Analysis (automated scan)
{analysis_section}

### Email Body Preview (first 1500 chars)
```
{body_preview}
```

Based on the above information, classify this email. Use tools only if you need additional information not provided above.
"""

    def _create_tools(
        self, all_headers: list[dict[str, str]], full_body: str
    ) -> list[StructuredTool]:
        """Create efficient tools for the model to access email information."""
        # Pre-compute body lines for efficient access
        body_lines = full_body.split("\n")

        def get_headers(header_names: list[str]) -> str:
            """Get multiple email headers by name (case-insensitive).

            Args:
                header_names: List of header names to retrieve
            """
            if not header_names:
                return "No header names provided."

            results = []
            headers_lower = {h.get("name", "").lower(): h for h in all_headers}

            for name in header_names:
                name_lower = name.lower()
                if name_lower in headers_lower:
                    h = headers_lower[name_lower]
                    results.append(f"{h.get('name', '')}: {h.get('value', '')}")
                else:
                    # Check for partial matches (e.g., "X-Campaign" matches "X-Campaign-ID")
                    partial_matches = [
                        f"{h.get('name', '')}: {h.get('value', '')}"
                        for h in all_headers
                        if name_lower in h.get("name", "").lower()
                    ]
                    if partial_matches:
                        results.extend(partial_matches)
                    else:
                        results.append(f"{name}: (not found)")

            return "\n".join(results) if results else "No matching headers found."

        def search_body(terms: list[str], context_lines: int = 1) -> str:
            """Search the email body for specific terms (case-insensitive).

            Args:
                terms: List of search terms or regex patterns
                context_lines: Number of lines of context around matches (default: 1)
            """
            if not terms:
                return "No search terms provided."

            matches: list[str] = []
            seen_lines: set[int] = set()

            for term in terms:
                try:
                    pattern = re.compile(term, re.IGNORECASE)
                except re.error:
                    # If not valid regex, escape it
                    pattern = re.compile(re.escape(term), re.IGNORECASE)

                for i, line in enumerate(body_lines):
                    if pattern.search(line) and i not in seen_lines:
                        # Get context
                        start = max(0, i - context_lines)
                        end = min(len(body_lines), i + context_lines + 1)

                        context_block: list[str] = []
                        for j in range(start, end):
                            prefix = ">>> " if j == i else "    "
                            line_text = f"{prefix}L{j + 1}: {body_lines[j]}"
                            context_block.append(line_text)
                            seen_lines.add(j)

                        matches.append(f"Match for '{term}':\n" + "\n".join(context_block))

            if not matches:
                return f"No matches found for: {', '.join(terms)}"

            # Limit output to avoid token explosion
            result = "\n\n".join(matches[:10])
            if len(matches) > 10:
                result += f"\n\n... and {len(matches) - 10} more matches"
            return result

        def read_body_chunk(start_line: int = 1, num_lines: int = 50) -> str:
            """Read a chunk of the email body by line numbers.

            Args:
                start_line: Starting line number (1-indexed, default: 1)
                num_lines: Number of lines to read (default: 50, max: 100)
            """
            # Convert to 0-indexed
            start_idx = max(0, start_line - 1)
            num_lines = min(num_lines, 100)  # Cap at 100 lines
            end_idx = min(start_idx + num_lines, len(body_lines))

            if start_idx >= len(body_lines):
                return f"Start line {start_line} is beyond the email body ({len(body_lines)} lines total)."

            chunk_lines: list[str] = []
            for i in range(start_idx, end_idx):
                line_text = f"L{i + 1}: {body_lines[i]}"
                chunk_lines.append(line_text)

            result = "\n".join(chunk_lines)
            if end_idx < len(body_lines):
                result += f"\n\n[{len(body_lines) - end_idx} more lines available]"

            return result

        def get_body_stats() -> str:
            """Get statistics about the email body structure."""
            stats = {
                "total_lines": len(body_lines),
                "total_chars": len(full_body),
                "non_empty_lines": sum(1 for line in body_lines if line.strip()),
            }

            # Detect common sections
            sections: list[str] = []
            for i, line in enumerate(body_lines):
                line_lower = line.lower().strip()
                if any(
                    kw in line_lower
                    for kw in [
                        "unsubscribe",
                        "opt out",
                        "manage preferences",
                        "email preferences",
                        "privacy policy",
                        "terms of service",
                    ]
                ):
                    sections.append(f"L{i + 1}: {line[:80]}...")

            # Count links
            link_count = len(re.findall(r"https?://", full_body, re.IGNORECASE))

            result = f"""Email Body Statistics:
- Total lines: {stats["total_lines"]}
- Non-empty lines: {stats["non_empty_lines"]}
- Total characters: {stats["total_chars"]}
- Links found: {link_count}
"""
            if sections:
                result += "\nRelevant sections detected:\n"
                for s in sections[:5]:
                    result += f"  {s}\n"
                if len(sections) > 5:
                    result += f"  ... and {len(sections) - 5} more\n"

            return result

        return [
            StructuredTool.from_function(
                func=get_headers,
                name="get_headers",
                description="Get specific email headers by name. Input: list of header names. Supports partial matching (e.g., 'X-Campaign' matches 'X-Campaign-ID').",
            ),
            StructuredTool.from_function(
                func=search_body,
                name="search_body",
                description="Search the email body for terms/patterns. Returns matching lines with context. Use this instead of reading the full body.",
            ),
            StructuredTool.from_function(
                func=read_body_chunk,
                name="read_body_chunk",
                description="Read a specific chunk of the email body by line number. Use after search_body to read around specific areas.",
            ),
            StructuredTool.from_function(
                func=get_body_stats,
                name="get_body_stats",
                description="Get email body statistics: line count, link count, detected sections (unsubscribe links, etc.).",
            ),
        ]

    def _execute_tool_calls(
        self,
        tool_calls: list[Any],
        tools_dict: dict[str, StructuredTool],
    ) -> list[Any]:
        """Execute tool calls and return ToolMessage results."""
        from langchain_core.messages import ToolMessage

        tool_messages = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {})
            tool_call_id = getattr(tool_call, "id", tool_name)

            if tool_name in tools_dict:
                tool = tools_dict[tool_name]
                try:
                    result = tool.invoke(tool_args)
                    result_str = str(result)

                    # Log if debug callback is set
                    if self.debug_callback:
                        self.debug_callback(tool_name, tool_args, result_str)

                    tool_messages.append(ToolMessage(content=result_str, tool_call_id=tool_call_id))
                except Exception as e:
                    error_msg = f"Error: {e}"
                    if self.debug_callback:
                        self.debug_callback(tool_name, tool_args, error_msg)
                    tool_messages.append(ToolMessage(content=error_msg, tool_call_id=tool_call_id))

        return tool_messages

    async def classify(
        self,
        subject: str,
        from_address: str,
        body: str,
        to_address: str = "",
        reply_to: str = "",
        sender: str = "",
        list_unsubscribe: str = "",
        list_unsubscribe_post: str = "",
        list_headers: str = "",
        all_headers: list[dict[str, str]] | None = None,
        full_body: str | None = None,
        raw_email: str | None = None,  # kept for API compatibility
    ) -> ClassificationResult:
        """Classify an email as marketing or not.

        Args:
            subject: Email subject line
            from_address: Email sender address
            body: Email body text (first 2000 chars recommended)
            to_address: To header value
            reply_to: Reply-To header value
            sender: Sender header value
            list_unsubscribe: List-Unsubscribe header value
            list_unsubscribe_post: List-Unsubscribe-Post header value
            list_headers: Other List-* headers (formatted as key: value pairs)
            all_headers: All email headers as list of dicts (for tool access)
            full_body: Full email body (for tool access)
            raw_email: Raw email content (unused, kept for compatibility)

        Returns:
            ClassificationResult with is_marketing, confidence, and reason
        """
        full_body = full_body or body
        all_headers = all_headers or []

        # Pre-analyze body to provide common signals upfront (reduces tool calls)
        body_analysis = self._pre_analyze_body(full_body)

        # Truncate body preview (first 1500 chars to leave room for tool output)
        body_preview = body[:1500] if len(body) > 1500 else body

        # Build email message with pre-analysis
        email_message = self._build_email_message(
            subject=subject,
            from_address=from_address,
            body_preview=body_preview,
            to_address=to_address,
            reply_to=reply_to,
            sender=sender,
            list_unsubscribe=list_unsubscribe,
            list_unsubscribe_post=list_unsubscribe_post,
            list_headers=list_headers,
            body_analysis=body_analysis,
        )

        # Build messages directly using Message objects
        # Avoid ChatPromptTemplate which interprets {} as template variables
        # Email content may contain curly braces (JSON, URLs, code) that cause format errors
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=self._static_prompt),
            HumanMessage(content=email_message),
        ]

        # Create tools
        tools = self._create_tools(all_headers, full_body)
        tools_dict = {tool.name: tool for tool in tools}

        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)

        # Handle tool calling loop (max 3 iterations)
        max_iterations = 3
        # Type: list of BaseMessage (can include AIMessage, HumanMessage, SystemMessage, ToolMessage)
        from langchain_core.messages import BaseMessage

        current_messages: list[BaseMessage] = list(messages)

        for _ in range(max_iterations):
            response = await llm_with_tools.ainvoke(current_messages)

            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_messages = self._execute_tool_calls(response.tool_calls, tools_dict)
                current_messages = [*current_messages, response, *tool_messages]
            else:
                # No tool calls, get structured output
                structured_llm = self.llm.with_structured_output(ClassificationResult)
                final_messages = [*current_messages, response]
                result = await structured_llm.ainvoke(final_messages)
                break
        else:
            structured_llm = self.llm.with_structured_output(ClassificationResult)
            result = await structured_llm.ainvoke(current_messages)

        assert isinstance(result, ClassificationResult)
        return result

    def classify_sync(
        self,
        subject: str,
        from_address: str,
        body: str,
        to_address: str = "",
        reply_to: str = "",
        sender: str = "",
        list_unsubscribe: str = "",
        list_unsubscribe_post: str = "",
        list_headers: str = "",
        all_headers: list[dict[str, str]] | None = None,
        full_body: str | None = None,
        raw_email: str | None = None,  # kept for API compatibility
    ) -> ClassificationResult:
        """Synchronous version of classify (for non-async contexts)."""
        full_body = full_body or body
        all_headers = all_headers or []

        # Pre-analyze body to provide common signals upfront (reduces tool calls)
        body_analysis = self._pre_analyze_body(full_body)

        # Truncate body preview
        body_preview = body[:1500] if len(body) > 1500 else body

        # Build email message with pre-analysis
        email_message = self._build_email_message(
            subject=subject,
            from_address=from_address,
            body_preview=body_preview,
            to_address=to_address,
            reply_to=reply_to,
            sender=sender,
            list_unsubscribe=list_unsubscribe,
            list_unsubscribe_post=list_unsubscribe_post,
            list_headers=list_headers,
            body_analysis=body_analysis,
        )

        # Build messages directly using Message objects
        # Avoid ChatPromptTemplate which interprets {} as template variables
        # Email content may contain curly braces (JSON, URLs, code) that cause format errors
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=self._static_prompt),
            HumanMessage(content=email_message),
        ]

        # Create tools
        tools = self._create_tools(all_headers, full_body)
        tools_dict = {tool.name: tool for tool in tools}

        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(tools)

        # Handle tool calling loop (max 3 iterations)
        max_iterations = 3
        # Type: list of BaseMessage (can include AIMessage, HumanMessage, SystemMessage, ToolMessage)
        from langchain_core.messages import BaseMessage

        current_messages: list[BaseMessage] = list(messages)

        for _ in range(max_iterations):
            response = llm_with_tools.invoke(current_messages)

            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_messages = self._execute_tool_calls(response.tool_calls, tools_dict)
                current_messages = [*current_messages, response, *tool_messages]
            else:
                # No tool calls, get structured output
                structured_llm = self.llm.with_structured_output(ClassificationResult)
                final_messages = [*current_messages, response]
                result = structured_llm.invoke(final_messages)
                break
        else:
            structured_llm = self.llm.with_structured_output(ClassificationResult)
            result = structured_llm.invoke(current_messages)

        assert isinstance(result, ClassificationResult)
        return result


def create_classifier(
    provider: Literal["google", "anthropic", "openai"],
    model: str,
    api_key: str,
    system_prompt: str,
    marketing_criteria: str,
    exclusions: str,
    temperature: float | None = None,
    thinking_level: str | None = None,
    max_tokens: int | None = None,
    user_preferences: str = "",
    debug_callback: ToolCallLogger | None = None,
) -> EmailClassifier:
    """Create an EmailClassifier with the specified LLM provider.

    Args:
        provider: LLM provider ("google", "anthropic", or "openai")
        model: Model name
        api_key: API key for the provider
        system_prompt: System prompt for classification
        marketing_criteria: What constitutes marketing emails
        exclusions: What to exclude from marketing classification
        temperature: Optional temperature setting (None = use model default)
        thinking_level: Optional thinking/reasoning level ("low", "high")
                       For Gemini 3+: maps to thinking_budget (512 for low, 8192 for high)
                       For OpenAI o-series: maps to reasoning_effort
        max_tokens: Optional max tokens for response
        user_preferences: Free-form user preferences for what to keep or avoid
        debug_callback: Optional callback for logging tool calls

    Returns:
        Configured EmailClassifier instance
    """
    llm: BaseChatModel

    if provider == "google":
        # Build kwargs for Gemini
        gemini_kwargs: dict[str, Any] = {
            "model": model,
            "google_api_key": api_key,
        }

        # Only add temperature if explicitly set
        if temperature is not None:
            gemini_kwargs["temperature"] = temperature

        # Only add max_tokens if explicitly set
        if max_tokens is not None:
            gemini_kwargs["max_output_tokens"] = max_tokens

        # Handle thinking_level for Gemini 3+ models
        # Maps to thinking_budget: "low" -> 512 (minimum), "high" -> 8192
        if thinking_level is not None:
            thinking_budget = 512 if thinking_level == "low" else 8192
            gemini_kwargs["thinking_budget"] = thinking_budget

        llm = ChatGoogleGenerativeAI(**gemini_kwargs)

    elif provider == "anthropic":
        anthropic_kwargs: dict[str, Any] = {
            "model": model,
            "anthropic_api_key": api_key,
        }

        if temperature is not None:
            anthropic_kwargs["temperature"] = temperature

        if max_tokens is not None:
            anthropic_kwargs["max_tokens"] = max_tokens

        llm = ChatAnthropic(**anthropic_kwargs)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        openai_kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
        }

        if temperature is not None:
            openai_kwargs["temperature"] = temperature

        if max_tokens is not None:
            openai_kwargs["max_tokens"] = max_tokens

        # Handle thinking_level for OpenAI o-series models
        if thinking_level is not None:
            openai_kwargs["model_kwargs"] = {"reasoning_effort": thinking_level}

        llm = ChatOpenAI(**openai_kwargs)

    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return EmailClassifier(
        llm=llm,
        system_prompt=system_prompt,
        marketing_criteria=marketing_criteria,
        exclusions=exclusions,
        user_preferences=user_preferences,
        debug_callback=debug_callback,
    )
