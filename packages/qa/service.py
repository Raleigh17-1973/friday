from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


# ─── Dataclasses ─────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    tc_id: str
    org_id: str
    title: str
    feature_area: str
    subfeature: str
    description: str
    preconditions: str
    steps: list[str]
    expected_result: str
    priority: str               # critical | high | medium | low
    severity_if_fails: str      # blocker | critical | major | minor | trivial
    test_type: str              # smoke | regression | deep | edge | ux | safety | data_integrity | orchestration | document_quality
    applies_to_agents: list[str]
    applies_to_ui_surfaces: list[str]
    release_blocker: bool
    status: str                 # draft | active | deprecated
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str
    linked_user_story_ids: list[str]
    linked_bug_ids: list[str]
    linked_workspace_ids: list[str]
    notes: str
    tags: list[str]


@dataclass
class TestSuite:
    suite_id: str
    org_id: str
    name: str
    description: str
    suite_type: str             # smoke | regression | feature_specific | release_candidate | agent_specific | ui_consistency | safety | custom
    feature_areas: list[str]
    test_case_ids: list[str]
    generated_by_rule: str      # e.g. "feature_area=workspaces,test_type=smoke"
    owner: str
    created_at: str
    updated_at: str
    status: str                 # active | archived


@dataclass
class TestRun:
    run_id: str
    org_id: str
    suite_id: str
    title: str
    environment: str            # development | staging | production
    triggered_by: str
    run_type: str               # manual | scheduled | ci
    started_at: str
    completed_at: str | None
    status: str                 # in_progress | completed | aborted
    summary: str
    notes: str
    pass_count: int
    fail_count: int
    blocked_count: int
    not_run_count: int


@dataclass
class TestResult:
    result_id: str
    run_id: str
    test_case_id: str
    result: str                 # pass | fail | blocked | not_run
    severity: str | None
    findings: str
    reproduction_notes: str
    linked_bug_id: str | None
    should_become_regression: bool
    tester: str
    timestamp: str


@dataclass
class BugReport:
    bug_id: str
    org_id: str
    title: str
    severity: str               # blocker | critical | major | minor | trivial
    category: str               # functional | visual | performance | data | security | ux
    area: str
    repro_steps: list[str]
    expected_result: str
    actual_result: str
    impact: str
    recommended_fix: str
    release_blocker: bool
    linked_test_case_ids: list[str]
    linked_run_ids: list[str]
    status: str                 # open | in_progress | resolved | wont_fix | duplicate
    owner: str
    created_at: str
    updated_at: str


@dataclass
class UserStoryCandidate:
    story_id: str
    org_id: str
    title: str
    user_story: str
    context: str
    acceptance_criteria: list[str]
    priority: str
    dependencies: list[str]
    source_test_case_id: str | None
    source_run_id: str | None
    status: str                 # candidate | promoted | rejected
    created_at: str
    updated_at: str


@dataclass
class CoverageGap:
    area: str
    test_count: int
    severity: str               # critical | warning | info
    missing_types: list[str]
    recommendation: str


@dataclass
class CoverageReport:
    generated_at: str
    total_active_tests: int
    coverage_by_area: dict[str, int]
    gaps: list[CoverageGap]
    unlinked_bugs: list[str]     # bug_ids with no linked test cases
    under_tested_agents: list[str]
    recommendations: list[str]
    risk_summary: dict[str, int]  # critical / warning / info counts


# ─── QA Service ──────────────────────────────────────────────────────────────

# Feature areas the system tracks coverage for
KNOWN_FEATURE_AREAS = [
    "chat",
    "agent_orchestration",
    "documents",
    "okrs",
    "workspaces",
    "navigation",
    "approvals",
    "ui_consistency",
    "provenance",
    "permissions",
    "memory",
    "analytics",
    "processes",
]

REQUIRED_TEST_TYPES_PER_AREA = {"smoke", "regression"}

VALID_TEST_TYPES = {
    "smoke", "regression", "deep", "edge", "ux",
    "safety", "data_integrity", "orchestration", "document_quality",
}

VALID_STATUSES = {"draft", "active", "deprecated"}
VALID_SUITE_TYPES = {
    "smoke", "regression", "feature_specific", "release_candidate",
    "agent_specific", "ui_consistency", "safety", "custom",
}
VALID_PRIORITIES = {"critical", "high", "medium", "low"}
VALID_SEVERITIES = {"blocker", "critical", "major", "minor", "trivial"}
VALID_RESULTS = {"pass", "fail", "blocked", "not_run"}


def _now() -> str:
    return datetime.utcnow().isoformat()


def _j(v: Any) -> str:
    return json.dumps(v)


def _p(v: str) -> Any:
    try:
        return json.loads(v)
    except Exception:
        return v


class QAService:
    """
    Internal QA Test Registry and Suite Manager.

    Provides structured test case management, suite assembly, test run tracking,
    bug linkage, coverage gap analysis, and default templates for all Friday
    feature areas.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/friday_qa.sqlite3")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._maybe_seed_templates()

    # ─── Schema Init ─────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS qa_test_cases (
                    tc_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    feature_area TEXT NOT NULL,
                    subfeature TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    preconditions TEXT NOT NULL DEFAULT '',
                    steps TEXT NOT NULL DEFAULT '[]',
                    expected_result TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    severity_if_fails TEXT NOT NULL DEFAULT 'major',
                    test_type TEXT NOT NULL DEFAULT 'regression',
                    applies_to_agents TEXT NOT NULL DEFAULT '[]',
                    applies_to_ui_surfaces TEXT NOT NULL DEFAULT '[]',
                    release_blocker INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_by TEXT NOT NULL DEFAULT 'system',
                    updated_by TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    linked_user_story_ids TEXT NOT NULL DEFAULT '[]',
                    linked_bug_ids TEXT NOT NULL DEFAULT '[]',
                    linked_workspace_ids TEXT NOT NULL DEFAULT '[]',
                    notes TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS qa_test_suites (
                    suite_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT 'default',
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    suite_type TEXT NOT NULL DEFAULT 'custom',
                    feature_areas TEXT NOT NULL DEFAULT '[]',
                    test_case_ids TEXT NOT NULL DEFAULT '[]',
                    generated_by_rule TEXT NOT NULL DEFAULT '',
                    owner TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS qa_test_runs (
                    run_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT 'default',
                    suite_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    environment TEXT NOT NULL DEFAULT 'development',
                    triggered_by TEXT NOT NULL DEFAULT 'manual',
                    run_type TEXT NOT NULL DEFAULT 'manual',
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL DEFAULT 'in_progress',
                    summary TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    pass_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    blocked_count INTEGER NOT NULL DEFAULT 0,
                    not_run_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS qa_test_results (
                    result_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    test_case_id TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT 'not_run',
                    severity TEXT,
                    findings TEXT NOT NULL DEFAULT '',
                    reproduction_notes TEXT NOT NULL DEFAULT '',
                    linked_bug_id TEXT,
                    should_become_regression INTEGER NOT NULL DEFAULT 0,
                    tester TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qa_bug_reports (
                    bug_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'major',
                    category TEXT NOT NULL DEFAULT 'functional',
                    area TEXT NOT NULL DEFAULT '',
                    repro_steps TEXT NOT NULL DEFAULT '[]',
                    expected_result TEXT NOT NULL DEFAULT '',
                    actual_result TEXT NOT NULL DEFAULT '',
                    impact TEXT NOT NULL DEFAULT '',
                    recommended_fix TEXT NOT NULL DEFAULT '',
                    release_blocker INTEGER NOT NULL DEFAULT 0,
                    linked_test_case_ids TEXT NOT NULL DEFAULT '[]',
                    linked_run_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'open',
                    owner TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qa_user_story_candidates (
                    story_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL,
                    user_story TEXT NOT NULL DEFAULT '',
                    context TEXT NOT NULL DEFAULT '',
                    acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                    priority TEXT NOT NULL DEFAULT 'medium',
                    dependencies TEXT NOT NULL DEFAULT '[]',
                    source_test_case_id TEXT,
                    source_run_id TEXT,
                    status TEXT NOT NULL DEFAULT 'candidate',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qa_seed_version (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

    # ─── Row Mappers ─────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_tc(row: tuple) -> TestCase:
        return TestCase(
            tc_id=row[0], org_id=row[1], title=row[2], feature_area=row[3],
            subfeature=row[4], description=row[5], preconditions=row[6],
            steps=_p(row[7]), expected_result=row[8], priority=row[9],
            severity_if_fails=row[10], test_type=row[11],
            applies_to_agents=_p(row[12]), applies_to_ui_surfaces=_p(row[13]),
            release_blocker=bool(row[14]), status=row[15],
            created_by=row[16], updated_by=row[17],
            created_at=row[18], updated_at=row[19],
            linked_user_story_ids=_p(row[20]),
            linked_bug_ids=_p(row[21]),
            linked_workspace_ids=_p(row[22]),
            notes=row[23], tags=_p(row[24]),
        )

    @staticmethod
    def _row_to_suite(row: tuple) -> TestSuite:
        return TestSuite(
            suite_id=row[0], org_id=row[1], name=row[2], description=row[3],
            suite_type=row[4], feature_areas=_p(row[5]),
            test_case_ids=_p(row[6]), generated_by_rule=row[7],
            owner=row[8], created_at=row[9], updated_at=row[10],
            status=row[11],
        )

    @staticmethod
    def _row_to_run(row: tuple) -> TestRun:
        return TestRun(
            run_id=row[0], org_id=row[1], suite_id=row[2], title=row[3],
            environment=row[4], triggered_by=row[5], run_type=row[6],
            started_at=row[7], completed_at=row[8], status=row[9],
            summary=row[10], notes=row[11], pass_count=row[12],
            fail_count=row[13], blocked_count=row[14], not_run_count=row[15],
        )

    @staticmethod
    def _row_to_result(row: tuple) -> TestResult:
        return TestResult(
            result_id=row[0], run_id=row[1], test_case_id=row[2],
            result=row[3], severity=row[4], findings=row[5],
            reproduction_notes=row[6], linked_bug_id=row[7],
            should_become_regression=bool(row[8]), tester=row[9],
            timestamp=row[10],
        )

    @staticmethod
    def _row_to_bug(row: tuple) -> BugReport:
        return BugReport(
            bug_id=row[0], org_id=row[1], title=row[2], severity=row[3],
            category=row[4], area=row[5], repro_steps=_p(row[6]),
            expected_result=row[7], actual_result=row[8], impact=row[9],
            recommended_fix=row[10], release_blocker=bool(row[11]),
            linked_test_case_ids=_p(row[12]), linked_run_ids=_p(row[13]),
            status=row[14], owner=row[15], created_at=row[16],
            updated_at=row[17],
        )

    @staticmethod
    def _row_to_story(row: tuple) -> UserStoryCandidate:
        return UserStoryCandidate(
            story_id=row[0], org_id=row[1], title=row[2], user_story=row[3],
            context=row[4], acceptance_criteria=_p(row[5]), priority=row[6],
            dependencies=_p(row[7]), source_test_case_id=row[8],
            source_run_id=row[9], status=row[10],
            created_at=row[11], updated_at=row[12],
        )

    # ─── Test Cases ──────────────────────────────────────────────────────────

    def create_test_case(
        self, *,
        title: str,
        feature_area: str,
        test_type: str,
        org_id: str = "default",
        subfeature: str = "",
        description: str = "",
        preconditions: str = "",
        steps: list[str] | None = None,
        expected_result: str = "",
        priority: str = "medium",
        severity_if_fails: str = "major",
        applies_to_agents: list[str] | None = None,
        applies_to_ui_surfaces: list[str] | None = None,
        release_blocker: bool = False,
        status: str = "draft",
        created_by: str = "system",
        linked_user_story_ids: list[str] | None = None,
        linked_bug_ids: list[str] | None = None,
        linked_workspace_ids: list[str] | None = None,
        notes: str = "",
        tags: list[str] | None = None,
    ) -> TestCase:
        tc_id = f"tc-{uuid4().hex[:12]}"
        now = _now()
        tc = TestCase(
            tc_id=tc_id, org_id=org_id, title=title, feature_area=feature_area,
            subfeature=subfeature, description=description,
            preconditions=preconditions, steps=steps or [],
            expected_result=expected_result, priority=priority,
            severity_if_fails=severity_if_fails, test_type=test_type,
            applies_to_agents=applies_to_agents or [],
            applies_to_ui_surfaces=applies_to_ui_surfaces or [],
            release_blocker=release_blocker, status=status,
            created_by=created_by, updated_by=created_by,
            created_at=now, updated_at=now,
            linked_user_story_ids=linked_user_story_ids or [],
            linked_bug_ids=linked_bug_ids or [],
            linked_workspace_ids=linked_workspace_ids or [],
            notes=notes, tags=tags or [],
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO qa_test_cases VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )""",
                (
                    tc.tc_id, tc.org_id, tc.title, tc.feature_area, tc.subfeature,
                    tc.description, tc.preconditions, _j(tc.steps),
                    tc.expected_result, tc.priority, tc.severity_if_fails,
                    tc.test_type, _j(tc.applies_to_agents),
                    _j(tc.applies_to_ui_surfaces), int(tc.release_blocker),
                    tc.status, tc.created_by, tc.updated_by, tc.created_at,
                    tc.updated_at, _j(tc.linked_user_story_ids),
                    _j(tc.linked_bug_ids), _j(tc.linked_workspace_ids),
                    tc.notes, _j(tc.tags),
                ),
            )
        return tc

    def get_test_case(self, tc_id: str) -> TestCase | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM qa_test_cases WHERE tc_id=?", (tc_id,)
            ).fetchone()
        return self._row_to_tc(row) if row else None

    def update_test_case(self, tc_id: str, updates: dict[str, Any], updated_by: str = "system") -> TestCase | None:
        tc = self.get_test_case(tc_id)
        if not tc:
            return None
        json_fields = {
            "steps", "applies_to_agents", "applies_to_ui_surfaces",
            "linked_user_story_ids", "linked_bug_ids", "linked_workspace_ids", "tags",
        }
        for k, v in updates.items():
            if hasattr(tc, k):
                setattr(tc, k, v)
        tc.updated_by = updated_by
        tc.updated_at = _now()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE qa_test_cases SET
                    title=?, feature_area=?, subfeature=?, description=?,
                    preconditions=?, steps=?, expected_result=?, priority=?,
                    severity_if_fails=?, test_type=?, applies_to_agents=?,
                    applies_to_ui_surfaces=?, release_blocker=?, status=?,
                    updated_by=?, updated_at=?, linked_user_story_ids=?,
                    linked_bug_ids=?, linked_workspace_ids=?, notes=?, tags=?
                WHERE tc_id=?""",
                (
                    tc.title, tc.feature_area, tc.subfeature, tc.description,
                    tc.preconditions, _j(tc.steps), tc.expected_result,
                    tc.priority, tc.severity_if_fails, tc.test_type,
                    _j(tc.applies_to_agents), _j(tc.applies_to_ui_surfaces),
                    int(tc.release_blocker), tc.status, tc.updated_by,
                    tc.updated_at, _j(tc.linked_user_story_ids),
                    _j(tc.linked_bug_ids), _j(tc.linked_workspace_ids),
                    tc.notes, _j(tc.tags), tc_id,
                ),
            )
        return tc

    def deprecate_test_case(self, tc_id: str, updated_by: str = "system") -> bool:
        result = self.update_test_case(tc_id, {"status": "deprecated"}, updated_by=updated_by)
        return result is not None

    def clone_test_case(self, tc_id: str, new_title: str | None = None, created_by: str = "system") -> TestCase | None:
        src = self.get_test_case(tc_id)
        if not src:
            return None
        return self.create_test_case(
            title=new_title or f"[Clone] {src.title}",
            feature_area=src.feature_area,
            test_type=src.test_type,
            org_id=src.org_id,
            subfeature=src.subfeature,
            description=src.description,
            preconditions=src.preconditions,
            steps=list(src.steps),
            expected_result=src.expected_result,
            priority=src.priority,
            severity_if_fails=src.severity_if_fails,
            applies_to_agents=list(src.applies_to_agents),
            applies_to_ui_surfaces=list(src.applies_to_ui_surfaces),
            release_blocker=src.release_blocker,
            status="draft",
            created_by=created_by,
            tags=list(src.tags),
        )

    def list_test_cases(
        self, *,
        org_id: str = "default",
        feature_area: str | None = None,
        test_type: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        release_blocker: bool | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[TestCase]:
        sql = "SELECT * FROM qa_test_cases WHERE org_id=?"
        params: list[Any] = [org_id]
        if feature_area:
            sql += " AND feature_area=?"
            params.append(feature_area)
        if test_type:
            sql += " AND test_type=?"
            params.append(test_type)
        if status:
            sql += " AND status=?"
            params.append(status)
        if priority:
            sql += " AND priority=?"
            params.append(priority)
        if release_blocker is not None:
            sql += " AND release_blocker=?"
            params.append(int(release_blocker))
        if search:
            sql += " AND (title LIKE ? OR description LIKE ? OR tags LIKE ?)"
            q = f"%{search}%"
            params += [q, q, q]
        sql += " ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, created_at DESC"
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_tc(r) for r in rows]

    # ─── Test Suites ─────────────────────────────────────────────────────────

    def create_suite(
        self, *,
        name: str,
        suite_type: str,
        org_id: str = "default",
        description: str = "",
        feature_areas: list[str] | None = None,
        test_case_ids: list[str] | None = None,
        generated_by_rule: str = "",
        owner: str = "",
    ) -> TestSuite:
        now = _now()
        suite = TestSuite(
            suite_id=f"suite-{uuid4().hex[:12]}",
            org_id=org_id, name=name, description=description,
            suite_type=suite_type, feature_areas=feature_areas or [],
            test_case_ids=test_case_ids or [],
            generated_by_rule=generated_by_rule,
            owner=owner, created_at=now, updated_at=now, status="active",
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO qa_test_suites VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    suite.suite_id, suite.org_id, suite.name, suite.description,
                    suite.suite_type, _j(suite.feature_areas),
                    _j(suite.test_case_ids), suite.generated_by_rule,
                    suite.owner, suite.created_at, suite.updated_at, suite.status,
                ),
            )
        return suite

    def get_suite(self, suite_id: str) -> TestSuite | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM qa_test_suites WHERE suite_id=?", (suite_id,)
            ).fetchone()
        return self._row_to_suite(row) if row else None

    def update_suite(self, suite_id: str, updates: dict[str, Any]) -> TestSuite | None:
        suite = self.get_suite(suite_id)
        if not suite:
            return None
        for k, v in updates.items():
            if hasattr(suite, k):
                setattr(suite, k, v)
        suite.updated_at = _now()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE qa_test_suites SET
                    name=?, description=?, suite_type=?, feature_areas=?,
                    test_case_ids=?, generated_by_rule=?, owner=?,
                    updated_at=?, status=?
                WHERE suite_id=?""",
                (
                    suite.name, suite.description, suite.suite_type,
                    _j(suite.feature_areas), _j(suite.test_case_ids),
                    suite.generated_by_rule, suite.owner, suite.updated_at,
                    suite.status, suite_id,
                ),
            )
        return suite

    def list_suites(self, org_id: str = "default", status: str | None = None) -> list[TestSuite]:
        sql = "SELECT * FROM qa_test_suites WHERE org_id=?"
        params: list[Any] = [org_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_suite(r) for r in rows]

    def generate_suite_from_rules(
        self, *,
        name: str,
        rule: str,
        org_id: str = "default",
        owner: str = "",
    ) -> TestSuite:
        """
        Generate a suite dynamically based on rule string.
        Rule format: "feature_area=workspaces,test_type=smoke,release_blocker=true"
        """
        kwargs: dict[str, Any] = {"org_id": org_id}
        for part in rule.split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "feature_area":
                    kwargs["feature_area"] = v
                elif k == "test_type":
                    kwargs["test_type"] = v
                elif k == "status":
                    kwargs["status"] = v
                elif k == "priority":
                    kwargs["priority"] = v
                elif k == "release_blocker":
                    kwargs["release_blocker"] = v.lower() == "true"
        tests = self.list_test_cases(**kwargs)
        feature_areas = list({t.feature_area for t in tests})
        # Determine suite_type from rule
        suite_type = "custom"
        if "release_blocker=true" in rule:
            suite_type = "release_candidate"
        elif "test_type=smoke" in rule:
            suite_type = "smoke"
        elif "test_type=regression" in rule:
            suite_type = "regression"
        elif "test_type=safety" in rule:
            suite_type = "safety"
        elif "feature_area=" in rule:
            suite_type = "feature_specific"
        return self.create_suite(
            name=name,
            suite_type=suite_type,
            org_id=org_id,
            description=f"Auto-generated from rule: {rule}",
            feature_areas=feature_areas,
            test_case_ids=[t.tc_id for t in tests],
            generated_by_rule=rule,
            owner=owner,
        )

    # ─── Test Runs ───────────────────────────────────────────────────────────

    def create_test_run(
        self, *,
        suite_id: str,
        title: str,
        org_id: str = "default",
        environment: str = "development",
        triggered_by: str = "manual",
        run_type: str = "manual",
        notes: str = "",
    ) -> TestRun:
        suite = self.get_suite(suite_id)
        not_run_count = len(suite.test_case_ids) if suite else 0
        now = _now()
        run = TestRun(
            run_id=f"run-{uuid4().hex[:12]}",
            org_id=org_id, suite_id=suite_id, title=title,
            environment=environment, triggered_by=triggered_by,
            run_type=run_type, started_at=now, completed_at=None,
            status="in_progress", summary="", notes=notes,
            pass_count=0, fail_count=0, blocked_count=0,
            not_run_count=not_run_count,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO qa_test_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run.run_id, run.org_id, run.suite_id, run.title,
                    run.environment, run.triggered_by, run.run_type,
                    run.started_at, run.completed_at, run.status,
                    run.summary, run.notes, run.pass_count, run.fail_count,
                    run.blocked_count, run.not_run_count,
                ),
            )
        return run

    def complete_test_run(self, run_id: str, summary: str = "", notes: str = "") -> TestRun | None:
        with sqlite3.connect(self._db_path) as conn:
            # Recount from results
            counts = conn.execute(
                """SELECT result, COUNT(*) FROM qa_test_results
                   WHERE run_id=? GROUP BY result""", (run_id,)
            ).fetchall()
            result_map = {r[0]: r[1] for r in counts}
            now = _now()
            conn.execute(
                """UPDATE qa_test_runs SET
                    status='completed', completed_at=?, summary=?, notes=?,
                    pass_count=?, fail_count=?, blocked_count=?, not_run_count=?
                WHERE run_id=?""",
                (
                    now, summary, notes,
                    result_map.get("pass", 0),
                    result_map.get("fail", 0),
                    result_map.get("blocked", 0),
                    result_map.get("not_run", 0),
                    run_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM qa_test_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return self._row_to_run(row) if row else None

    def get_run(self, run_id: str) -> TestRun | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM qa_test_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        return self._row_to_run(row) if row else None

    def list_runs(self, org_id: str = "default", suite_id: str | None = None, limit: int = 50) -> list[TestRun]:
        sql = "SELECT * FROM qa_test_runs WHERE org_id=?"
        params: list[Any] = [org_id]
        if suite_id:
            sql += " AND suite_id=?"
            params.append(suite_id)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_run(r) for r in rows]

    # ─── Test Results ────────────────────────────────────────────────────────

    def store_test_result(
        self, *,
        run_id: str,
        test_case_id: str,
        result: str,
        findings: str = "",
        reproduction_notes: str = "",
        severity: str | None = None,
        linked_bug_id: str | None = None,
        should_become_regression: bool = False,
        tester: str = "",
    ) -> TestResult:
        tr = TestResult(
            result_id=f"res-{uuid4().hex[:12]}",
            run_id=run_id, test_case_id=test_case_id, result=result,
            severity=severity, findings=findings,
            reproduction_notes=reproduction_notes,
            linked_bug_id=linked_bug_id,
            should_become_regression=should_become_regression,
            tester=tester, timestamp=_now(),
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO qa_test_results VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    tr.result_id, tr.run_id, tr.test_case_id, tr.result,
                    tr.severity, tr.findings, tr.reproduction_notes,
                    tr.linked_bug_id, int(tr.should_become_regression),
                    tr.tester, tr.timestamp,
                ),
            )
        return tr

    def list_test_results(self, run_id: str) -> list[TestResult]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM qa_test_results WHERE run_id=? ORDER BY timestamp",
                (run_id,),
            ).fetchall()
        return [self._row_to_result(r) for r in rows]

    def get_regression_candidates(self, org_id: str = "default") -> list[TestResult]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT r.* FROM qa_test_results r
                   JOIN qa_test_runs ru ON r.run_id=ru.run_id
                   WHERE ru.org_id=? AND r.should_become_regression=1
                   ORDER BY r.timestamp DESC""",
                (org_id,),
            ).fetchall()
        return [self._row_to_result(r) for r in rows]

    # ─── Bug Reports ─────────────────────────────────────────────────────────

    def create_bug_report(
        self, *,
        title: str,
        org_id: str = "default",
        severity: str = "major",
        category: str = "functional",
        area: str = "",
        repro_steps: list[str] | None = None,
        expected_result: str = "",
        actual_result: str = "",
        impact: str = "",
        recommended_fix: str = "",
        release_blocker: bool = False,
        linked_test_case_ids: list[str] | None = None,
        linked_run_ids: list[str] | None = None,
        owner: str = "",
    ) -> BugReport:
        now = _now()
        bug = BugReport(
            bug_id=f"bug-{uuid4().hex[:12]}",
            org_id=org_id, title=title, severity=severity,
            category=category, area=area, repro_steps=repro_steps or [],
            expected_result=expected_result, actual_result=actual_result,
            impact=impact, recommended_fix=recommended_fix,
            release_blocker=release_blocker,
            linked_test_case_ids=linked_test_case_ids or [],
            linked_run_ids=linked_run_ids or [],
            status="open", owner=owner, created_at=now, updated_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO qa_bug_reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    bug.bug_id, bug.org_id, bug.title, bug.severity,
                    bug.category, bug.area, _j(bug.repro_steps),
                    bug.expected_result, bug.actual_result, bug.impact,
                    bug.recommended_fix, int(bug.release_blocker),
                    _j(bug.linked_test_case_ids), _j(bug.linked_run_ids),
                    bug.status, bug.owner, bug.created_at, bug.updated_at,
                ),
            )
        return bug

    def update_bug_report(self, bug_id: str, updates: dict[str, Any]) -> BugReport | None:
        bug = self.get_bug_report(bug_id)
        if not bug:
            return None
        for k, v in updates.items():
            if hasattr(bug, k):
                setattr(bug, k, v)
        bug.updated_at = _now()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """UPDATE qa_bug_reports SET
                    title=?, severity=?, category=?, area=?, repro_steps=?,
                    expected_result=?, actual_result=?, impact=?,
                    recommended_fix=?, release_blocker=?,
                    linked_test_case_ids=?, linked_run_ids=?,
                    status=?, owner=?, updated_at=?
                WHERE bug_id=?""",
                (
                    bug.title, bug.severity, bug.category, bug.area,
                    _j(bug.repro_steps), bug.expected_result,
                    bug.actual_result, bug.impact, bug.recommended_fix,
                    int(bug.release_blocker), _j(bug.linked_test_case_ids),
                    _j(bug.linked_run_ids), bug.status, bug.owner,
                    bug.updated_at, bug_id,
                ),
            )
        return bug

    def get_bug_report(self, bug_id: str) -> BugReport | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM qa_bug_reports WHERE bug_id=?", (bug_id,)
            ).fetchone()
        return self._row_to_bug(row) if row else None

    def list_bug_reports(
        self, org_id: str = "default", status: str | None = None, area: str | None = None
    ) -> list[BugReport]:
        sql = "SELECT * FROM qa_bug_reports WHERE org_id=?"
        params: list[Any] = [org_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        if area:
            sql += " AND area=?"
            params.append(area)
        sql += " ORDER BY CASE severity WHEN 'blocker' THEN 1 WHEN 'critical' THEN 2 WHEN 'major' THEN 3 ELSE 4 END, created_at DESC"
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_bug(r) for r in rows]

    # ─── User Story Candidates ───────────────────────────────────────────────

    def create_user_story_candidate(
        self, *,
        title: str,
        org_id: str = "default",
        user_story: str = "",
        context: str = "",
        acceptance_criteria: list[str] | None = None,
        priority: str = "medium",
        dependencies: list[str] | None = None,
        source_test_case_id: str | None = None,
        source_run_id: str | None = None,
    ) -> UserStoryCandidate:
        now = _now()
        story = UserStoryCandidate(
            story_id=f"story-{uuid4().hex[:12]}",
            org_id=org_id, title=title, user_story=user_story,
            context=context, acceptance_criteria=acceptance_criteria or [],
            priority=priority, dependencies=dependencies or [],
            source_test_case_id=source_test_case_id,
            source_run_id=source_run_id, status="candidate",
            created_at=now, updated_at=now,
        )
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO qa_user_story_candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    story.story_id, story.org_id, story.title, story.user_story,
                    story.context, _j(story.acceptance_criteria), story.priority,
                    _j(story.dependencies), story.source_test_case_id,
                    story.source_run_id, story.status, story.created_at,
                    story.updated_at,
                ),
            )
        return story

    def list_user_story_candidates(
        self, org_id: str = "default", status: str | None = None
    ) -> list[UserStoryCandidate]:
        sql = "SELECT * FROM qa_user_story_candidates WHERE org_id=?"
        params: list[Any] = [org_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_story(r) for r in rows]

    # ─── Coverage Gap Analyzer ───────────────────────────────────────────────

    def analyze_coverage_gaps(self, org_id: str = "default") -> CoverageReport:
        """
        Compare registered test cases against known feature areas and
        identify coverage gaps, unlinked bugs, and under-tested agents.
        """
        all_tests = self.list_test_cases(org_id=org_id, status="active")
        all_bugs = self.list_bug_reports(org_id=org_id)

        # Coverage by area
        coverage_by_area: dict[str, int] = {}
        for area in KNOWN_FEATURE_AREAS:
            coverage_by_area[area] = sum(1 for t in all_tests if t.feature_area == area)

        # Also count any custom areas not in known list
        for t in all_tests:
            if t.feature_area not in coverage_by_area:
                coverage_by_area[t.feature_area] = coverage_by_area.get(t.feature_area, 0) + 1

        # Identify gaps
        gaps: list[CoverageGap] = []
        for area in KNOWN_FEATURE_AREAS:
            area_tests = [t for t in all_tests if t.feature_area == area]
            existing_types = {t.test_type for t in area_tests}
            missing_types = list(REQUIRED_TEST_TYPES_PER_AREA - existing_types)

            if len(area_tests) == 0:
                gaps.append(CoverageGap(
                    area=area, test_count=0, severity="critical",
                    missing_types=["smoke", "regression", "deep"],
                    recommendation=f"No test cases exist for '{area}'. Add at minimum a smoke test and regression test.",
                ))
            elif missing_types:
                gaps.append(CoverageGap(
                    area=area, test_count=len(area_tests),
                    severity="warning",
                    missing_types=missing_types,
                    recommendation=f"'{area}' is missing {', '.join(missing_types)} test coverage. Add these test types.",
                ))
            elif len(area_tests) < 3:
                gaps.append(CoverageGap(
                    area=area, test_count=len(area_tests),
                    severity="info",
                    missing_types=[],
                    recommendation=f"'{area}' has minimal coverage ({len(area_tests)} tests). Consider adding deep or edge case tests.",
                ))

        # Bugs without linked test cases
        unlinked_bug_ids = [b.bug_id for b in all_bugs if not b.linked_test_case_ids]

        # Agents without test coverage
        covered_agents: set[str] = set()
        for t in all_tests:
            covered_agents.update(t.applies_to_agents)
        # We can't enumerate all agents without the registry, so we note from test data
        under_tested_agents = []  # Would be populated if we had agent registry access

        # Recommendations
        recommendations: list[str] = []
        critical_gaps = [g for g in gaps if g.severity == "critical"]
        warning_gaps = [g for g in gaps if g.severity == "warning"]
        if critical_gaps:
            recommendations.append(
                f"{len(critical_gaps)} feature areas have zero test coverage: "
                + ", ".join(g.area for g in critical_gaps)
            )
        if warning_gaps:
            recommendations.append(
                f"{len(warning_gaps)} areas are missing required test types (smoke/regression)"
            )
        if unlinked_bug_ids:
            recommendations.append(
                f"{len(unlinked_bug_ids)} bugs have no linked test cases — create regression tests for each"
            )
        regression_candidates = self.get_regression_candidates(org_id=org_id)
        if regression_candidates:
            recommendations.append(
                f"{len(regression_candidates)} failing results are flagged for regression promotion"
            )

        risk_summary = {
            "critical": len([g for g in gaps if g.severity == "critical"]),
            "warning": len([g for g in gaps if g.severity == "warning"]),
            "info": len([g for g in gaps if g.severity == "info"]),
        }

        return CoverageReport(
            generated_at=_now(),
            total_active_tests=len(all_tests),
            coverage_by_area=coverage_by_area,
            gaps=gaps,
            unlinked_bugs=unlinked_bug_ids,
            under_tested_agents=under_tested_agents,
            recommendations=recommendations,
            risk_summary=risk_summary,
        )

    # ─── Registry Summary ────────────────────────────────────────────────────

    def get_registry_summary(self, org_id: str = "default") -> dict[str, Any]:
        """Return high-level stats for the QA home page."""
        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM qa_test_cases WHERE org_id=?", (org_id,)
            ).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM qa_test_cases WHERE org_id=? AND status='active'", (org_id,)
            ).fetchone()[0]
            draft = conn.execute(
                "SELECT COUNT(*) FROM qa_test_cases WHERE org_id=? AND status='draft'", (org_id,)
            ).fetchone()[0]
            deprecated = conn.execute(
                "SELECT COUNT(*) FROM qa_test_cases WHERE org_id=? AND status='deprecated'", (org_id,)
            ).fetchone()[0]
            by_type = conn.execute(
                """SELECT test_type, COUNT(*) FROM qa_test_cases
                   WHERE org_id=? AND status='active' GROUP BY test_type""",
                (org_id,),
            ).fetchall()
            by_area = conn.execute(
                """SELECT feature_area, COUNT(*) FROM qa_test_cases
                   WHERE org_id=? AND status='active' GROUP BY feature_area""",
                (org_id,),
            ).fetchall()
            release_blockers = conn.execute(
                "SELECT COUNT(*) FROM qa_test_cases WHERE org_id=? AND status='active' AND release_blocker=1", (org_id,)
            ).fetchone()[0]
            suite_count = conn.execute(
                "SELECT COUNT(*) FROM qa_test_suites WHERE org_id=? AND status='active'", (org_id,)
            ).fetchone()[0]
            run_count = conn.execute(
                "SELECT COUNT(*) FROM qa_test_runs WHERE org_id=?", (org_id,)
            ).fetchone()[0]
            open_bugs = conn.execute(
                "SELECT COUNT(*) FROM qa_bug_reports WHERE org_id=? AND status='open'", (org_id,)
            ).fetchone()[0]
            recent_tests = conn.execute(
                "SELECT tc_id, title, feature_area, test_type, status, created_at FROM qa_test_cases WHERE org_id=? ORDER BY created_at DESC LIMIT 5",
                (org_id,),
            ).fetchall()

        return {
            "total": total,
            "active": active,
            "draft": draft,
            "deprecated": deprecated,
            "by_type": dict(by_type),
            "by_area": dict(by_area),
            "release_blockers": release_blockers,
            "suite_count": suite_count,
            "run_count": run_count,
            "open_bugs": open_bugs,
            "recent_tests": [
                {"tc_id": r[0], "title": r[1], "feature_area": r[2],
                 "test_type": r[3], "status": r[4], "created_at": r[5]}
                for r in recent_tests
            ],
            "coverage_areas": len({r[0] for r in by_area}),
        }

    # ─── Seed Templates ──────────────────────────────────────────────────────

    def _maybe_seed_templates(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT value FROM qa_seed_version WHERE key='templates_v1'"
            ).fetchone()
            if row:
                return  # Already seeded
        self._seed_templates()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO qa_seed_version VALUES ('templates_v1', ?)",
                (_now(),),
            )

    def _seed_templates(self) -> None:
        """Seed default test cases for all 13 Friday feature areas."""
        templates = self._build_templates()
        for t in templates:
            self.create_test_case(**t)

    def _build_templates(self) -> list[dict[str, Any]]:
        return [
            # ── Chat ──────────────────────────────────────────────────────────
            dict(title="Basic question receives a coherent answer", feature_area="chat",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that a basic business question sent to Friday returns a coherent, on-topic response.",
                 preconditions="Friday is running and the chat interface is accessible.",
                 steps=["Open the chat interface", "Type: 'What are the top priorities for next quarter?'", "Submit the message"],
                 expected_result="Friday returns a relevant, coherent response within 15 seconds. No errors shown.",
                 tags=["smoke", "core", "chat"]),
            dict(title="Multi-turn conversation maintains context", feature_area="chat",
                 test_type="regression", priority="high", severity_if_fails="critical",
                 status="active", release_blocker=True,
                 description="Verify that follow-up messages in a conversation refer correctly to prior context.",
                 preconditions="Chat interface is open with an existing conversation.",
                 steps=["Send: 'Analyze our Q1 OKR performance'", "Wait for response", "Follow up: 'Which of those is most at risk?'"],
                 expected_result="The follow-up response correctly references the OKRs discussed in the first message.",
                 tags=["regression", "context", "memory"]),
            dict(title="Empty message is handled gracefully", feature_area="chat",
                 test_type="edge", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that submitting an empty or whitespace-only message does not cause errors.",
                 steps=["Focus the chat input", "Press Enter without typing anything"],
                 expected_result="Nothing is sent. No error is shown. Input remains focused.",
                 tags=["edge", "input-validation"]),
            dict(title="Friday response renders markdown formatting", feature_area="chat",
                 test_type="ux", priority="medium", severity_if_fails="minor",
                 status="active", applies_to_ui_surfaces=["chat"],
                 description="Verify that markdown in Friday's responses (headers, bullets, bold) renders correctly.",
                 steps=["Ask: 'Summarize our company strategy in a structured format'", "Review the response layout"],
                 expected_result="Response displays with proper markdown: headers bold, lists indented, code blocks styled.",
                 tags=["ux", "markdown", "rendering"]),

            # ── Agent Orchestration ──────────────────────────────────────────
            dict(title="Single specialist agent responds to domain query", feature_area="agent_orchestration",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 applies_to_agents=["chief_of_staff_strategist"],
                 description="Verify that a domain-specific question routes to the correct specialist and returns a response.",
                 steps=["Send: 'What should our sales strategy be for enterprise accounts?'"],
                 expected_result="Response is generated using the Sales & Revenue specialist. Output includes strategy recommendations.",
                 tags=["smoke", "orchestration", "agents"]),
            dict(title="Multi-agent consultation produces synthesized response", feature_area="agent_orchestration",
                 test_type="regression", priority="high", severity_if_fails="critical",
                 status="active", release_blocker=True,
                 description="Verify that complex cross-domain questions trigger multiple specialist consultations.",
                 steps=["Send: 'Should we pursue the M&A target? Consider finance, legal, and strategic fit.'"],
                 expected_result="Response draws from Finance, Legal, and Strategy specialists. Synthesis coherent. Run trace shows multi-agent consultation.",
                 tags=["regression", "multi-agent", "orchestration"]),
            dict(title="Reasoning trace records all specialist contributions", feature_area="agent_orchestration",
                 test_type="deep", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that the reasoning trace for a run captures specialist memos, confidence scores, and assumptions.",
                 steps=["Trigger a complex query", "Expand the reasoning trace on the response", "Inspect each specialist section"],
                 expected_result="Trace shows: problem statement, specialist names, confidence %, key assumptions, and risk flags.",
                 tags=["deep", "provenance", "trace"]),
            dict(title="Agent does not exceed declared tool permissions", feature_area="agent_orchestration",
                 test_type="safety", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that agents only use tools listed in their manifest's tools_allowed field.",
                 steps=["Trigger a query handled by a restricted-permission agent", "Observe tool call log in audit trace"],
                 expected_result="No tool calls outside tools_allowed. Policy engine blocks any unauthorized tool attempt.",
                 tags=["safety", "permissions", "governance"]),

            # ── Documents ────────────────────────────────────────────────────
            dict(title="Document generation returns downloadable artifact", feature_area="documents",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that requesting a document generates and returns a downloadable file.",
                 steps=["Ask: 'Generate a board update memo for Q1 performance'", "Wait for document artifact", "Click download"],
                 expected_result="A DOCX artifact appears in the response. File downloads successfully and opens in Word.",
                 tags=["smoke", "documents", "artifacts"]),
            dict(title="Document content matches the user's request", feature_area="documents",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that generated document content accurately reflects the requested topic and data.",
                 steps=["Ask: 'Create an OKR summary report for Q1 2026'", "Download and open the document", "Verify headings and data accuracy"],
                 expected_result="Document includes Q1 OKR data, is well-structured, and matches the described context.",
                 tags=["regression", "documents", "data-accuracy"]),
            dict(title="PPTX artifact renders correct slide count and layout", feature_area="documents",
                 test_type="data_integrity", priority="medium", severity_if_fails="major",
                 status="active",
                 description="Verify that generated PPTX files have the expected number of slides and layout structure.",
                 steps=["Ask: 'Create a 5-slide investor update deck'", "Download PPTX", "Open in PowerPoint and count slides"],
                 expected_result="PPTX has ~5 slides. Each slide has a title. Content is formatted, not blank.",
                 tags=["data-integrity", "pptx", "document-quality"]),

            # ── OKRs ─────────────────────────────────────────────────────────
            dict(title="Create a new objective successfully", feature_area="okrs",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 applies_to_ui_surfaces=["okrs"],
                 description="Verify that an OKR can be created through the UI and appears in the list.",
                 steps=["Navigate to /okrs", "Click '+ New Objective'", "Fill in title, level, period", "Submit"],
                 expected_result="New objective appears in the list with correct data. No error shown.",
                 tags=["smoke", "okrs", "crud"]),
            dict(title="OKR hierarchy displays parent-child relationships", feature_area="okrs",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that team-level OKRs correctly nest under company-level OKRs in the list view.",
                 steps=["Create a company-level objective", "Create a team objective with parent_id set to the company objective", "View the OKR list"],
                 expected_result="Team objective is indented under the company objective. Level dot color differs between levels.",
                 tags=["regression", "okrs", "hierarchy"]),
            dict(title="Check-in updates OKR progress and confidence", feature_area="okrs",
                 test_type="deep", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that submitting a check-in updates the objective's progress and confidence fields.",
                 steps=["Open an objective with key results", "Submit a check-in with confidence 0.8 and status 'on_track'", "Reload the objective detail"],
                 expected_result="Confidence and status reflect the submitted check-in values. Check-in appears in history.",
                 tags=["deep", "okrs", "check-in"]),
            dict(title="OKR list filters by period correctly", feature_area="okrs",
                 test_type="regression", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that the period filter on the OKR list only shows objectives for that period.",
                 steps=["Create objectives for 2026-Q1 and 2026-Q2", "Select period '2026-Q1' in the filter", "Observe the list"],
                 expected_result="Only 2026-Q1 objectives appear. Q2 objectives are hidden.",
                 tags=["regression", "okrs", "filtering"]),

            # ── Workspaces ───────────────────────────────────────────────────
            dict(title="Create a new workspace successfully", feature_area="workspaces",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 applies_to_ui_surfaces=["workspaces"],
                 description="Verify that a new workspace can be created and appears in the workspace list.",
                 steps=["Navigate to /workspaces", "Click '+ New Workspace'", "Enter name, type, description", "Save"],
                 expected_result="Workspace appears in the list with correct name and icon. No errors shown.",
                 tags=["smoke", "workspaces", "crud"]),
            dict(title="Workspace creation shows error on failure", feature_area="workspaces",
                 test_type="ux", priority="medium", severity_if_fails="major",
                 status="active",
                 description="Verify that workspace creation surfaces a clear error message if the API fails.",
                 steps=["Open New Workspace modal", "Stop the API server", "Attempt to save"],
                 expected_result="Modal displays an inline error message. Button re-enables. User is not stuck.",
                 tags=["ux", "error-handling", "workspaces"]),
            dict(title="Add and remove a workspace member", feature_area="workspaces",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that members can be added to and removed from a workspace.",
                 steps=["Open a workspace", "Add a member with role 'editor'", "Verify they appear in Members tab", "Remove them"],
                 expected_result="Member appears after addition. Member disappears after removal. No errors.",
                 tags=["regression", "workspaces", "members"]),
            dict(title="Link an OKR to a workspace", feature_area="workspaces",
                 test_type="deep", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that an OKR can be linked to a workspace and appears in workspace overview.",
                 steps=["Open workspace detail", "Use the Link Entity action", "Select an OKR", "View Overview tab"],
                 expected_result="Linked OKR appears in the OKR health table on the workspace overview.",
                 tags=["deep", "workspaces", "linking"]),

            # ── Navigation ───────────────────────────────────────────────────
            dict(title="All primary navigation links render and route correctly", feature_area="navigation",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 applies_to_ui_surfaces=["nav"],
                 description="Verify that all sidebar navigation links route to the correct pages without errors.",
                 steps=["Click Chat", "Click Process Library", "Click Documents", "Click Analytics", "Click OKRs", "Click Workspaces", "Click QA", "Click Settings"],
                 expected_result="Each link routes to the correct page. Active link is highlighted. No 404 errors.",
                 tags=["smoke", "navigation", "routing"]),
            dict(title="Command palette opens and filters with Cmd+K", feature_area="navigation",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 applies_to_ui_surfaces=["command-palette"],
                 description="Verify that pressing Cmd+K opens the command palette and typing filters results.",
                 steps=["Press Cmd+K", "Type 'OKR'", "Verify filtered results appear", "Press Escape"],
                 expected_result="Palette opens. Results filter in real-time. Escape closes the palette.",
                 tags=["regression", "command-palette", "keyboard"]),
            dict(title="Breadcrumbs display correct path on detail pages", feature_area="navigation",
                 test_type="ux", priority="low", severity_if_fails="trivial",
                 status="active",
                 description="Verify that detail pages (OKR detail, workspace detail) show correct breadcrumbs.",
                 steps=["Navigate to an OKR detail page"],
                 expected_result="Breadcrumb shows 'OKRs / [Objective Title]'. OKRs link navigates back to list.",
                 tags=["ux", "breadcrumbs", "navigation"]),

            # ── Approvals ────────────────────────────────────────────────────
            dict(title="Write-scope action triggers approval request", feature_area="approvals",
                 test_type="smoke", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that a Friday action requiring write scope creates a visible approval request.",
                 steps=["Ask Friday to perform a write-scope action (e.g. 'Update Q1 OKR target')", "Check the approvals list"],
                 expected_result="An approval card appears in the chat. Approvals endpoint returns the pending request.",
                 tags=["smoke", "approvals", "governance"]),
            dict(title="Approved action executes and logs to audit", feature_area="approvals",
                 test_type="regression", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that approving an approval request causes the action to execute and logs to audit trail.",
                 steps=["Trigger a write-scope action", "Click Approve on the approval card", "Verify execution", "Check audit log"],
                 expected_result="Action executes successfully. Audit log entry created with approver, timestamp, and action summary.",
                 tags=["regression", "approvals", "audit"]),
            dict(title="Rejected action is blocked and logged", feature_area="approvals",
                 test_type="regression", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that rejecting an approval prevents the action and logs the rejection.",
                 steps=["Trigger a write-scope action", "Click Reject on the approval card", "Verify action did not execute"],
                 expected_result="Action does not execute. Rejection reason is logged. Friday acknowledges the rejection.",
                 tags=["regression", "approvals", "safety"]),

            # ── UI Consistency ───────────────────────────────────────────────
            dict(title="Design tokens apply globally across pages", feature_area="ui_consistency",
                 test_type="smoke", priority="high", severity_if_fails="major",
                 status="active",
                 applies_to_ui_surfaces=["all"],
                 description="Verify that CSS design tokens (colors, spacing, typography) are consistent across pages.",
                 steps=["Visit Chat, OKRs, Workspaces, QA pages", "Compare background, accent, text, and surface colors"],
                 expected_result="All pages use identical color tokens. No pages have broken or hardcoded styles.",
                 tags=["ui-consistency", "design-system", "css"]),
            dict(title="Empty states show helpful callout and CTA", feature_area="ui_consistency",
                 test_type="ux", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that list pages with no data show a helpful empty state with a clear call to action.",
                 steps=["Create a fresh org with no data", "Visit OKRs, Suites, Runs, Analytics pages"],
                 expected_result="Each empty state shows an icon, descriptive message, and a primary action button.",
                 tags=["ux", "empty-state", "ui-consistency"]),
            dict(title="Status badges use correct color for each status", feature_area="ui_consistency",
                 test_type="ux", priority="low", severity_if_fails="trivial",
                 status="active",
                 description="Verify that status badges render the correct background/text color for each status value.",
                 steps=["View OKR list with active, at_risk, and behind objectives"],
                 expected_result="Active = green, At Risk = orange, Behind = red. Colors match design token values.",
                 tags=["ux", "status-badges", "color"]),

            # ── Provenance ───────────────────────────────────────────────────
            dict(title="Response reasoning trace captures full specialist chain", feature_area="provenance",
                 test_type="deep", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that the reasoning trace for a complex query captures every specialist consulted.",
                 steps=["Ask a multi-domain question", "Expand the reasoning trace dropdown", "Count specialist sections"],
                 expected_result="Each specialist that contributed appears with: name, analysis summary, confidence, assumptions.",
                 tags=["deep", "provenance", "reasoning-trace"]),
            dict(title="Audit log records every run with correct metadata", feature_area="provenance",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that every Friday run creates an entry in the audit log.",
                 steps=["Send a chat message", "Query the audit log via /runs endpoint"],
                 expected_result="An audit entry exists for the run with: run_id, user_id, org_id, started_at, specialists.",
                 tags=["regression", "audit", "provenance"]),
            dict(title="Meta-questions about Friday's own reasoning are answered", feature_area="provenance",
                 test_type="regression", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that asking 'Why did you say that?' or 'What sources did you use?' returns a sensible explanation.",
                 steps=["Ask a domain question", "Follow up: 'What reasoning did you use for that answer?'"],
                 expected_result="Friday explains which specialists were consulted and what assumptions were made.",
                 tags=["regression", "meta-questions", "transparency"]),

            # ── Permissions ──────────────────────────────────────────────────
            dict(title="Admin routes require AdminAuth header", feature_area="permissions",
                 test_type="safety", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that admin endpoints return 401 or 403 without proper authorization.",
                 steps=["Call GET /admin/dashboard without auth header", "Call POST /admin/runtime/reload without auth"],
                 expected_result="Both requests return 401 or 403. No admin data is exposed.",
                 tags=["safety", "auth", "admin"]),
            dict(title="Org data isolation prevents cross-org access", feature_area="permissions",
                 test_type="safety", priority="critical", severity_if_fails="blocker",
                 status="active", release_blocker=True,
                 description="Verify that queries with org_id A cannot return data belonging to org_id B.",
                 steps=["Create data for org-A", "Query endpoints using org-B credentials", "Verify no org-A data returned"],
                 expected_result="All list endpoints filter by org_id. No cross-org data leaks.",
                 tags=["safety", "data-isolation", "permissions"]),

            # ── Memory ───────────────────────────────────────────────────────
            dict(title="Fact persists in memory after session ends", feature_area="memory",
                 test_type="regression", priority="high", severity_if_fails="major",
                 status="active",
                 description="Verify that a fact stored in a conversation is retrievable in a new conversation.",
                 steps=["In conversation 1: state a fact ('Our head of sales is Alex')", "Start conversation 2", "Ask: 'Who is our head of sales?'"],
                 expected_result="Friday recalls 'Alex' in the new conversation without being prompted again.",
                 tags=["regression", "memory", "persistence"]),
            dict(title="Memory search returns relevant results for query", feature_area="memory",
                 test_type="deep", priority="medium", severity_if_fails="major",
                 status="active",
                 description="Verify that the memory search endpoint returns semantically relevant results.",
                 steps=["Store several organizational facts", "Query GET /memories/search?q=revenue+targets"],
                 expected_result="Results include facts related to revenue, ARR, targets. Unrelated facts are not returned.",
                 tags=["deep", "memory", "search"]),
            dict(title="Memory candidate promotion persists promoted fact", feature_area="memory",
                 test_type="regression", priority="medium", severity_if_fails="minor",
                 status="active",
                 description="Verify that promoting a memory candidate makes it available in future queries.",
                 steps=["Generate a memory candidate", "Call POST /memories/candidates/promote", "Query memory search"],
                 expected_result="Promoted fact appears in memory search results.",
                 tags=["regression", "memory", "candidates"]),

            # ── Analytics ────────────────────────────────────────────────────
            dict(title="Analytics page loads KPI dashboard", feature_area="analytics",
                 test_type="smoke", priority="high", severity_if_fails="major",
                 status="active",
                 applies_to_ui_surfaces=["analytics"],
                 description="Verify that navigating to /analytics loads the KPI dashboard without errors.",
                 steps=["Navigate to /analytics"],
                 expected_result="Page loads. If KPIs exist, they display. If none, empty state shows.",
                 tags=["smoke", "analytics", "kpi"]),
            dict(title="KPI status updates reflect on dashboard", feature_area="analytics",
                 test_type="regression", priority="medium", severity_if_fails="major",
                 status="active",
                 description="Verify that adding a KPI data point updates the KPI status card on the dashboard.",
                 steps=["Create a KPI with a target", "Post a new data point above the target", "Reload analytics"],
                 expected_result="KPI card shows 'on_track' status. Progress indicator reflects the new value.",
                 tags=["regression", "analytics", "kpi"]),

            # ── Processes ────────────────────────────────────────────────────
            dict(title="Process library loads with process list", feature_area="processes",
                 test_type="smoke", priority="high", severity_if_fails="major",
                 status="active",
                 applies_to_ui_surfaces=["processes"],
                 description="Verify that the Process Library page loads and displays existing processes.",
                 steps=["Navigate to /processes"],
                 expected_result="Page loads. Process cards appear with name, status, and completeness score.",
                 tags=["smoke", "processes", "ui"]),
            dict(title="Process version history is preserved on update", feature_area="processes",
                 test_type="regression", priority="medium", severity_if_fails="major",
                 status="active",
                 description="Verify that editing a process creates a new version rather than overwriting.",
                 steps=["Open a process", "Edit a step", "Save", "View process history"],
                 expected_result="History shows previous version. Current version is v2 or higher. Old content preserved.",
                 tags=["regression", "processes", "versioning"]),
        ]
