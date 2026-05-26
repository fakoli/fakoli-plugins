"""Tests for fakoli_state.planning.llm_planner — LLM-driven task generation."""

from __future__ import annotations

import datetime

import pytest

from fakoli_state.clock import FrozenClock
from fakoli_state.planning.llm import LLMResponse, RecordedLLMProvider
from fakoli_state.planning.llm_planner import (
    PlannerProviderUnavailable,
    TaskGenerationError,
    _build_user_prompt,
    _SYSTEM_PROMPT,
    _validate_and_normalize,
    generate_tasks_markdown,
    resolve_planner_provider,
)
from fakoli_state.planning.template import parse_prd
from fakoli_state.state.models import PRD, Feature, Requirement, Task

_FROZEN = FrozenClock(datetime.datetime(2026, 5, 26, 12, 0, tzinfo=datetime.UTC))


# ---------------------------------------------------------------------------
# resolve_planner_provider — the tier chain
# ---------------------------------------------------------------------------


class TestResolvePlannerProvider:
    """v1.17.0 — multi-provider precedence + env auto-detect + config wins."""

    # --- env auto-detect path (no config supplied) ---------------------

    def test_anthropic_chosen_when_api_key_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ANTHROPIC_API_KEY alone in env → anthropic."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-not-real")
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("CUSTOM_LLM_BASE_URL", raising=False)
        provider, tier = resolve_planner_provider()
        assert tier == "anthropic"
        assert hasattr(provider, "generate")

    def test_anthropic_wins_over_aws_when_both_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both ANTHROPIC_API_KEY and AWS_REGION are set, direct API
        wins because it's cheaper per token. Users who want Bedrock pinning
        must set llm_provider in config."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        provider, tier = resolve_planner_provider()
        assert tier == "anthropic"

    def test_custom_chosen_when_only_custom_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CUSTOM_LLM_BASE_URL alone → custom."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "http://localhost:8000/v1")
        provider, tier = resolve_planner_provider()
        assert tier == "custom"

    def test_raises_when_nothing_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No config + no env vars → fail loudly with a help message that
        names every supported provider path."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
        monkeypatch.delenv("CUSTOM_LLM_BASE_URL", raising=False)
        with pytest.raises(PlannerProviderUnavailable) as exc_info:
            resolve_planner_provider()
        msg = str(exc_info.value)
        assert "ANTHROPIC_API_KEY" in msg
        assert "Bedrock" in msg or "bedrock" in msg
        assert "CUSTOM_LLM_BASE_URL" in msg

    # --- explicit config precedence over env ---------------------------

    def test_config_provider_wins_over_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config.llm_provider="custom" wins even when ANTHROPIC_API_KEY is
        the only env variable set. (We construct a custom provider so the
        test does not need the openai SDK on the env path.)"""
        from fakoli_state.config import Config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
        monkeypatch.setenv("CUSTOM_LLM_BASE_URL", "http://localhost:8000/v1")
        cfg = Config(
            project_name="t",
            project_id="t",
            llm_provider="custom",
            llm_model="gpt-4o-mini",  # explicit model for custom
        )
        provider, tier = resolve_planner_provider(cfg)
        assert tier == "custom"

    def test_config_tier_threads_to_anthropic_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config.llm_tier="opus" → AnthropicProvider built with the Opus id."""
        from fakoli_state.config import Config
        from fakoli_state.planning.llm import MODEL_TIERS

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
        cfg = Config(
            project_name="t",
            project_id="t",
            llm_provider="anthropic",
            llm_tier="opus",
        )
        provider, tier = resolve_planner_provider(cfg)
        assert tier == "anthropic"
        # The provider should have built with the Opus model id from
        # the direct-API tier table.
        assert provider._model == MODEL_TIERS["opus"]  # type: ignore[attr-defined]

    def test_config_explicit_model_overrides_tier(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config.llm_model wins over llm_tier when both are set."""
        from fakoli_state.config import Config

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")
        cfg = Config(
            project_name="t",
            project_id="t",
            llm_provider="anthropic",
            llm_tier="haiku",
            llm_model="claude-opus-4-7-20260601",
        )
        provider, _ = resolve_planner_provider(cfg)
        assert provider._model == "claude-opus-4-7-20260601"  # type: ignore[attr-defined]


class TestResolveModelForTier:
    """v1.17.0 — tier ↔ model-id mapping helper."""

    def test_direct_api_table(self) -> None:
        from fakoli_state.planning.llm import resolve_model_for_tier

        assert resolve_model_for_tier("opus") == "claude-opus-4-7"
        assert resolve_model_for_tier("sonnet") == "claude-sonnet-4-6"
        assert resolve_model_for_tier("haiku") == "claude-haiku-4-5"

    def test_bedrock_table_has_us_prefix(self) -> None:
        from fakoli_state.planning.llm import resolve_model_for_tier

        assert resolve_model_for_tier("opus", bedrock=True).startswith(
            "us.anthropic."
        )
        assert resolve_model_for_tier("sonnet", bedrock=True).startswith(
            "us.anthropic."
        )

    def test_unknown_tier_raises_valueerror(self) -> None:
        import pytest as _pytest

        from fakoli_state.planning.llm import resolve_model_for_tier

        with _pytest.raises(ValueError) as exc_info:
            resolve_model_for_tier("supernova")
        assert "supernova" in str(exc_info.value)
        # Error message should name the valid tiers so the user can fix it.
        assert "opus" in str(exc_info.value)


class TestCustomEndpointProvider:
    """v1.17.0 — OpenAI-compatible endpoint provider."""

    def test_requires_explicit_model(self) -> None:
        """No portable default model → ValueError when model is empty."""
        import pytest as _pytest

        from fakoli_state.planning.llm import CustomEndpointProvider

        with _pytest.raises(ValueError) as exc_info:
            CustomEndpointProvider(model="", base_url="http://localhost:8000/v1")
        assert "model" in str(exc_info.value).lower()

    def test_missing_base_url_and_env_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No base_url arg AND no CUSTOM_LLM_BASE_URL env → ValueError."""
        import pytest as _pytest

        from fakoli_state.planning.llm import CustomEndpointProvider

        monkeypatch.delenv("CUSTOM_LLM_BASE_URL", raising=False)
        with _pytest.raises(ValueError) as exc_info:
            CustomEndpointProvider(model="any-model")
        assert "base_url" in str(exc_info.value) or "CUSTOM_LLM_BASE_URL" in str(
            exc_info.value
        )


# ---------------------------------------------------------------------------
# _build_user_prompt — assembly from PRD model
# ---------------------------------------------------------------------------


def _feat(feat_id: str, title: str, requirements: list[str]) -> Feature:
    return Feature(id=feat_id, title=title, description=f"Description of {title}.",
                   requirements=requirements, tasks=[])


def _req(req_id: str, text: str) -> Requirement:
    return Requirement(id=req_id, prd_section="requirements", text=text)


class TestBuildUserPrompt:
    def test_includes_summary_goals_and_requirements(self) -> None:
        prd = PRD(
            summary="A simple CLI for converting JSON to YAML.",
            goals=["Convert JSON to YAML.", "Preserve key order."],
            non_goals=["Round-trip YAML→JSON."],
            requirements=["R001", "R002"],
        )
        prompt = _build_user_prompt(
            prd=prd,
            features=[_feat("F001", "Conversion", ["R001", "R002"])],
            requirements=[
                _req("R001", "Accept JSON file paths"),
                _req("R002", "Write YAML output"),
            ],
            existing_tasks=None,
        )
        assert "## Summary" in prompt
        assert "JSON to YAML" in prompt
        assert "## Goals" in prompt
        assert "Preserve key order" in prompt
        assert "## Non-Goals" in prompt
        assert "Round-trip YAML→JSON" in prompt
        assert "## Requirements" in prompt
        assert "R001" in prompt and "R002" in prompt
        assert "F001" in prompt and "Conversion" in prompt

    def test_existing_tasks_advances_id_counter(self) -> None:
        """When existing tasks are passed, the prompt tells the LLM the next
        ID to use so it doesn't collide."""
        prd = PRD(summary="x", goals=["g"], requirements=["R001"])
        existing = _existing_task("T005")
        prompt = _build_user_prompt(
            prd=prd,
            features=[_feat("F001", "Feature", ["R001"])],
            requirements=[_req("R001", "r")],
            existing_tasks=[existing],
        )
        assert "T005" in prompt
        assert "T006" in prompt, "Next available ID after T005 should be T006"

    def test_omits_optional_sections_when_empty(self) -> None:
        prd = PRD(summary="x", goals=["g"], requirements=["R001"])
        prompt = _build_user_prompt(
            prd=prd,
            features=[_feat("F001", "F", ["R001"])],
            requirements=[_req("R001", "r")],
            existing_tasks=None,
        )
        assert "## Non-Goals" not in prompt
        assert "## Risks" not in prompt
        assert "## Open Questions" not in prompt


def _existing_task(task_id: str) -> Task:
    from fakoli_state.state.models import Score, TaskPriority, TaskStatus, Verification
    now = _FROZEN.now()
    return Task(
        id=task_id,
        feature_id="F001",
        title=f"Existing {task_id}",
        description="",
        status=TaskStatus.drafted,
        priority=TaskPriority.medium,
        scores=Score(),
        acceptance_criteria=["Works"],
        verification=Verification(commands=["pytest"]),
        likely_files=[],
        created_at=now,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# _validate_and_normalize — robust to LLM output quirks
# ---------------------------------------------------------------------------


class TestValidateAndNormalize:
    def test_clean_response_returns_unchanged(self) -> None:
        raw = """\
## Tasks

### T001: First task

**Feature:** F001
**Priority:** medium
**Likely files:** src/foo.py

Description.

**Acceptance criteria:**

- Works.

**Verification:**

- `pytest tests/`
"""
        text, count = _validate_and_normalize(raw)
        assert "## Tasks" in text
        assert count == 1

    def test_strips_markdown_code_fences(self) -> None:
        """Some models wrap the output in ```markdown ... ``` despite the
        instruction. Strip the fences so the downstream parser sees clean
        markdown."""
        raw = """```markdown
## Tasks

### T001: A

**Feature:** F001
**Priority:** high
**Likely files:** src/x.py

d

**Acceptance criteria:**

- a

**Verification:**

- `pytest`
```"""
        text, count = _validate_and_normalize(raw)
        assert not text.startswith("```")
        assert count == 1

    def test_adds_missing_tasks_header(self) -> None:
        """Some models forget the `## Tasks` header and jump straight to
        `### T001:`. Re-add the header so the parser can find the section."""
        raw = """\
### T001: A

**Feature:** F001
**Priority:** medium
**Likely files:** src/x.py

d

**Acceptance criteria:**

- a

**Verification:**

- `pytest`
"""
        text, count = _validate_and_normalize(raw)
        assert text.lstrip().lower().startswith("## tasks")
        assert count == 1

    def test_empty_response_raises(self) -> None:
        with pytest.raises(TaskGenerationError, match="empty"):
            _validate_and_normalize("")
        with pytest.raises(TaskGenerationError, match="empty"):
            _validate_and_normalize("   \n\n  ")

    def test_no_task_blocks_raises(self) -> None:
        """Response without any `### TXXX:` blocks fails loudly so the agent
        can see what the LLM actually wrote."""
        raw = """## Tasks

Some descriptive prose but no actual task blocks.
"""
        with pytest.raises(TaskGenerationError, match="### TXXX"):
            _validate_and_normalize(raw)

    def test_counts_multiple_tasks(self) -> None:
        raw = """\
## Tasks

### T001: One

**Feature:** F001
**Priority:** medium
**Likely files:** a

d

**Acceptance criteria:**

- a

**Verification:**

- `c`

### T002: Two

**Feature:** F001
**Priority:** medium
**Likely files:** b

d

**Acceptance criteria:**

- b

**Verification:**

- `c2`
"""
        text, count = _validate_and_normalize(raw)
        assert count == 2


# ---------------------------------------------------------------------------
# generate_tasks_markdown — end-to-end with recorded provider
# ---------------------------------------------------------------------------


def _canned_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=50,
        model="claude-opus-4-7",
        finish_reason="end_turn",
    )


_CANNED_TASKS_MARKDOWN = """## Tasks

### T001: Implement JSON parser

**Feature:** F001
**Priority:** high
**Likely files:** src/jy2yaml/parser.py

Parse JSON files into Python dicts preserving key order.

**Acceptance criteria:**

- A valid JSON file produces a dict with original key order.
- Invalid JSON raises a clear error including the filename.

**Verification:**

- `pytest tests/test_parser.py -v`

### T002: Implement YAML writer

**Feature:** F001
**Priority:** high
**Likely files:** src/jy2yaml/writer.py

Write Python dicts to YAML preserving the dict's iteration order.

**Acceptance criteria:**

- The output YAML re-parses to the same dict.
- Keys appear in the same order as the input dict.

**Verification:**

- `pytest tests/test_writer.py -v`
"""


class TestGenerateTasksMarkdown:
    def test_happy_path_with_injected_provider(self) -> None:
        """End-to-end: build prompt, run via recorded provider, validate output."""
        prd = PRD(
            summary="JSON to YAML CLI",
            goals=["Convert JSON to YAML"],
            requirements=["R001"],
        )
        features = [_feat("F001", "Conversion", ["R001"])]
        requirements = [_req("R001", "Accept JSON file path")]

        user_prompt = _build_user_prompt(prd, features, requirements, None)
        key = RecordedLLMProvider.record_key(
            _SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.0
        )
        provider = RecordedLLMProvider({key: _canned_response(_CANNED_TASKS_MARKDOWN)})

        result = generate_tasks_markdown(
            prd=prd,
            features=features,
            requirements=requirements,
            provider=provider,
        )
        assert result.task_count == 2
        assert "## Tasks" in result.markdown
        assert "T001" in result.markdown and "T002" in result.markdown
        assert result.provider_used == "injected"

    def test_generated_markdown_round_trips_through_parser(self) -> None:
        """The generated markdown MUST be parseable by the existing
        planning.template.parse_prd parser. This is the round-trip contract
        that lets the CLI append generated tasks to prd.md and re-parse
        without duplicating logic."""
        prd_markdown = """\
# Project: Round-Trip Test

## Summary

A test project.

## Goals

- Test the round trip.

## Requirements

- R001: First requirement.

## Features

### F001: Single feature

**Requirements:** R001

A description.
"""
        # Generate tasks via the LLM, append to the PRD, re-parse end-to-end.
        parsed = parse_prd(prd_markdown, clock=_FROZEN)
        user_prompt = _build_user_prompt(
            parsed.prd, parsed.features, parsed.requirements, None
        )
        key = RecordedLLMProvider.record_key(
            _SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.0
        )
        provider = RecordedLLMProvider({key: _canned_response(_CANNED_TASKS_MARKDOWN)})
        result = generate_tasks_markdown(
            prd=parsed.prd,
            features=parsed.features,
            requirements=parsed.requirements,
            provider=provider,
        )

        # Append the generated markdown to the PRD and re-parse.
        full_prd = prd_markdown + "\n" + result.markdown
        reparsed = parse_prd(full_prd, clock=_FROZEN)

        assert len(reparsed.tasks) == 2
        assert reparsed.tasks[0].id == "T001"
        assert reparsed.tasks[1].id == "T002"
        assert reparsed.tasks[0].feature_id == "F001"
        assert reparsed.tasks[0].acceptance_criteria
        assert reparsed.tasks[0].verification.commands

    def test_provider_resolution_when_provider_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When provider=None, resolve_planner_provider() is called and the
        resulting tier_name is reflected in the response."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake")

        # We can't actually call the real Anthropic API in a test, so we
        # monkeypatch resolve_planner_provider to return a recorded one
        # with the right key.
        prd = PRD(summary="x", goals=["g"], requirements=["R001"])
        features = [_feat("F001", "F", ["R001"])]
        requirements = [_req("R001", "r")]
        user_prompt = _build_user_prompt(prd, features, requirements, None)
        key = RecordedLLMProvider.record_key(
            _SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.0
        )
        recorded = RecordedLLMProvider({key: _canned_response(_CANNED_TASKS_MARKDOWN)})

        from fakoli_state.planning import llm_planner as planner_mod
        monkeypatch.setattr(
            planner_mod,
            "resolve_planner_provider",
            lambda config=None: (recorded, "anthropic"),
        )

        result = generate_tasks_markdown(
            prd=prd, features=features, requirements=requirements
        )
        assert result.provider_used == "anthropic"
        assert result.task_count == 2

    def test_validation_error_propagates(self) -> None:
        """A bad LLM response raises TaskGenerationError, not a silent zero-count
        success."""
        prd = PRD(summary="x", goals=["g"], requirements=["R001"])
        features = [_feat("F001", "F", ["R001"])]
        requirements = [_req("R001", "r")]
        user_prompt = _build_user_prompt(prd, features, requirements, None)
        key = RecordedLLMProvider.record_key(
            _SYSTEM_PROMPT, user_prompt, max_tokens=8000, temperature=0.0
        )
        bad_response = _canned_response("Sorry, I don't know how to plan this.")
        provider = RecordedLLMProvider({key: bad_response})

        with pytest.raises(TaskGenerationError):
            generate_tasks_markdown(
                prd=prd,
                features=features,
                requirements=requirements,
                provider=provider,
            )


# ---------------------------------------------------------------------------
# System prompt — dependency-emission instructions (v1.16.0)
# ---------------------------------------------------------------------------


class TestSystemPromptInstructsDependencyEmission:
    """v1.16.0: the system prompt MUST instruct the LLM to identify and
    emit `**Dependencies:**` from acceptance criteria text. Regression for
    a user-reported bug where T002's chaos-test task obviously depended
    on T001's HttpTransport implementation but the planner's task graph
    showed `dependencies=[]` — the prompt didn't tell the model to look
    for them."""

    def test_prompt_shows_dependencies_in_output_format(self) -> None:
        """The example template inside the system prompt must include a
        `**Dependencies:**` line so the model knows the field exists."""
        assert "**Dependencies:**" in _SYSTEM_PROMPT, (
            "System prompt must include **Dependencies:** in the example "
            "task block so the LLM knows the field is part of the contract."
        )

    def test_prompt_explains_when_to_emit_dependencies(self) -> None:
        """The prompt must explicitly describe the two trigger conditions
        for emitting a dependency (infrastructure dep + phrasal dep in
        criteria) — otherwise the model treats Dependencies as optional
        in the I-don't-know-when sense."""
        prompt = _SYSTEM_PROMPT.lower()
        # Trigger 1: infrastructure dependency
        assert "infrastructure" in prompt, (
            "Prompt must name 'infrastructure dependency' so the LLM "
            "recognises the T001-implements / T002-tests pattern."
        )
        # Trigger 2: phrasal criteria match
        assert "acceptance criteria" in prompt, (
            "Prompt must reference acceptance criteria as a source of "
            "dependency signals."
        )

    def test_prompt_says_omit_field_when_no_dependencies(self) -> None:
        """The prompt must tell the model to OMIT the field entirely when
        no deps exist — not emit an empty `**Dependencies:**` line that
        the parser would treat as an empty list (harmless but noisy)."""
        assert "omit" in _SYSTEM_PROMPT.lower()

    def test_prompt_warns_against_cycles(self) -> None:
        """The prompt must explicitly call out cycle avoidance — without
        this, the model can produce A → B and B → A on closely-coupled
        tasks (the v1.15.0 planner had no notion of dep ordering)."""
        prompt = _SYSTEM_PROMPT.lower()
        assert "cycle" in prompt or "cycles" in prompt
