#!/usr/bin/env python3
"""
Tests for the /do router's routing logic.

These tests validate that routing patterns correctly identify:
1. Which agent should handle a request
2. Which skill should be paired with the agent
3. When to trigger parallel routing
4. When to skip routing (trivial tasks)

Run with: python3 -m pytest hooks/tests/test_do_routing.py -v
Or directly: python3 hooks/tests/test_do_routing.py
"""

import re
from dataclasses import dataclass
from typing import Optional

# =============================================================================
# Routing Pattern Definitions (extracted from /do command)
# =============================================================================

# Domain agent triggers
AGENT_TRIGGERS = {
    "golang-general-engineer": {"go", "golang", ".go", "gofmt", "go mod", "goroutine", "channel"},
    "python-general-engineer": {"python", ".py", "pip", "pytest", "ruff", "mypy"},
    "typescript-frontend-engineer": {"typescript", ".ts", "react", "nextjs", "next.js"},
    "kubernetes-helm-engineer": {"kubernetes", "k8s", "helm", "kubectl", "pod", "deployment"},
    "database-engineer": {"database", "postgresql", "postgres", "sql", "schema", "migration"},
    "testing-automation-engineer": {"e2e", "playwright", "testing framework"},
    "reviewer-security": {"security review", "vulnerability", "vulnerabilities", "owasp"},
    "reviewer-business-logic": {"business logic", "domain review", "requirements"},
}

# Skill triggers
SKILL_TRIGGERS = {
    "systematic-debugging": {"debug", "fix bug", "investigate failure"},
    "test-driven-development": {"tdd", "test first", "red green refactor"},
    "systematic-code-review": {"review", "check code", "pr review"},
    "workflow-orchestrator": {"implement", "build feature"},
    "go-patterns": {"go test", "_test.go", "table-driven", "t.run", "goroutine", "channel", "sync.mutex", "waitgroup"},
}

# Trivial task patterns (should NOT route)
TRIVIAL_PATTERNS = [
    re.compile(r"^what\s+(is|are|does)", re.IGNORECASE),
    re.compile(r"^git\s+status", re.IGNORECASE),
    re.compile(r"^read\s+", re.IGNORECASE),
    re.compile(r"^ls\s+", re.IGNORECASE),
]


# =============================================================================
# Routing Logic (simplified version of /do)
# =============================================================================


@dataclass
class RoutingDecision:
    """Result of routing analysis."""

    agent: Optional[str]
    skill: Optional[str]
    is_trivial: bool
    parallel: bool
    reason: str


def find_agent(prompt: str) -> Optional[str]:
    """Find the best matching agent for a prompt."""
    prompt_lower = prompt.lower()

    for agent, triggers in AGENT_TRIGGERS.items():
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                return agent
    return None


def find_skill(prompt: str) -> Optional[str]:
    """Find the best matching skill for a prompt."""
    prompt_lower = prompt.lower()

    for skill, triggers in SKILL_TRIGGERS.items():
        for trigger in triggers:
            if trigger.lower() in prompt_lower:
                return skill
    return None


def is_trivial(prompt: str) -> bool:
    """Check if prompt is trivial and doesn't need routing."""
    return any(pattern.search(prompt) for pattern in TRIVIAL_PATTERNS)


def should_parallelize(prompt: str) -> bool:
    """Check if prompt suggests parallel agent dispatch."""
    indicators = [
        "3+ independent",
        "multiple failures",
        "in parallel",
        "comprehensive review",
    ]
    prompt_lower = prompt.lower()
    return any(ind in prompt_lower for ind in indicators)


def route(prompt: str) -> RoutingDecision:
    """Route a prompt to appropriate agent and skill."""
    if is_trivial(prompt):
        return RoutingDecision(agent=None, skill=None, is_trivial=True, parallel=False, reason="trivial task")

    agent = find_agent(prompt)
    skill = find_skill(prompt)
    parallel = should_parallelize(prompt)

    if not agent and not skill:
        return RoutingDecision(agent=None, skill=None, is_trivial=False, parallel=parallel, reason="no match found")

    return RoutingDecision(agent=agent, skill=skill, is_trivial=False, parallel=parallel, reason="routed")


# =============================================================================
# Tests: Agent Routing
# =============================================================================


def test_routes_go_to_golang_engineer():
    """Go-related prompts should route to golang-general-engineer."""
    prompts = [
        "implement a rate limiter in Go",
        "debug this Go test failure",
        "review my .go files",
        "add goroutine worker pool",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.agent == "golang-general-engineer", (
            f"Expected golang-general-engineer for '{prompt}', got {result.agent}"
        )


def test_routes_python_to_python_engineer():
    """Python-related prompts should route to python-general-engineer."""
    prompts = [
        "fix this Python bug",
        "add pytest tests",
        "run mypy on the codebase",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.agent == "python-general-engineer", (
            f"Expected python-general-engineer for '{prompt}', got {result.agent}"
        )


def test_routes_kubernetes_to_k8s_engineer():
    """Kubernetes prompts should route to kubernetes-helm-engineer."""
    prompts = [
        "update the kubernetes deployment",
        "fix the helm chart",
        "debug the pod crash",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.agent == "kubernetes-helm-engineer", (
            f"Expected kubernetes-helm-engineer for '{prompt}', got {result.agent}"
        )


def test_routes_security_review():
    """Security review prompts should route to reviewer-security."""
    prompts = [
        "security review this API",
        "check for vulnerabilities",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.agent == "reviewer-security", f"Expected reviewer-security for '{prompt}', got {result.agent}"


# =============================================================================
# Tests: Skill Routing
# =============================================================================


def test_routes_debug_to_debugging_skill():
    """Debug prompts should pair with systematic-debugging skill."""
    prompts = [
        "debug this test failure",
        "fix bug in the login flow",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.skill == "systematic-debugging", (
            f"Expected systematic-debugging for '{prompt}', got {result.skill}"
        )


def test_routes_tdd_to_tdd_skill():
    """TDD prompts should pair with test-driven-development skill."""
    prompts = [
        "use TDD to implement this",
        "test first approach",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.skill == "test-driven-development", (
            f"Expected test-driven-development for '{prompt}', got {result.skill}"
        )


def test_routes_go_test_to_go_patterns_skill():
    """Go test prompts should pair with go-patterns skill (forced)."""
    prompts = [
        "add table-driven tests",
        "write Go test for this function",
        "add t.Run subtests",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.skill == "go-patterns", f"Expected go-patterns for '{prompt}', got {result.skill}"


# =============================================================================
# Tests: Trivial Detection
# =============================================================================


def test_trivial_detection_fact_lookups():
    """Fact lookup questions should be trivial."""
    prompts = [
        "what is the syntax for Go channels?",
        "what are the SOLID principles?",
        "what does this error mean?",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert result.is_trivial, f"Expected trivial for '{prompt}'"
        assert result.agent is None
        assert result.skill is None


def test_trivial_detection_git_status():
    """git status should be trivial."""
    result = route("git status")
    assert result.is_trivial


def test_trivial_detection_read_file():
    """read file should be trivial."""
    result = route("read the README.md")
    assert result.is_trivial


def test_not_trivial_code_changes():
    """Code changes should NOT be trivial."""
    prompts = [
        "fix this Python bug",
        "add a new endpoint",
        "refactor the authentication",
    ]
    for prompt in prompts:
        result = route(prompt)
        assert not result.is_trivial, f"Expected non-trivial for '{prompt}'"


# =============================================================================
# Tests: Parallel Routing
# =============================================================================


def test_parallel_for_comprehensive_review():
    """Comprehensive review should trigger parallel routing."""
    result = route("do a comprehensive review of this PR")
    assert result.parallel, "Expected parallel for comprehensive review"


def test_parallel_for_multiple_failures():
    """Multiple failures should trigger parallel routing."""
    result = route("investigate these 3+ independent failures in parallel")
    assert result.parallel, "Expected parallel for multiple failures"


def test_no_parallel_for_single_task():
    """Single tasks should not trigger parallel routing."""
    result = route("fix this one bug")
    assert not result.parallel, "Expected no parallel for single task"


# =============================================================================
# Tests: Combined Routing
# =============================================================================


def test_go_debug_routes_correctly():
    """Go debugging should get both agent and skill."""
    result = route("debug this Go test failure")
    assert result.agent == "golang-general-engineer"
    assert result.skill == "systematic-debugging"
    assert not result.is_trivial


def test_python_tdd_routes_correctly():
    """Python TDD should get both agent and skill."""
    result = route("use TDD to implement this Python feature")
    assert result.agent == "python-general-engineer"
    assert result.skill == "test-driven-development"
    assert not result.is_trivial


def test_unknown_domain_no_agent():
    """Unknown domains should not get an agent."""
    result = route("do something with COBOL")
    assert result.agent is None
    # But it shouldn't be trivial
    assert not result.is_trivial


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all tests."""
    import sys

    print("=" * 60)
    print(" /do Routing Logic Tests")
    print("=" * 60)

    tests = [
        # Agent routing
        test_routes_go_to_golang_engineer,
        test_routes_python_to_python_engineer,
        test_routes_kubernetes_to_k8s_engineer,
        test_routes_security_review,
        # Skill routing
        test_routes_debug_to_debugging_skill,
        test_routes_tdd_to_tdd_skill,
        test_routes_go_test_to_go_patterns_skill,
        # Trivial detection
        test_trivial_detection_fact_lookups,
        test_trivial_detection_git_status,
        test_trivial_detection_read_file,
        test_not_trivial_code_changes,
        # Parallel routing
        test_parallel_for_comprehensive_review,
        test_parallel_for_multiple_failures,
        test_no_parallel_for_single_task,
        # Combined
        test_go_debug_routes_correctly,
        test_python_tdd_routes_correctly,
        test_unknown_domain_no_agent,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}: Unexpected error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f" Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
