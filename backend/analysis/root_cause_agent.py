"""Prompt-only root-cause analysis agent.

The agent deliberately has no repository or file-system access. A Context
Builder must provide all evidence in one prompt, and the agent returns one
validated JSON analysis for that prompt.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Protocol, Union
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class RootCauseAnalysisError(ValueError):
    """Raised when the prompt, model response, or client configuration is invalid."""


class LLMClient(Protocol):
    """Minimal client contract used by the agent."""

    def complete(self, prompt: str) -> str:
        """Return the model's response text for one prompt."""


@dataclass
class Evidence:
    """A grounded observation from the supplied prompt."""

    file: str
    line: int
    observation: str


@dataclass
class FaultyLocation:
    """Location identified by the model from the supplied context."""

    file: str
    qualified_name: str
    line_start: int
    line_end: int


@dataclass
class AnalysisResult:
    """Validated RCA output for one bug group."""

    bug_ids: List[str]
    verdict: str
    faulty_location: Optional[FaultyLocation]
    root_cause: str
    evidence: List[Evidence]
    fix_strategy: str
    affected_symbols: List[str]
    blast_radius: str
    confidence: float
    needs_more_context: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation."""

        return asdict(self)


class OpenAICompatibleClient:
    """Small stdlib client for OmniRoute and other OpenAI-compatible gateways."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("OMNIROUTE_API_KEY")
        self.model = model or os.getenv("OMNIROUTE_MODEL", "auto/coding")
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        """Send one prompt to the configured OpenAI-compatible chat endpoint."""

        if not self.api_key:
            raise RootCauseAnalysisError("OMNIROUTE_API_KEY is not configured")

        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RootCauseAnalysisError(f"RCA model request failed: {exc}") from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RootCauseAnalysisError("RCA model response has no chat completion content") from exc

        if isinstance(content, list):
            content = "".join(
                part.get("text", "") for part in content if isinstance(part, Mapping)
            )
        if not isinstance(content, str) or not content.strip():
            raise RootCauseAnalysisError("RCA model returned empty content")
        return content


Client = Union[LLMClient, Callable[[str], str]]


class RootCauseAnalysisAgent:
    """Analyze one Context Builder prompt without reading files or writing fixes."""

    _VERDICTS = {"source_bug", "test_bug", "environment", "flaky", "unknown"}
    _BLAST_RADII = {"low", "medium", "high"}

    def __init__(self, client: Optional[Client] = None) -> None:
        self.client = client or OpenAICompatibleClient()

    def analyze(self, prompt: str) -> AnalysisResult:
        """Analyze exactly one already-built prompt."""

        if not isinstance(prompt, str) or not prompt.strip():
            raise RootCauseAnalysisError("RCA prompt must be a non-empty string")

        response = self._complete(prompt)
        payload = self._parse_json(response)
        return self._validate(payload)

    def _complete(self, prompt: str) -> str:
        if callable(self.client):
            return self.client(prompt)
        return self.client.complete(prompt)

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        if not isinstance(response, str) or not response.strip():
            raise RootCauseAnalysisError("RCA model returned an empty response")

        candidate = response.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            candidate = "\n".join(lines).strip()

        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RootCauseAnalysisError(f"RCA model did not return valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise RootCauseAnalysisError("RCA model JSON must be an object")
        return value

    def _validate(self, payload: Dict[str, Any]) -> AnalysisResult:
        required = {
            "bug_ids", "verdict", "faulty_location", "root_cause", "evidence",
            "fix_strategy", "affected_symbols", "blast_radius", "confidence",
            "needs_more_context", "assumptions",
        }
        missing = sorted(required - payload.keys())
        if missing:
            raise RootCauseAnalysisError(f"RCA output is missing fields: {', '.join(missing)}")

        self._require_list(payload, "bug_ids")
        self._require_list(payload, "evidence")
        self._require_list(payload, "affected_symbols")
        self._require_list(payload, "needs_more_context")
        self._require_list(payload, "assumptions")
        self._require_string(payload, "verdict")
        self._require_string(payload, "root_cause")
        self._require_string(payload, "fix_strategy")
        self._require_string(payload, "blast_radius")

        if payload["verdict"] not in self._VERDICTS:
            raise RootCauseAnalysisError(f"Unsupported RCA verdict: {payload['verdict']}")
        if payload["blast_radius"] not in self._BLAST_RADII:
            raise RootCauseAnalysisError(f"Unsupported blast radius: {payload['blast_radius']}")
        if isinstance(payload["confidence"], bool) or not isinstance(payload["confidence"], (int, float)):
            raise RootCauseAnalysisError("RCA confidence must be a number")
        if not 0 <= payload["confidence"] <= 1:
            raise RootCauseAnalysisError("RCA confidence must be between 0 and 1")

        location = payload["faulty_location"]
        parsed_location = None
        if location is not None:
            if not isinstance(location, dict):
                raise RootCauseAnalysisError("faulty_location must be an object or null")
            for field_name in ("file", "qualified_name", "line_start", "line_end"):
                if field_name not in location:
                    raise RootCauseAnalysisError(f"faulty_location is missing {field_name}")
            if (
                not isinstance(location["file"], str)
                or not isinstance(location["qualified_name"], str)
                or not isinstance(location["line_start"], int)
                or not isinstance(location["line_end"], int)
                or location["line_start"] < 1
                or location["line_end"] < location["line_start"]
            ):
                raise RootCauseAnalysisError("faulty_location has invalid file, symbol, or line range")
            parsed_location = FaultyLocation(**location)

        evidence = []
        for item in payload["evidence"]:
            if not isinstance(item, dict) or not isinstance(item.get("file"), str) or not isinstance(item.get("line"), int) or not isinstance(item.get("observation"), str):
                raise RootCauseAnalysisError("Each evidence item needs file, integer line, and observation")
            evidence.append(Evidence(**item))

        return AnalysisResult(
            bug_ids=payload["bug_ids"],
            verdict=payload["verdict"],
            faulty_location=parsed_location,
            root_cause=payload["root_cause"],
            evidence=evidence,
            fix_strategy=payload["fix_strategy"],
            affected_symbols=payload["affected_symbols"],
            blast_radius=payload["blast_radius"],
            confidence=float(payload["confidence"]),
            needs_more_context=payload["needs_more_context"],
            assumptions=payload["assumptions"],
        )

    @staticmethod
    def _require_list(payload: Dict[str, Any], field_name: str) -> None:
        if not isinstance(payload[field_name], list):
            raise RootCauseAnalysisError(f"RCA field '{field_name}' must be an array")

    @staticmethod
    def _require_string(payload: Dict[str, Any], field_name: str) -> None:
        if not isinstance(payload[field_name], str) or not payload[field_name].strip():
            raise RootCauseAnalysisError(f"RCA field '{field_name}' must be a non-empty string")