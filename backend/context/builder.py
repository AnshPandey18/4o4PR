"""Context Builder - Assembles LLM prompts with token budgeting.

Builds prompts for RCA by:
1. Loading prompt templates
2. Retrieving relevant code
3. Sanitizing and formatting
4. Managing token budget
5. Generating manifest
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from common.io import read_text, read_json, write_text, write_json, ensure_dir
from common.tokens import TokenCounter, create_token_counter
from common.hashing import short_hash
from indexer.query import RepoIndex, StaleIndexError
from .models import (
    BuiltContext, ContextManifest, ContextStatus, ContextTier, ItemForm,
    IncludedItem, DroppedItem, SanitizationSummary
)
from .sanitizer import sanitize_test_code, sanitize_source_code, should_exclude_file

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context for LLM analysis with token budgeting."""
    
    def __init__(
        self,
        project_root: Path,
        prompts_dir: Path,
        token_counter: TokenCounter,
        input_budget: int,
        output_reserved: int,
        tier_budgets: Optional[Dict[str, float]] = None,
        redact_patterns: Optional[List[str]] = None,
        denylist_files: Optional[List[str]] = None
    ):
        """Initialize context builder.
        
        Args:
            project_root: Project root directory
            prompts_dir: Directory containing prompt templates
            token_counter: Token counter for budgeting
            input_budget: Total input token budget
            output_reserved: Tokens reserved for output
            tier_budgets: Soft caps per tier (percentages)
            redact_patterns: Patterns for redacting secrets
            denylist_files: Files to never include
        """
        self.project_root = Path(project_root)
        self.prompts_dir = Path(prompts_dir)
        self.token_counter = token_counter
        self.input_budget = input_budget
        self.output_reserved = output_reserved
        
        # Default tier budgets (as percentages of input budget)
        self.tier_budgets = tier_budgets or {
            'T1_evidence': 0.20,
            'T2_tests': 0.20,
            'T3_suspects': 0.30,
            'T4_neighbors': 0.20,
            'T5_repo_map': 0.10
        }
        
        self.redact_patterns = redact_patterns or []
        self.denylist_files = denylist_files or []
        
        # Load templates
        self.system_rules = self._load_system_rules()
        self.output_schema = self._load_output_schema()
        
        # Extension tracking (for extend() API)
        self.extend_count = 0
        self.max_extends = 2
    
    def build(
        self,
        group: Dict,
        bugs: Dict[str, Dict],
        index: RepoIndex,
        run_id: str,
        attempt: int = 1
    ) -> BuiltContext:
        """Build context for a bug group.
        
        Args:
            group: BugGroup dictionary
            bugs: Dict mapping bug_id to bug dictionary
            index: RepoIndex for code retrieval
            run_id: Run identifier
            attempt: Attempt number (for extend() calls)
            
        Returns:
            BuiltContext with prompt and manifest
        """
        group_id = group['group_id']
        bug_ids = group['bug_ids']
        
        logger.info(f"Building context for {group_id} (attempt {attempt})")
        
        # Initialize manifest
        manifest = ContextManifest(
            stage="analysis",
            run_id=run_id,
            group_id=group_id,
            bug_ids=bug_ids,
            attempt=attempt,
            status="ok",
            prompt_version="analysis_v1",
            token_method=self.token_counter.name(),
            budget={
                'input': self.input_budget,
                'output_reserved': self.output_reserved,
                'used': 0
            },
            retrieval="evidence",
            sanitization=SanitizationSummary(),
            included=[],
            dropped=[],
            warnings=[]
        )
        
        # Compute nonce for section tags
        nonce = self._compute_nonce(group['group_key'], "analysis_v1")
        
        # Build context sections
        sections = []
        
        try:
            # T0: System rules (always included)
            t0_text, t0_tokens = self._build_t0_section(nonce)
            sections.append(t0_text)
            manifest.included.append(IncludedItem(
                item="system_rules",
                tier="T0",
                form="verbatim",
                tokens=t0_tokens,
                reason="required"
            ))
            
            # T1: Failure evidence
            t1_text, t1_items = self._build_t1_section(bug_ids, bugs, nonce)
            sections.append(t1_text)
            manifest.included.extend(t1_items)
            
            # T2: Test code (sanitized)
            t2_text, t2_items, san_summary = self._build_t2_section(bug_ids, bugs, index, nonce)
            sections.append(t2_text)
            manifest.included.extend(t2_items)
            manifest.sanitization.docstrings_removed += san_summary.docstrings_removed
            manifest.sanitization.comments_removed += san_summary.comments_removed
            
            # T3: Suspect functions (required)
            t3_text, t3_items, t3_dropped = self._build_t3_section(group, bugs, index, nonce)
            sections.append(t3_text)
            manifest.included.extend(t3_items)
            manifest.dropped.extend(t3_dropped)
            
            # Check if required tiers fit
            current_text = '\n\n'.join(sections)
            current_tokens = self.token_counter.count(current_text)
            
            if current_tokens > self.input_budget:
                # Required tiers don't fit - overflow
                manifest.status = "overflow"
                manifest.dropped.append(DroppedItem(
                    item="entire_context",
                    tier="all",
                    reason=f"required_tiers_exceed_budget ({current_tokens} > {self.input_budget})"
                ))
                
                return BuiltContext(
                    status=ContextStatus.OVERFLOW,
                    prompt_text=None,
                    manifest=manifest
                )
            
            # T4: Neighbors (optional)
            remaining_budget = self.input_budget - current_tokens
            t4_budget = int(self.input_budget * self.tier_budgets.get('T4_neighbors', 0.20))
            t4_budget = min(t4_budget, remaining_budget)
            
            if t4_budget > 100:
                t4_text, t4_items, t4_dropped = self._build_t4_section(
                    group, index, nonce, t4_budget
                )
                if t4_text:
                    sections.append(t4_text)
                    manifest.included.extend(t4_items)
                manifest.dropped.extend(t4_dropped)
            
            # T5: Repo map (optional)
            current_text = '\n\n'.join(sections)
            current_tokens = self.token_counter.count(current_text)
            remaining_budget = self.input_budget - current_tokens
            t5_budget = min(
                int(self.input_budget * self.tier_budgets.get('T5_repo_map', 0.10)),
                remaining_budget
            )
            
            if t5_budget > 100:
                t5_text, t5_items = self._build_t5_section(group, index, nonce, t5_budget)
                if t5_text:
                    sections.append(t5_text)
                    manifest.included.extend(t5_items)
            
            # T6: Output schema (always last)
            t6_text, t6_tokens = self._build_t6_section(nonce)
            sections.append(t6_text)
            manifest.included.append(IncludedItem(
                item="output_schema",
                tier="T6",
                form="verbatim",
                tokens=t6_tokens,
                reason="required"
            ))
            
            # Assemble final prompt
            prompt_text = '\n\n'.join(sections)
            
            # Final token count
            final_tokens = self.token_counter.count(prompt_text)
            manifest.budget['used'] = final_tokens
            
            # Check final budget
            if final_tokens > self.input_budget:
                # This shouldn't happen if we did budgeting correctly
                manifest.warnings.append(
                    f"Final token count ({final_tokens}) exceeds budget ({self.input_budget})"
                )
            
            logger.info(f"Context built: {final_tokens} tokens used")
            
            return BuiltContext(
                status=ContextStatus.OK,
                prompt_text=prompt_text,
                manifest=manifest
            )
        
        except StaleIndexError as e:
            manifest.warnings.append(f"StaleIndexError: {e}")
            manifest.status = "overflow"
            return BuiltContext(
                status=ContextStatus.OVERFLOW,
                prompt_text=None,
                manifest=manifest
            )
        
        except Exception as e:
            logger.error(f"Failed to build context: {e}", exc_info=True)
            manifest.warnings.append(f"BuildError: {e}")
            manifest.status = "overflow"
            return BuiltContext(
                status=ContextStatus.OVERFLOW,
                prompt_text=None,
                manifest=manifest
            )
    
    def extend(
        self,
        context: BuiltContext,
        additional_symbols: List[str],
        index: RepoIndex,
        bugs: Dict[str, Dict]
    ) -> BuiltContext:
        """Extend a context with additional symbols.
        
        Args:
            context: Previous BuiltContext
            additional_symbols: List of symbol IDs to add
            index: RepoIndex for retrieval
            bugs: Bug dictionaries
            
        Returns:
            New BuiltContext with extended content
        """
        self.extend_count += 1
        
        if self.extend_count > self.max_extends:
            raise RuntimeError(
                f"Maximum extend rounds exceeded ({self.max_extends}). "
                f"Cannot extend context further."
            )
        
        logger.info(f"Extending context with {len(additional_symbols)} symbols (round {self.extend_count})")
        
        # Rebuild with additional symbols marked as required
        # For simplicity in this implementation, we'll just note this limitation
        # A full implementation would modify the build process to include these symbols
        
        raise NotImplementedError(
            "Context extension not fully implemented. "
            "This would require rebuilding the context with additional symbols in T3."
        )
    
    def _load_system_rules(self) -> str:
        """Load system rules template."""
        rules_path = self.prompts_dir / "system_rules.md"
        return read_text(rules_path)
    
    def _load_output_schema(self) -> str:
        """Load output schema."""
        schema_path = self.prompts_dir / "output_schema.json"
        schema_dict = read_json(schema_path)
        # Pretty-print the schema
        import json
        return json.dumps(schema_dict, indent=2)
    
    def _compute_nonce(self, group_key: str, prompt_version: str) -> str:
        """Compute nonce for section tags.
        
        Args:
            group_key: Group key (hash of bug IDs)
            prompt_version: Prompt version
            
        Returns:
            6-character hex nonce
        """
        combined = f"{group_key}_{prompt_version}"
        return short_hash(combined, length=6)
    
    def _wrap_section(self, tag: str, content: str, nonce: str) -> str:
        """Wrap content in tagged section.
        
        Args:
            tag: Section tag (e.g., "code", "test")
            content: Section content
            nonce: Nonce for tag uniqueness
            
        Returns:
            Wrapped content
        """
        return f"<{tag}_{nonce}>\n{content}\n</{tag}_{nonce}>"
    
    def _build_t0_section(self, nonce: str) -> Tuple[str, int]:
        """Build T0: System rules section.
        
        Returns:
            Tuple of (section_text, token_count)
        """
        text = self._wrap_section("rules", self.system_rules, nonce)
        tokens = self.token_counter.count(text)
        return text, tokens
    
    def _build_t1_section(
        self,
        bug_ids: List[str],
        bugs: Dict[str, Dict],
        nonce: str
    ) -> Tuple[str, List[IncludedItem]]:
        """Build T1: Failure evidence section.
        
        Returns:
            Tuple of (section_text, included_items)
        """
        lines = ["# Failure Evidence\n"]
        items = []
        
        for bug_id in bug_ids:
            bug = bugs.get(bug_id)
            if not bug:
                continue
            
            lines.append(f"## Bug: {bug['test_name']}")
            lines.append(f"**Bug ID:** `{bug_id}`\n")
            
            # Error information
            lines.append(f"**Error Type:** {bug['error_type']}")
            lines.append(f"**Error Message:**")
            lines.append(f"```")
            lines.append(bug['error_message'])
            lines.append(f"```\n")
            
            # Assertion details
            if bug.get('first_failing_assertion'):
                assertion = bug['first_failing_assertion']
                lines.append(f"**Failing Assertion:**")
                lines.append(f"- Statement: `{assertion['statement']}`")
                lines.append(f"- Line: {assertion['line']}")
                lines.append(f"- Assertion {assertion['assertion_index']} of {assertion['assert_total']}")
                if assertion['assertions_not_evaluated'] > 0:
                    lines.append(
                        f"- {assertion['assertions_not_evaluated']} assertion(s) not evaluated after this failure"
                    )
                lines.append("")
            
            # Structured frames
            if bug.get('frames'):
                lines.append(f"**Traceback Frames:**")
                for frame in bug['frames']:
                    external_marker = " [EXTERNAL]" if frame.get('external') else ""
                    lines.append(f"- {frame['file']}:{frame['line']} in {frame['function']}{external_marker}")
                lines.append("")
            
            items.append(IncludedItem(
                item=f"evidence_{bug_id}",
                tier="T1",
                form="verbatim",
                tokens=0,  # Will be counted in total
                reason="failure_evidence"
            ))
        
        text = self._wrap_section("evidence", '\n'.join(lines), nonce)
        tokens = self.token_counter.count(text)
        
        # Update token counts
        for item in items:
            item.tokens = tokens // len(items) if items else 0
        
        return text, items
    
    def _build_t2_section(
        self,
        bug_ids: List[str],
        bugs: Dict[str, Dict],
        index: RepoIndex,
        nonce: str
    ) -> Tuple[str, List[IncludedItem], SanitizationSummary]:
        """Build T2: Test code section (sanitized).
        
        Returns:
            Tuple of (section_text, included_items, sanitization_summary)
        """
        lines = ["# Test Code\n"]
        items = []
        total_summary = SanitizationSummary()
        
        seen_tests = set()
        
        for bug_id in bug_ids:
            bug = bugs.get(bug_id)
            if not bug:
                continue
            
            test_name = bug['test_name']
            if test_name in seen_tests:
                continue
            seen_tests.add(test_name)
            
            # Get test code and sanitize
            test_code = bug.get('code', '')
            if test_code:
                sanitized_code, summary = sanitize_test_code(test_code)
                total_summary.docstrings_removed += summary.docstrings_removed
                total_summary.comments_removed += summary.comments_removed
                
                lines.append(f"## Test: {test_name}\n")
                lines.append("```python")
                lines.append(sanitized_code)
                lines.append("```\n")
                
                items.append(IncludedItem(
                    item=test_name,
                    tier="T2",
                    form="full",
                    tokens=self.token_counter.count(sanitized_code),
                    reason="test_function"
                ))
        
        text = self._wrap_section("tests", '\n'.join(lines), nonce)
        return text, items, total_summary
    
    def _build_t3_section(
        self,
        group: Dict,
        bugs: Dict[str, Dict],
        index: RepoIndex,
        nonce: str
    ) -> Tuple[str, List[IncludedItem], List[DroppedItem]]:
        """Build T3: Suspect functions section.
        
        Returns:
            Tuple of (section_text, included_items, dropped_items)
        """
        lines = ["# Suspect Functions\n"]
        items = []
        dropped = []
        
        # Collect suspect symbols from the group
        suspect_symbols = set(group['suspect']['symbols'])
        
        # Also collect from bug called_symbols
        for bug_id in group['bug_ids']:
            bug = bugs.get(bug_id)
            if bug:
                for called_sym in bug.get('called_symbols', []):
                    if called_sym.get('symbol_id') and called_sym['resolution'] == 'resolved':
                        suspect_symbols.add(called_sym['symbol_id'])
        
        # Retrieve and include suspect source code
        for symbol_id in sorted(suspect_symbols):
            try:
                # Check if file is denylisted
                file_part = symbol_id.split('::')[0]
                if should_exclude_file(file_part, self.denylist_files):
                    dropped.append(DroppedItem(
                        item=symbol_id,
                        tier="T3",
                        reason="denylisted"
                    ))
                    continue
                
                # Get source with line numbers
                source = index.get_source(symbol_id, with_line_numbers=True)
                
                # Sanitize (redact secrets)
                sanitized_source, san_summary = sanitize_source_code(source, self.redact_patterns)
                
                symbol = index.get_symbol(symbol_id)
                if symbol:
                    lines.append(f"## {symbol_id}")
                    lines.append(f"Location: `{symbol.file}:{symbol.line_start}-{symbol.line_end}`\n")
                    lines.append("```python")
                    lines.append(sanitized_source)
                    lines.append("```\n")
                    
                    items.append(IncludedItem(
                        item=symbol_id,
                        tier="T3",
                        form="full",
                        lines=f"{symbol.line_start}-{symbol.line_end}",
                        tokens=self.token_counter.count(sanitized_source),
                        reason="suspect_function"
                    ))
            
            except StaleIndexError:
                raise  # Propagate to caller
            except Exception as e:
                logger.warning(f"Failed to retrieve {symbol_id}: {e}")
                dropped.append(DroppedItem(
                    item=symbol_id,
                    tier="T3",
                    reason=f"not_found ({str(e)[:50]})"
                ))
        
        if not items:
            # No suspect symbols retrieved
            lines.append("*(No suspect functions could be retrieved)*\n")
        
        text = self._wrap_section("code", '\n'.join(lines), nonce)
        return text, items, dropped
    
    def _build_t4_section(
        self,
        group: Dict,
        index: RepoIndex,
        nonce: str,
        budget: int
    ) -> Tuple[str, List[IncludedItem], List[DroppedItem]]:
        """Build T4: Neighbor functions (callers/callees).
        
        Returns:
            Tuple of (section_text, included_items, dropped_items)
        """
        lines = ["# Related Functions\n"]
        items = []
        dropped = []
        
        # Collect neighbors (callers and callees)
        suspect_symbols = set(group['suspect']['symbols'])
        neighbors = set()
        
        for symbol_id in suspect_symbols:
            callers = index.get_callers(symbol_id)
            callees = index.get_callees(symbol_id)
            neighbors.update(callers)
            neighbors.update(callees)
        
        # Remove suspects themselves
        neighbors -= suspect_symbols
        
        # Sort neighbors (prioritize by whether they appear in failing assertions)
        # For now, simple alphabetical sort
        neighbors = sorted(neighbors)
        
        used_tokens = 0
        
        for symbol_id in neighbors:
            if used_tokens >= budget:
                dropped.append(DroppedItem(
                    item=symbol_id,
                    tier="T4",
                    reason="over_budget"
                ))
                continue
            
            try:
                symbol = index.get_symbol(symbol_id)
                if not symbol:
                    continue
                
                # Include signature only for T4
                signature_text = f"{symbol.name}{symbol.signature}"
                if symbol.docstring:
                    signature_text += f'  # {symbol.docstring}'
                
                tokens = self.token_counter.count(signature_text)
                
                if used_tokens + tokens > budget:
                    dropped.append(DroppedItem(
                        item=symbol_id,
                        tier="T4",
                        reason="over_budget"
                    ))
                    break
                
                lines.append(f"- `{symbol.file}::{symbol.name}{symbol.signature}`")
                if symbol.docstring:
                    lines.append(f"  *{symbol.docstring}*")
                lines.append("")
                
                items.append(IncludedItem(
                    item=symbol_id,
                    tier="T4",
                    form="signature",
                    tokens=tokens,
                    reason="neighbor"
                ))
                
                used_tokens += tokens
            
            except Exception as e:
                logger.debug(f"Skipping neighbor {symbol_id}: {e}")
                continue
        
        if not items:
            return "", [], dropped
        
        text = self._wrap_section("neighbors", '\n'.join(lines), nonce)
        return text, items, dropped
    
    def _build_t5_section(
        self,
        group: Dict,
        index: RepoIndex,
        nonce: str,
        budget: int
    ) -> Tuple[str, List[IncludedItem]]:
        """Build T5: Repository map.
        
        Returns:
            Tuple of (section_text, included_items)
        """
        lines = ["# Repository Structure\n"]
        items = []
        
        # Get the package containing suspect files
        suspect_file = group['suspect']['file']
        if '/' in suspect_file:
            package_prefix = suspect_file.rsplit('/', 1)[0]
        else:
            package_prefix = None
        
        # Get file tree
        try:
            tree = index.file_tree(prefix=package_prefix, depth=2)
            tokens = self.token_counter.count(tree)
            
            if tokens <= budget:
                lines.append("```")
                lines.append(tree)
                lines.append("```\n")
                
                items.append(IncludedItem(
                    item=f"file_tree_{package_prefix or 'root'}",
                    tier="T5",
                    form="compressed",
                    tokens=tokens,
                    reason="repository_map"
                ))
        except:
            pass
        
        if not items:
            return "", []
        
        text = self._wrap_section("repo_map", '\n'.join(lines), nonce)
        return text, items
    
    def _build_t6_section(self, nonce: str) -> Tuple[str, int]:
        """Build T6: Output schema section.
        
        Returns:
            Tuple of (section_text, token_count)
        """
        lines = [
            "# Required Output Format\n",
            "You must respond with valid JSON matching this exact schema:\n",
            "```json",
            self.output_schema,
            "```"
        ]
        
        text = self._wrap_section("schema", '\n'.join(lines), nonce)
        tokens = self.token_counter.count(text)
        return text, tokens


def save_context_artifacts(
    context: BuiltContext,
    output_dir: Path
) -> None:
    """Save context artifacts to disk.
    
    Args:
        context: BuiltContext to save
        output_dir: Output directory
    """
    ensure_dir(output_dir)
    
    # Save manifest
    manifest_path = output_dir / "context_manifest.json"
    write_json(manifest_path, context.manifest.to_dict())
    
    # Save prompt text if available
    if context.prompt_text:
        prompt_path = output_dir / "analysis_context.txt"
        write_text(prompt_path, context.prompt_text)
