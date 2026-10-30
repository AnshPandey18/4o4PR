"""Shared OmniRoute client for LLM calls.

Extracted from analysis.root_cause_agent to provide a shared client
for both RCA and bug detector collectors.
"""

import json
import os
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OmnirouteError(Exception):
    """Raised when OmniRoute API call fails."""


def call_omniroute(
    prompt: str,
    max_tokens: Optional[int] = None,
    temperature: float = 0.0,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 120.0,
) -> str:
    """Call OmniRoute API with a prompt.
    
    Args:
        prompt: The prompt text to send
        max_tokens: Maximum tokens in response (optional)
        temperature: Sampling temperature (default 0.0)
        base_url: OmniRoute base URL (defaults to OMNIROUTE_BASE_URL env var)
        api_key: API key (defaults to OMNIROUTE_API_KEY env var)
        model: Model name (defaults to OMNIROUTE_MODEL env var)
        timeout: Request timeout in seconds (default 120.0)
        
    Returns:
        Response content string
        
    Raises:
        OmnirouteError: If the request fails or response is invalid
    """
    # Check LLM kill switch
    if os.getenv('LLM_DISABLED') == '1':
        raise OmnirouteError("LLM is disabled (LLM_DISABLED=1)")
    
    # Get configuration from environment if not provided
    base_url = (base_url or os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
    api_key = api_key or os.getenv("OMNIROUTE_API_KEY")
    model = model or os.getenv("OMNIROUTE_MODEL", "auto/coding")
    
    if not api_key:
        raise OmnirouteError("OMNIROUTE_API_KEY is not configured")
    
    if not isinstance(prompt, str) or not prompt.strip():
        raise OmnirouteError("Prompt must be a non-empty string")
    
    # Build payload
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    
    # Make request
    request = Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    
    try:
        with urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                status = getattr(response, "status", "unknown")
                content_type = response.headers.get("Content-Type", "unknown")
                details = raw_body.strip()[:1000] or "<empty response body>"
                raise OmnirouteError(
                    f"OmniRoute returned non-JSON response: "
                    f"HTTP {status}, Content-Type {content_type}: {details}"
                ) from exc
    except HTTPError as exc:
        try:
            details = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            details = ""
        suffix = f": {details[:1000]}" if details else ""
        raise OmnirouteError(
            f"OmniRoute request failed: HTTP {exc.code} {exc.reason}{suffix}"
        ) from exc
    except (URLError, TimeoutError, UnicodeError) as exc:
        raise OmnirouteError(f"OmniRoute request failed: {exc}") from exc
    
    # Extract content
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OmnirouteError("OmniRoute response has no chat completion content") from exc
    
    # Handle content that might be a list
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    
    if not isinstance(content, str) or not content.strip():
        raise OmnirouteError("OmniRoute returned empty content")
    
    return content
