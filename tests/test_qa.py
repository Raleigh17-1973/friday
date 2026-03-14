"""
QA Test Registry — integration tests.

Covers:
- Test case CRUD (create, read, update, deprecate, clone)
- Suite creation, rule-based generation, update
- Test run lifecycle (create, record results, complete)
- Bug report creation and update
- User story candidate creation
- Coverage gap analyzer logic
- Filtering and search
- Registry summary
- Template seeding
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from packages.qa.service import (
    QAService,
    KNOWN_FEATURE_AREAS,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def qa(tmp_path: Path) -> QAService:
    """Fresh QAService with a temporary database (templates seeded)."""
    return QAService(db_path=tmp_path / "test_qa.sqlite3")


@pytest.fixture
def qa_empty(tmp_path: Path) -> QAService:
    """QAService with no templates — just an empty DB."""
    svc = QAService.__new__(QAService)
    svc._db_path = tmp_path / "empty_qa.sqlite3"
    svc._db_path.parent.mkdir(parents=True, exist_ok=True)
    svc._init_db()
    return svc


# ─── Test Case CRUD ──────────────────────────────────────────────────────────


class TestTestCaseCRUD:
    def test_create_returns_structured_test_case(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(
            title="Basic smoke test",
            feature_area="chat",
            test_type="smoke",
            description="Verify chat returns a response",
            steps=["Open chat", "Send a message", "Verify response"],
            expected_result="Response received within 15 seconds",
            priority="critical",
            severity_if_fails="blocker",
            release_blocker=True,
            status="active",
            tags=["smoke", "core"],
        )
        assert tc.tc_id.startswith("tc-")
        assert tc.title == "Basic smoke test"
        assert tc.feature_area == "chat"
        assert tc.test_type == "smoke"
        assert tc.priority == "critical"
        assert tc.release_blocker is True
        assert tc.status == "active"
        assert tc.steps == ["Open chat", "Send a message", "Verify response"]
        assert "smoke" in tc.tags

    def test_get_returns_same_data(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(
            title="Get test", feature_area="okrs", test_type="regression"
        )
        fetched = qa_empty.get_test_case(tc.tc_id)
        assert fetched is not None
        assert fetched.tc_id == tc.tc_id
        assert fetched.title == "Get test"

    def test_get_nonexistent_returns_none(self, qa_empty: QAService):
        assert qa_empty.get_test_case("tc-nonexistent") is None

    def test_update_changes_fields(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(
            title="Old title", feature_area="workspaces", test_type="smoke", status="draft"
        )
        updated = qa_empty.update_test_case(tc.tc_id, {
            "title": "New title",
            "status": "active",
            "priority": "high",
        })
        assert updated is not None
        assert updated.title == "New title"
        assert updated.status == "active"
        assert updated.priority == "high"
        # Persisted
        fetched = qa_empty.get_test_case(tc.tc_id)
        assert fetched is not None
        assert fetched.title == "New title"

    def test_update_nonexistent_returns_none(self, qa_empty: QAService):
        result = qa_empty.update_test_case("tc-nonexistent", {"title": "x"})
        assert result is None

    def test_deprecate_sets_status(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(
            title="Active test", feature_area="chat", test_type="regression", status="active"
        )
        ok = qa_empty.deprecate_test_case(tc.tc_id)
        assert ok is True
        fetched = qa_empty.get_test_case(tc.tc_id)
        assert fetched is not None
        assert fetched.status == "deprecated"

    def test_deprecate_nonexistent_returns_false(self, qa_empty: QAService):
        assert qa_empty.deprecate_test_case("tc-nonexistent") is False

    def test_clone_creates_new_record(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(
            title="Original", feature_area="okrs", test_type="deep",
            description="Original description",
            steps=["Step 1", "Step 2"],
            tags=["deep"],
            status="active",
        )
        cloned = qa_empty.clone_test_case(tc.tc_id)
        assert cloned is not None
        assert cloned.tc_id != tc.tc_id
        assert "[Clone]" in cloned.title
        assert cloned.steps == tc.steps
        assert cloned.tags == tc.tags
        assert cloned.status == "draft"  # Clone starts as draft

    def test_clone_with_custom_title(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(title="Original", feature_area="chat", test_type="smoke")
        cloned = qa_empty.clone_test_case(tc.tc_id, new_title="My Custom Clone")
        assert cloned is not None
        assert cloned.title == "My Custom Clone"

    def test_clone_nonexistent_returns_none(self, qa_empty: QAService):
        assert qa_empty.clone_test_case("tc-nonexistent") is None


# ─── Filtering and Search ────────────────────────────────────────────────────


class TestFiltering:
    def _seed(self, svc: QAService):
        svc.create_test_case(title="Chat smoke", feature_area="chat", test_type="smoke", status="active", priority="critical")
        svc.create_test_case(title="Chat regression", feature_area="chat", test_type="regression", status="active", priority="medium")
        svc.create_test_case(title="OKR smoke", feature_area="okrs", test_type="smoke", status="active", priority="high")
        svc.create_test_case(title="Draft test", feature_area="chat", test_type="deep", status="draft", priority="low")
        svc.create_test_case(title="Blocker test", feature_area="workspaces", test_type="regression", status="active", priority="critical", release_blocker=True)

    def test_filter_by_feature_area(self, qa_empty: QAService):
        self._seed(qa_empty)
        chat_tests = qa_empty.list_test_cases(feature_area="chat")
        assert all(t.feature_area == "chat" for t in chat_tests)
        assert len(chat_tests) == 3

    def test_filter_by_test_type(self, qa_empty: QAService):
        self._seed(qa_empty)
        smoke = qa_empty.list_test_cases(test_type="smoke")
        assert all(t.test_type == "smoke" for t in smoke)
        assert len(smoke) == 2

    def test_filter_by_status(self, qa_empty: QAService):
        self._seed(qa_empty)
        drafts = qa_empty.list_test_cases(status="draft")
        assert all(t.status == "draft" for t in drafts)
        assert len(drafts) == 1

    def test_filter_by_priority(self, qa_empty: QAService):
        self._seed(qa_empty)
        critical = qa_empty.list_test_cases(priority="critical")
        assert all(t.priority == "critical" for t in critical)
        assert len(critical) == 2

    def test_filter_release_blocker(self, qa_empty: QAService):
        self._seed(qa_empty)
        blockers = qa_empty.list_test_cases(release_blocker=True)
        assert all(t.release_blocker for t in blockers)
        assert len(blockers) == 1

    def test_search_by_title(self, qa_empty: QAService):
        self._seed(qa_empty)
        results = qa_empty.list_test_cases(search="smoke")
        assert len(results) >= 2

    def test_combined_filters(self, qa_empty: QAService):
        self._seed(qa_empty)
        results = qa_empty.list_test_cases(feature_area="chat", status="active")
        assert all(t.feature_area == "chat" and t.status == "active" for t in results)
        assert len(results) == 2

    def test_results_ordered_by_priority(self, qa_empty: QAService):
        self._seed(qa_empty)
        all_active = qa_empty.list_test_cases(status="active")
        priorities = [t.priority for t in all_active]
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        # Verify critical comes before medium
        critical_idx = next((i for i, p in enumerate(priorities) if p == "critical"), None)
        medium_idx = next((i for i, p in enumerate(priorities) if p == "medium"), None)
        if critical_idx is not None and medium_idx is not None:
            assert critical_idx < medium_idx


# ─── Suites ──────────────────────────────────────────────────────────────────


class TestSuites:
    def test_create_manual_suite(self, qa_empty: QAService):
        suite = qa_empty.create_suite(
            name="Smoke Suite",
            suite_type="smoke",
            description="All smoke tests",
            feature_areas=["chat", "okrs"],
        )
        assert suite.suite_id.startswith("suite-")
        assert suite.name == "Smoke Suite"
        assert suite.suite_type == "smoke"
        assert "chat" in suite.feature_areas

    def test_get_suite(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Test Suite", suite_type="regression")
        fetched = qa_empty.get_suite(suite.suite_id)
        assert fetched is not None
        assert fetched.name == "Test Suite"

    def test_update_suite(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Old Name", suite_type="custom")
        updated = qa_empty.update_suite(suite.suite_id, {"name": "New Name", "status": "archived"})
        assert updated is not None
        assert updated.name == "New Name"
        assert updated.status == "archived"

    def test_generate_suite_from_rules_feature_area(self, qa_empty: QAService):
        qa_empty.create_test_case(title="Chat smoke 1", feature_area="chat", test_type="smoke", status="active")
        qa_empty.create_test_case(title="Chat regression", feature_area="chat", test_type="regression", status="active")
        qa_empty.create_test_case(title="OKR smoke", feature_area="okrs", test_type="smoke", status="active")

        suite = qa_empty.generate_suite_from_rules(
            name="Chat Suite",
            rule="feature_area=chat",
        )
        assert suite.suite_type == "feature_specific"
        assert len(suite.test_case_ids) == 2
        assert "chat" in suite.feature_areas

    def test_generate_suite_smoke_type(self, qa_empty: QAService):
        qa_empty.create_test_case(title="Smoke A", feature_area="chat", test_type="smoke", status="active")
        qa_empty.create_test_case(title="Smoke B", feature_area="okrs", test_type="smoke", status="active")
        qa_empty.create_test_case(title="Regression C", feature_area="chat", test_type="regression", status="active")

        suite = qa_empty.generate_suite_from_rules(name="All Smoke", rule="test_type=smoke")
        assert suite.suite_type == "smoke"
        assert len(suite.test_case_ids) == 2

    def test_generate_release_blocker_suite(self, qa_empty: QAService):
        qa_empty.create_test_case(title="Blocker A", feature_area="chat", test_type="smoke", status="active", release_blocker=True)
        qa_empty.create_test_case(title="Non-blocker", feature_area="chat", test_type="regression", status="active", release_blocker=False)

        suite = qa_empty.generate_suite_from_rules(name="RC Suite", rule="release_blocker=true")
        assert suite.suite_type == "release_candidate"
        assert len(suite.test_case_ids) == 1

    def test_list_suites(self, qa_empty: QAService):
        qa_empty.create_suite(name="Suite A", suite_type="smoke")
        qa_empty.create_suite(name="Suite B", suite_type="regression")
        suites = qa_empty.list_suites()
        assert len(suites) == 2

    def test_add_test_cases_to_suite(self, qa_empty: QAService):
        tc = qa_empty.create_test_case(title="Test", feature_area="chat", test_type="smoke")
        suite = qa_empty.create_suite(name="Suite", suite_type="custom")
        updated = qa_empty.update_suite(suite.suite_id, {"test_case_ids": [tc.tc_id]})
        assert updated is not None
        assert tc.tc_id in updated.test_case_ids


# ─── Test Runs ───────────────────────────────────────────────────────────────


class TestRuns:
    def test_create_run(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Test Suite", suite_type="smoke")
        tc = qa_empty.create_test_case(title="T1", feature_area="chat", test_type="smoke")
        qa_empty.update_suite(suite.suite_id, {"test_case_ids": [tc.tc_id]})

        run = qa_empty.create_test_run(
            suite_id=suite.suite_id,
            title="Sprint 1 Smoke Run",
            environment="staging",
        )
        assert run.run_id.startswith("run-")
        assert run.status == "in_progress"
        assert run.suite_id == suite.suite_id

    def test_store_results(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Suite", suite_type="smoke")
        run = qa_empty.create_test_run(suite_id=suite.suite_id, title="Run")

        result = qa_empty.store_test_result(
            run_id=run.run_id,
            test_case_id="tc-abc123",
            result="pass",
            tester="qa-specialist",
        )
        assert result.result_id.startswith("res-")
        assert result.result == "pass"

    def test_fail_result_with_regression_flag(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Suite", suite_type="regression")
        run = qa_empty.create_test_run(suite_id=suite.suite_id, title="Run")

        result = qa_empty.store_test_result(
            run_id=run.run_id,
            test_case_id="tc-fail",
            result="fail",
            findings="Button not clickable",
            reproduction_notes="Step 3 fails consistently",
            severity="major",
            should_become_regression=True,
        )
        assert result.result == "fail"
        assert result.should_become_regression is True
        assert result.findings == "Button not clickable"

    def test_complete_run_updates_counts(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Suite", suite_type="smoke")
        run = qa_empty.create_test_run(suite_id=suite.suite_id, title="Run")

        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-1", result="pass")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-2", result="pass")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-3", result="fail")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-4", result="blocked")

        completed = qa_empty.complete_test_run(run.run_id, summary="Sprint 1 done")
        assert completed is not None
        assert completed.status == "completed"
        assert completed.pass_count == 2
        assert completed.fail_count == 1
        assert completed.blocked_count == 1
        assert completed.summary == "Sprint 1 done"

    def test_list_results_for_run(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Suite", suite_type="smoke")
        run = qa_empty.create_test_run(suite_id=suite.suite_id, title="Run")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-1", result="pass")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-2", result="fail")

        results = qa_empty.list_test_results(run.run_id)
        assert len(results) == 2
        assert {r.result for r in results} == {"pass", "fail"}

    def test_regression_candidates_query(self, qa_empty: QAService):
        suite = qa_empty.create_suite(name="Suite", suite_type="regression")
        run = qa_empty.create_test_run(suite_id=suite.suite_id, title="Run")
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-1", result="fail", should_become_regression=True)
        qa_empty.store_test_result(run_id=run.run_id, test_case_id="tc-2", result="pass", should_become_regression=False)

        candidates = qa_empty.get_regression_candidates()
        assert len(candidates) == 1
        assert candidates[0].test_case_id == "tc-1"


# ─── Bug Reports ─────────────────────────────────────────────────────────────


class TestBugReports:
    def test_create_bug_report(self, qa_empty: QAService):
        bug = qa_empty.create_bug_report(
            title="Login button invisible",
            severity="critical",
            category="visual",
            area="ui_consistency",
            repro_steps=["Open login page", "Observe button area"],
            expected_result="Button visible",
            actual_result="Button not visible — white on white",
            impact="Users cannot log in",
            release_blocker=True,
        )
        assert bug.bug_id.startswith("bug-")
        assert bug.severity == "critical"
        assert bug.release_blocker is True
        assert bug.status == "open"

    def test_update_bug_status(self, qa_empty: QAService):
        bug = qa_empty.create_bug_report(title="Test bug", area="chat")
        updated = qa_empty.update_bug_report(bug.bug_id, {"status": "resolved"})
        assert updated is not None
        assert updated.status == "resolved"

    def test_link_test_cases_to_bug(self, qa_empty: QAService):
        bug = qa_empty.create_bug_report(title="Linked bug", area="chat")
        qa_empty.update_bug_report(bug.bug_id, {"linked_test_case_ids": ["tc-abc", "tc-def"]})
        fetched = qa_empty.get_bug_report(bug.bug_id)
        assert fetched is not None
        assert "tc-abc" in fetched.linked_test_case_ids

    def test_list_bug_reports(self, qa_empty: QAService):
        bug1 = qa_empty.create_bug_report(title="Bug 1", area="chat")
        bug2 = qa_empty.create_bug_report(title="Bug 2", area="okrs")
        qa_empty.update_bug_report(bug2.bug_id, {"status": "resolved"})
        all_bugs = qa_empty.list_bug_reports()
        assert len(all_bugs) == 2

    def test_filter_by_status(self, qa_empty: QAService):
        qa_empty.create_bug_report(title="Open bug", area="chat")
        qa_empty.create_bug_report(title="Resolved bug", area="chat")
        qa_empty.update_bug_report(qa_empty.list_bug_reports()[-1].bug_id, {"status": "resolved"})

        open_bugs = qa_empty.list_bug_reports(status="open")
        assert all(b.status == "open" for b in open_bugs)


# ─── User Story Candidates ───────────────────────────────────────────────────


class TestUserStoryCandidates:
    def test_create_story_candidate(self, qa_empty: QAService):
        story = qa_empty.create_user_story_candidate(
            title="As a QA specialist, I can filter tests by feature area",
            user_story="As a QA specialist, I want to filter test cases by feature area so I can focus on specific areas during a sprint.",
            acceptance_criteria=[
                "Filter dropdown shows all 13 feature areas",
                "Selecting an area only shows tests for that area",
                "Filter persists while navigating",
            ],
            priority="high",
        )
        assert story.story_id.startswith("story-")
        assert story.status == "candidate"
        assert len(story.acceptance_criteria) == 3

    def test_list_candidates(self, qa_empty: QAService):
        qa_empty.create_user_story_candidate(title="Story A")
        qa_empty.create_user_story_candidate(title="Story B")
        stories = qa_empty.list_user_story_candidates()
        assert len(stories) == 2


# ─── Coverage Gap Analyzer ───────────────────────────────────────────────────


class TestCoverageGapAnalyzer:
    def test_empty_db_produces_critical_gaps_for_all_areas(self, qa_empty: QAService):
        report = qa_empty.analyze_coverage_gaps()
        assert report.total_active_tests == 0
        critical_gaps = [g for g in report.gaps if g.severity == "critical"]
        # All 13 known areas should be critical
        assert len(critical_gaps) == len(KNOWN_FEATURE_AREAS)
        assert report.risk_summary["critical"] == len(KNOWN_FEATURE_AREAS)

    def test_partial_coverage_produces_warnings(self, qa_empty: QAService):
        # Add only a smoke test for chat — missing regression
        qa_empty.create_test_case(title="Chat smoke", feature_area="chat", test_type="smoke", status="active")
        report = qa_empty.analyze_coverage_gaps()
        chat_gap = next((g for g in report.gaps if g.area == "chat"), None)
        assert chat_gap is not None
        assert chat_gap.severity == "warning"
        assert "regression" in chat_gap.missing_types

    def test_full_coverage_produces_info_or_no_gap(self, qa_empty: QAService):
        # Add smoke + regression for chat — should either produce info or no gap
        qa_empty.create_test_case(title="Chat smoke", feature_area="chat", test_type="smoke", status="active")
        qa_empty.create_test_case(title="Chat regression", feature_area="chat", test_type="regression", status="active")
        qa_empty.create_test_case(title="Chat deep", feature_area="chat", test_type="deep", status="active")
        report = qa_empty.analyze_coverage_gaps()
        chat_gap = next((g for g in report.gaps if g.area == "chat"), None)
        # With smoke + regression + deep (3 tests), should be no gap or info only
        if chat_gap:
            assert chat_gap.severity == "info"

    def test_unlinked_bugs_reported(self, qa_empty: QAService):
        bug1 = qa_empty.create_bug_report(title="Bug 1", area="chat")
        bug2 = qa_empty.create_bug_report(title="Bug 2", area="okrs")
        # bug2 gets a linked test case
        qa_empty.update_bug_report(bug2.bug_id, {"linked_test_case_ids": ["tc-abc"]})

        report = qa_empty.analyze_coverage_gaps()
        assert bug1.bug_id in report.unlinked_bugs
        assert bug2.bug_id not in report.unlinked_bugs

    def test_deprecated_tests_not_counted_as_active(self, qa_empty: QAService):
        qa_empty.create_test_case(title="Deprecated", feature_area="chat", test_type="smoke", status="deprecated")
        report = qa_empty.analyze_coverage_gaps()
        assert report.total_active_tests == 0

    def test_report_contains_recommendations(self, qa_empty: QAService):
        report = qa_empty.analyze_coverage_gaps()
        assert len(report.recommendations) > 0


# ─── Registry Summary ────────────────────────────────────────────────────────


class TestRegistrySummary:
    def test_summary_reflects_seeded_templates(self, qa: QAService):
        """Seeded QAService should have 30+ tests across multiple areas."""
        summary = qa.get_registry_summary()
        assert summary["total"] >= 30
        assert summary["active"] >= 30
        assert summary["coverage_areas"] >= 10

    def test_summary_counts_by_type(self, qa: QAService):
        summary = qa.get_registry_summary()
        # Should have smoke and regression tests at minimum
        assert summary["by_type"].get("smoke", 0) >= 1
        assert summary["by_type"].get("regression", 0) >= 1

    def test_summary_by_area(self, qa: QAService):
        summary = qa.get_registry_summary()
        # All major areas should have at least 1 test
        for area in ["chat", "okrs", "workspaces", "approvals"]:
            assert summary["by_area"].get(area, 0) >= 1

    def test_summary_release_blockers(self, qa: QAService):
        summary = qa.get_registry_summary()
        # Templates include multiple release blockers
        assert summary["release_blockers"] >= 5

    def test_summary_recent_tests(self, qa: QAService):
        summary = qa.get_registry_summary()
        assert len(summary["recent_tests"]) <= 5
        for t in summary["recent_tests"]:
            assert "tc_id" in t
            assert "title" in t


# ─── Template Seeding ────────────────────────────────────────────────────────


class TestTemplateSeed:
    def test_templates_seeded_on_first_run(self, qa: QAService):
        """Fresh QAService with templates should have 30+ active tests."""
        tests = qa.list_test_cases(status="active")
        assert len(tests) >= 30

    def test_seed_not_duplicated_on_second_run(self, qa: QAService):
        """Calling _maybe_seed_templates again should not duplicate data."""
        count_before = len(qa.list_test_cases())
        qa._maybe_seed_templates()  # Should be a no-op
        count_after = len(qa.list_test_cases())
        assert count_before == count_after

    def test_templates_cover_all_major_areas(self, qa: QAService):
        areas_covered = {t.feature_area for t in qa.list_test_cases(status="active")}
        required = {"chat", "agent_orchestration", "documents", "okrs",
                    "workspaces", "approvals", "permissions", "memory"}
        for area in required:
            assert area in areas_covered, f"Missing coverage for {area}"

    def test_templates_include_smoke_and_regression_types(self, qa: QAService):
        types = {t.test_type for t in qa.list_test_cases(status="active")}
        assert "smoke" in types
        assert "regression" in types
        assert "safety" in types

    def test_templates_include_release_blockers(self, qa: QAService):
        blockers = qa.list_test_cases(release_blocker=True, status="active")
        assert len(blockers) >= 5


# ─── End-to-End: QA Specialist Workflow ─────────────────────────────────────


class TestQASpecialistWorkflow:
    def test_full_regression_workflow(self, qa_empty: QAService):
        """
        Simulate: QA specialist creates tests → suite → run → records fail → flags regression.
        """
        # 1. Create test cases
        tc1 = qa_empty.create_test_case(
            title="Workspace creation", feature_area="workspaces",
            test_type="smoke", status="active", priority="critical",
            steps=["Navigate to /workspaces", "Click New", "Fill form", "Submit"],
            expected_result="Workspace appears in list",
        )
        tc2 = qa_empty.create_test_case(
            title="OKR list loads", feature_area="okrs",
            test_type="smoke", status="active", priority="critical",
        )

        # 2. Create a suite with both tests
        suite = qa_empty.create_suite(
            name="Release Smoke", suite_type="smoke",
            test_case_ids=[tc1.tc_id, tc2.tc_id],
        )
        assert len(suite.test_case_ids) == 2

        # 3. Start a run
        run = qa_empty.create_test_run(
            suite_id=suite.suite_id, title="Sprint 5 RC", environment="staging"
        )
        assert run.status == "in_progress"

        # 4. Record results — tc1 passes, tc2 fails
        qa_empty.store_test_result(run_id=run.run_id, test_case_id=tc1.tc_id, result="pass", tester="qa-specialist")
        qa_empty.store_test_result(
            run_id=run.run_id, test_case_id=tc2.tc_id, result="fail",
            findings="OKR list shows 0 despite data in DB",
            reproduction_notes="Navigate to /okrs — 'No OKRs yet' shown even with data",
            severity="major",
            should_become_regression=True,
        )

        # 5. Complete the run
        completed = qa_empty.complete_test_run(run.run_id, summary="Smoke mostly passing, 1 regression found")
        assert completed is not None
        assert completed.pass_count == 1
        assert completed.fail_count == 1

        # 6. Create a bug for the failing test
        bug = qa_empty.create_bug_report(
            title="OKR list shows 0 despite data existing",
            severity="major", area="okrs",
            repro_steps=["Navigate to /okrs", "Observe '0 Total Objectives'"],
            expected_result="OKRs listed",
            actual_result="Empty list despite data in DB",
            linked_test_case_ids=[tc2.tc_id],
            linked_run_ids=[run.run_id],
        )
        assert bug.bug_id.startswith("bug-")
        assert tc2.tc_id in bug.linked_test_case_ids

        # 7. Regression candidates should include tc2
        candidates = qa_empty.get_regression_candidates()
        assert any(c.test_case_id == tc2.tc_id for c in candidates)

    def test_generate_pre_release_suite(self, qa_empty: QAService):
        """Generate a release candidate suite from active blockers."""
        qa_empty.create_test_case(title="Blocker 1", feature_area="chat", test_type="smoke", status="active", release_blocker=True)
        qa_empty.create_test_case(title="Blocker 2", feature_area="approvals", test_type="regression", status="active", release_blocker=True)
        qa_empty.create_test_case(title="Non-blocker", feature_area="chat", test_type="deep", status="active", release_blocker=False)

        suite = qa_empty.generate_suite_from_rules(
            name="Pre-Release Suite",
            rule="release_blocker=true,status=active",
        )
        assert len(suite.test_case_ids) == 2
        assert suite.suite_type == "release_candidate"

    def test_deprecate_obsolete_tests(self, qa_empty: QAService):
        """Deprecate tests for a removed feature."""
        tc1 = qa_empty.create_test_case(title="Old OKR layout test", feature_area="okrs", test_type="ux", status="active")
        tc2 = qa_empty.create_test_case(title="New OKR test", feature_area="okrs", test_type="ux", status="active")

        # Deprecate old test
        qa_empty.deprecate_test_case(tc1.tc_id)

        active_okr = qa_empty.list_test_cases(feature_area="okrs", status="active")
        deprecated_okr = qa_empty.list_test_cases(feature_area="okrs", status="deprecated")

        assert len(active_okr) == 1
        assert active_okr[0].tc_id == tc2.tc_id
        assert len(deprecated_okr) == 1
        assert deprecated_okr[0].tc_id == tc1.tc_id
