import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.routing import APIRoute

from apps.api.main import app
from apps.api.security import AdminAuth, HTTPException, RateLimiter
from apps.api.routes import conversations, files, finance, governance, integrations, okrs, org, processes, proactive, tasks, workspaces
from apps.api.security import AuthContext
from packages.common.models import ApprovalRequest
from packages.agents.registry import AgentRegistry, SHARED_SPECIALIST_RULES
from packages.tools.mcp import MCPRegistry, MCPServer
from packages.tools.registry import ToolRegistry


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class _FakeAuthedRequest:
    def __init__(self, *, user_id: str, org_id: str) -> None:
        self.state = SimpleNamespace(auth=AuthContext(user_id=user_id, org_id=org_id, roles=["user"]))


def test_mcp_registry_register_and_toggle(tmp_path: Path) -> None:
    reg = MCPRegistry(tmp_path / "mcp_servers.json")
    server = reg.register(MCPServer(server_id="crm", name="CRM", endpoint="http://localhost:8123"))
    assert server.server_id == "crm"

    listed = reg.list_servers()
    assert len(listed) == 1
    assert listed[0].enabled

    updated = reg.set_enabled("crm", False)
    assert updated.enabled is False


def test_tool_registry_lists_function_and_mcp_tools(tmp_path: Path) -> None:
    mcp = MCPRegistry(tmp_path / "mcp_servers.json")
    mcp.register(MCPServer(server_id="erp", name="ERP", endpoint="http://localhost:8124"))
    tools = ToolRegistry(mcp).list_tools()
    ids = [tool["tool_id"] for tool in tools]
    assert "web.research" in ids
    assert "docs.retrieve" in ids
    assert "mcp::erp" in ids


def test_agent_registry_update_status_in_temp_dir(tmp_path: Path) -> None:
    manifests_src = Path(__file__).resolve().parents[1] / "packages" / "agents" / "manifests"
    manifests_dst = tmp_path / "manifests"
    manifests_dst.mkdir(parents=True, exist_ok=True)

    src_file = manifests_src / "finance.json"
    dst_file = manifests_dst / "finance.json"
    dst_file.write_text(src_file.read_text(encoding="utf-8"), encoding="utf-8")

    registry = AgentRegistry(manifests_dst)
    updated = registry.update_status("finance", "deprecated")
    assert updated.status == "deprecated"

    loaded = json.loads(dst_file.read_text(encoding="utf-8"))
    assert loaded["status"] == "deprecated"


def test_admin_auth_and_rate_limiter(monkeypatch) -> None:
    monkeypatch.setenv("FRIDAY_ADMIN_API_KEY", "secret")
    auth = AdminAuth()
    auth.require(_FakeRequest({"x-admin-api-key": "secret"}))

    limiter = RateLimiter(requests_per_minute=2)
    limiter.check("k1")
    limiter.check("k1")
    with pytest.raises(HTTPException):
        limiter.check("k1")


def test_all_specialists_inherit_shared_registry_rules() -> None:
    manifests_dir = Path(__file__).resolve().parents[1] / "packages" / "agents" / "manifests"
    registry = AgentRegistry(manifests_dir)
    specialist = registry.build_specialist("finance")

    assert specialist.shared_rules == list(SHARED_SPECIALIST_RULES)


def test_governance_routes_filter_approvals_by_authenticated_org(monkeypatch) -> None:
    approval = ApprovalRequest(
        approval_id="appr-1",
        run_id="run-1",
        reason="need approval",
        action_summary="approve this action",
        requested_scopes=["crm.write"],
    )

    fake_service = SimpleNamespace(
        approvals=SimpleNamespace(
            get=lambda _aid: approval,
            list_pending=lambda: [approval],
            approve=lambda _aid: approval,
            reject=lambda _aid: approval,
        ),
        audit=SimpleNamespace(
            get_run=lambda run_id: SimpleNamespace(org_id="org-1") if run_id == "run-1" else None
        ),
        activity=SimpleNamespace(log=lambda **_kwargs: None),
        memory=None,
        notifications=None,
        manager=None,
    )
    monkeypatch.setattr(governance, "service", fake_service)

    allowed = governance.list_approvals(_FakeAuthedRequest(user_id="u1", org_id="org-1"))
    assert len(allowed["approvals"]) == 1

    with pytest.raises(HTTPException) as exc:
        governance.get_approval("appr-1", _FakeAuthedRequest(user_id="u2", org_id="org-2"))
    assert exc.value.status_code == 404


def test_governance_memory_routes_bind_to_authenticated_org(monkeypatch) -> None:
    captured: dict[str, object] = {}
    def _list_semantic(org_id, workspace_id=None, limit=100, offset=0):
        captured["list_org"] = org_id
        return []

    fake_memory = SimpleNamespace(
        list_semantic=_list_semantic,
        search=lambda org_id, query: {"org_id": org_id, "query": query},
        get_candidate=lambda candidate_id: {"candidate_id": candidate_id, "org_id": "org-1"},
        promote_candidate=lambda candidate_id, approved=False: {"candidate_id": candidate_id, "approved": approved},
        _semantic_by_org={"org-1": {"foo": "bar"}},
        _repository=None,
        list_candidates=lambda org_id: [{"candidate_id": "cand-1", "org_id": org_id}],
    )
    fake_service = SimpleNamespace(memory=fake_memory)
    monkeypatch.setattr(governance, "service", fake_service)

    req = _FakeAuthedRequest(user_id="u1", org_id="org-1")
    listed = governance.list_memories(req, org_id="other-org")
    assert listed["org_id"] == "org-1"
    assert captured["list_org"] == "org-1"

    with pytest.raises(HTTPException) as exc:
        governance.search_memories(_FakeAuthedRequest(user_id="u1", org_id="org-1"), org_id="org-2", q="foo")
    assert exc.value.status_code == 404

    promoted = governance.promote_memory_candidate(
        governance.PromoteCandidatePayload(candidate_id="cand-1", approved=True),
        _FakeAuthedRequest(user_id="u1", org_id="org-1"),
    )
    assert promoted["candidate_id"] == "cand-1"


def test_notification_routes_bind_to_authenticated_user(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    fake_notifications = SimpleNamespace(
        list=lambda recipient_id, unread_only=False, limit=50: calls.append(("list", recipient_id)) or [],
        count_unread=lambda recipient_id: calls.append(("count", recipient_id)) or 3,
        mark_all_read=lambda recipient_id: calls.append(("read_all", recipient_id)),
    )
    fake_service = SimpleNamespace(notifications=fake_notifications)
    monkeypatch.setattr(tasks, "service", fake_service)

    req = _FakeAuthedRequest(user_id="user-123", org_id="org-1")
    tasks.list_notifications(req, recipient_id="other-user")
    count = tasks.unread_notification_count(req, recipient_id="other-user")
    tasks.mark_all_notifications_read(req, recipient_id="other-user")

    assert count["count"] == 3
    assert calls == [
        ("list", "user-123"),
        ("count", "user-123"),
        ("read_all", "user-123"),
    ]


def test_activity_route_binds_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    fake_activity = SimpleNamespace(
        list_for_org=lambda org_id="org-1", limit=50, entity_type=None, action_prefix=None: calls.append(("activity", org_id)) or []
    )
    monkeypatch.setattr(tasks, "service", SimpleNamespace(activity=fake_activity))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-222")
    tasks.list_activity(req, org_id="other-org")
    assert calls == [("activity", "org-222")]


def test_notification_id_routes_require_authenticated_recipient(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    matching = SimpleNamespace(notification_id="notif-1", recipient_id="user-123")
    other = SimpleNamespace(notification_id="notif-2", recipient_id="other-user")
    fake_notifications = SimpleNamespace(
        get=lambda notification_id: matching if notification_id == "notif-1" else other if notification_id == "notif-2" else None,
        mark_read=lambda notification_id: calls.append(("read", notification_id)),
        delete=lambda notification_id: calls.append(("delete", notification_id)),
    )
    monkeypatch.setattr(tasks, "service", SimpleNamespace(notifications=fake_notifications))

    req = _FakeAuthedRequest(user_id="user-123", org_id="org-1")
    tasks.mark_notification_read("notif-1", req)
    tasks.delete_notification("notif-1", req)
    assert calls == [("read", "notif-1"), ("delete", "notif-1")]

    with pytest.raises(HTTPException) as exc:
        tasks.mark_notification_read("notif-2", req)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        tasks.delete_notification("notif-2", req)
    assert exc.value.status_code == 404


def test_activity_entity_route_binds_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str, str]] = []
    fake_activity = SimpleNamespace(
        list_for_entity=lambda entity_type, entity_id, org_id=None, limit=50: calls.append((entity_type, entity_id, org_id)) or []
    )
    monkeypatch.setattr(tasks, "service", SimpleNamespace(activity=fake_activity))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-333")
    tasks.list_activity_for_entity(req, "task", "task-1")
    assert calls == [("task", "task-1", "org-333")]


def test_integration_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str, str | None]] = []
    fake_credentials = SimpleNamespace(
        list_credentials=lambda org_id: calls.append(("list", org_id, None)) or [],
        has_credential=lambda provider, org_id: calls.append(("has", org_id, provider)) or False,
        delete_credential=lambda provider, org_id: calls.append(("delete", org_id, provider)),
        get_credential=lambda provider, org_id: SimpleNamespace(token="x", metadata={"team": "T", "bot": "B"}),
    )
    monkeypatch.setattr(integrations, "service", SimpleNamespace(credentials=fake_credentials))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-123")
    integrations.list_credentials(req, org_id="other-org")
    integrations.integration_status(req, org_id="other-org")
    integrations.slack_status(req, org_id="other-org")
    integrations.slack_disconnect(req, org_id="other-org")

    assert ("list", "org-123", None) in calls
    assert ("delete", "org-123", "slack") in calls
    assert all(call[1] == "org-123" for call in calls)


def test_org_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    fake_org_context = SimpleNamespace(
        get_profile=lambda org_id: calls.append(("profile", org_id)) or None,
        list_people=lambda org_id, department=None: calls.append(("people", org_id)) or [],
        org_chart=lambda org_id: calls.append(("chart", org_id)) or {},
        list_priorities=lambda org_id: calls.append(("priorities", org_id)) or [],
    )
    fake_meetings = SimpleNamespace(
        list_meetings=lambda org_id, status=None: calls.append(("meetings", org_id)) or [],
        list_action_items=lambda org_id, status="open", owner=None: calls.append(("action_items", org_id)) or [],
    )
    fake_decisions = SimpleNamespace(
        list_decisions=lambda org_id, tag=None: calls.append(("decisions", org_id)) or [],
        search=lambda q, org_id: calls.append(("decision_search", org_id)) or [],
    )
    monkeypatch.setattr(
        org,
        "service",
        SimpleNamespace(org_context=fake_org_context, meetings=fake_meetings, decisions=fake_decisions),
    )

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-456")
    org.get_org_profile(req, org_id="other-org")
    org.list_people(req, org_id="other-org")
    org.org_chart(req, org_id="other-org")
    org.list_priorities(req, org_id="other-org")
    org.list_meetings(req, org_id="other-org")
    org.list_action_items(req, org_id="other-org")
    org.list_decisions(req, org_id="other-org")
    org.search_decisions(req, q="risk", org_id="other-org")

    assert calls
    assert all(call[1] == "org-456" for call in calls)


def test_file_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    matching_file = SimpleNamespace(
        file_id="file-1",
        org_id="org-789",
        filename="memo.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_path="/tmp/memo.docx",
        metadata={"format": "docx"},
        to_dict=lambda: {"file_id": "file-1", "filename": "memo.docx", "metadata": {"format": "docx"}},
    )
    other_file = SimpleNamespace(
        file_id="file-2",
        org_id="other-org",
        filename="secret.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_path="/tmp/secret.docx",
        metadata={"format": "docx"},
        to_dict=lambda: {"file_id": "file-2"},
    )
    fake_storage = SimpleNamespace(
        list_files=lambda org_id, limit=50: calls.append(("list", org_id)) or [matching_file],
        get_metadata=lambda file_id: matching_file if file_id == "file-1" else other_file if file_id == "file-2" else None,
        retrieve=lambda file_id: (matching_file, b"doc"),
        delete=lambda file_id: calls.append(("delete", file_id)),
    )
    fake_templates = SimpleNamespace(
        list_templates=lambda org_id, category=None: calls.append(("templates", org_id)) or [],
        get=lambda template_id: SimpleNamespace(
            template_id=template_id,
            org_id="org-789" if template_id == "tpl-ok" else "other-org",
            to_dict=lambda: {"template_id": template_id},
        ),
    )
    fake_brand = SimpleNamespace(
        get_brand_or_default=lambda org_id: calls.append(("brand", org_id)) or {"org_id": org_id},
        update_brand=lambda org_id, changes: calls.append(("brand_update", org_id)) or {"org_id": org_id, **changes},
    )
    monkeypatch.setattr(
        files,
        "service",
        SimpleNamespace(storage=fake_storage, templates=fake_templates, brand=fake_brand, docgen=None),
    )

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-789")
    listed = files.list_files(req, org_id="other-org")
    docs = files.list_documents(req, org_id="other-org")
    templates = files.list_templates(req, org_id="other-org")
    brand = files.get_brand(req, org_id="other-org")
    updated = files.update_brand(files.BrandUpdatePayload(company_name="Friday Co"), req, org_id="other-org")
    tpl = files.get_template("tpl-ok", req)
    files.delete_file("file-1", req)

    assert listed[0]["file_id"] == "file-1"
    assert docs[0]["file_id"] == "file-1"
    assert templates == []
    assert brand["org_id"] == "org-789"
    assert updated["org_id"] == "org-789"
    assert tpl["template_id"] == "tpl-ok"
    assert ("list", "org-789") in calls
    assert ("templates", "org-789") in calls
    assert ("brand", "org-789") in calls
    assert ("brand_update", "org-789") in calls

    with pytest.raises(HTTPException) as exc:
        files.get_template("tpl-other", req)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        files.delete_file("file-2", req)
    assert exc.value.status_code == 404


def test_process_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    process_doc = SimpleNamespace(
        id="proc-1",
        org_id="org-999",
        process_name="Reporting QA",
        status="draft",
        version="1.0.0",
        trigger="monthly close",
        roles=[],
        steps=[],
        exceptions=[],
        decision_points=[],
        completeness_score=0.5,
        to_dict=lambda: {"id": "proc-1", "org_id": "org-999"},
    )
    other_doc = SimpleNamespace(id="proc-2", org_id="other-org", to_dict=lambda: {"id": "proc-2"})
    fake_repo = SimpleNamespace(
        get_execution_run=lambda run_id: {"run_id": run_id, "process_id": "proc-1"} if run_id == "run-1" else None
    )
    fake_processes = SimpleNamespace(
        list=lambda org_id="org-1": calls.append(("list", org_id)) or [process_doc],
        get=lambda process_id: process_doc if process_id == "proc-1" else other_doc if process_id == "proc-2" else None,
        history=lambda process_id: calls.append(("history", process_id)) or [],
        list_executions=lambda process_id: calls.append(("runs", process_id)) or [],
        start_execution=lambda process_id, actor="user": calls.append(("start", actor)) or {"run_id": "run-1"},
        advance_step=lambda run_id: calls.append(("advance", run_id)) or {"run_id": run_id},
        complete_execution=lambda run_id: calls.append(("complete", run_id)) or {"run_id": run_id},
        completeness_breakdown=lambda doc: {"score": 0.5},
        generate_mermaid=lambda process_id: {"mermaid": "graph TD", "source": "generated"},
        delete=lambda process_id: calls.append(("delete", process_id)),
        _repo=fake_repo,
    )
    monkeypatch.setattr(
        processes,
        "service",
        SimpleNamespace(
            processes=fake_processes,
            process_analytics=SimpleNamespace(org_health=lambda org_id: calls.append(("analytics", org_id)) or {"org_id": org_id}),
            brand=SimpleNamespace(get_brand_or_default=lambda org_id: SimpleNamespace(to_dict=lambda: {"company_name": "Friday"})),
            docgen=None,
        ),
    )

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-999")
    listed = processes.list_processes(req, org_id="other-org")
    fetched = processes.get_process("proc-1", req)
    analytics = processes.process_analytics(req, org_id="other-org")
    processes.process_history("proc-1", req)
    processes.list_process_executions("proc-1", req)
    processes.start_process_execution("proc-1", req, actor="other-user")
    processes.advance_process_step("run-1", req)
    processes.complete_process_execution("run-1", req)
    processes.delete_process("proc-1", req)

    assert listed[0]["id"] == "proc-1"
    assert fetched["org_id"] == "org-999"
    assert analytics["org_id"] == "org-999"
    assert ("list", "org-999") in calls
    assert ("analytics", "org-999") in calls
    assert ("start", "user-1") in calls

    with pytest.raises(HTTPException) as exc:
        processes.get_process("proc-2", req)
    assert exc.value.status_code == 404


def test_okr_routes_bind_to_authenticated_org(monkeypatch) -> None:
    import asyncio

    calls: list[tuple[str, str]] = []
    org_node = SimpleNamespace(node_id="node-1", org_id="org-321")
    other_node = SimpleNamespace(node_id="node-2", org_id="other-org")
    period = SimpleNamespace(period_id="period-1", org_id="org-321")
    objective = SimpleNamespace(objective_id="obj-1", org_id="org-321", period_id="period-1", org_node_id="node-1")
    other_objective = SimpleNamespace(objective_id="obj-2", org_id="other-org")
    key_result = SimpleNamespace(kr_id="kr-1", org_id="org-321")
    other_kr = SimpleNamespace(kr_id="kr-2", org_id="other-org")
    kpi = SimpleNamespace(kpi_id="kpi-1", org_id="org-321")
    other_kpi = SimpleNamespace(kpi_id="kpi-2", org_id="other-org")
    initiative = SimpleNamespace(initiative_id="init-1", org_id="org-321")
    other_initiative = SimpleNamespace(initiative_id="init-2", org_id="other-org")

    fake_okrs = SimpleNamespace(
        list_org_nodes=lambda org_id="org-1": calls.append(("org_nodes", org_id)) or [],
        create_org_node=lambda **kwargs: SimpleNamespace(**kwargs, node_id="node-1"),
        get_org_node=lambda node_id: org_node if node_id == "node-1" else other_node if node_id == "node-2" else None,
        update_org_node=lambda node_id, **kwargs: SimpleNamespace(node_id=node_id, org_id="org-321", **kwargs),
        get_org_tree=lambda org_id="org-1", root_node_id=None: {"org_id": org_id, "root_node_id": root_node_id},
        list_periods=lambda org_id="org-1", status=None: calls.append(("periods", org_id)) or [],
        create_period=lambda **kwargs: SimpleNamespace(**kwargs, period_id="period-1"),
        get_period=lambda period_id: period if period_id == "period-1" else None,
        update_period=lambda period_id, **kwargs: SimpleNamespace(period_id=period_id, org_id="org-321", **kwargs),
        activate_period=lambda period_id: SimpleNamespace(period_id=period_id, org_id="org-321", status="active"),
        close_period=lambda period_id: SimpleNamespace(period_id=period_id, org_id="org-321", status="closed"),
        list_objectives=lambda org_id="org-1", **kwargs: calls.append(("objectives", org_id)) or [],
        create_objective=lambda **kwargs: SimpleNamespace(**kwargs, objective_id="obj-1"),
        get_objective=lambda objective_id: objective if objective_id == "obj-1" else other_objective if objective_id == "obj-2" else None,
        get_objective_with_details=lambda objective_id: {"objective": {"objective_id": objective_id, "org_id": "org-321"}} if objective_id == "obj-1" else {"objective": {"objective_id": objective_id, "org_id": "other-org"}} if objective_id == "obj-2" else {},
        update_objective=lambda objective_id, **kwargs: SimpleNamespace(objective_id=objective_id, org_id="org-321", **kwargs),
        archive_objective=lambda objective_id: SimpleNamespace(objective_id=objective_id),
        get_objective_hierarchy=lambda objective_id: {"objective_id": objective_id},
        list_key_results=lambda objective_id: [],
        add_checkin=lambda **kwargs: SimpleNamespace(**kwargs, checkin_id="ci-1"),
        create_key_result=lambda **kwargs: SimpleNamespace(**kwargs, kr_id="kr-1"),
        get_key_result=lambda kr_id: key_result if kr_id == "kr-1" else other_kr if kr_id == "kr-2" else None,
        update_key_result=lambda kr_id, **kwargs: SimpleNamespace(kr_id=kr_id, org_id="org-321", **kwargs),
        delete_key_result=lambda kr_id: True,
        link_kr_to_kpi=lambda **kwargs: SimpleNamespace(**kwargs, link_id="lnk-1"),
        unlink_kr_kpi=lambda kr_id, kpi_id: True,
        list_overdue_checkins=lambda org_id="org-1", days=10: calls.append(("overdue", org_id)) or [],
        list_kpis=lambda org_id="org-1", org_node_id=None: calls.append(("kpis", org_id)) or [],
        create_kpi=lambda **kwargs: SimpleNamespace(**kwargs, kpi_id="kpi-1"),
        get_kpi=lambda kpi_id: kpi if kpi_id == "kpi-1" else other_kpi if kpi_id == "kpi-2" else None,
        update_kpi=lambda kpi_id, **kwargs: SimpleNamespace(kpi_id=kpi_id, org_id="org-321", **kwargs),
        record_kpi_value=lambda kpi_id, value: SimpleNamespace(kpi_id=kpi_id, org_id="org-321", current_value=value),
        get_kpi_trend=lambda kpi_id, limit=30: {"kpi_id": kpi_id},
        create_dependency=lambda **kwargs: SimpleNamespace(**kwargs, dependency_id="dep-1"),
        list_initiatives=lambda org_id="org-1", **kwargs: calls.append(("initiatives", org_id)) or [],
        create_initiative=lambda **kwargs: SimpleNamespace(**kwargs, initiative_id="init-1"),
        _get_initiative=lambda initiative_id: initiative if initiative_id == "init-1" else other_initiative if initiative_id == "init-2" else None,
        update_initiative=lambda initiative_id, **kwargs: SimpleNamespace(initiative_id=initiative_id, org_id="org-321", **kwargs),
        get_alignment_graph=lambda org_id="org-1", period_id=None: {"org_id": org_id},
        executive_dashboard=lambda org_id="org-1", period_id=None: {"org_id": org_id},
        analytics_dashboard=lambda org_id="org-1": {"org_id": org_id},
        generate_meeting_artifact=lambda **kwargs: SimpleNamespace(**kwargs, artifact_id="mtg-1"),
        list_meeting_artifacts=lambda org_id="org-1", meeting_type=None: calls.append(("meetings", org_id)) or [],
    )
    monkeypatch.setattr(okrs, "service", SimpleNamespace(okrs=fake_okrs))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-321")

    asyncio.run(okrs.list_org_nodes(req, org_id="other-org"))
    asyncio.run(okrs.list_periods(req, org_id="other-org"))
    asyncio.run(okrs.list_objectives(req, org_id="other-org"))
    asyncio.run(okrs.list_overdue_checkins(req, org_id="other-org"))
    asyncio.run(okrs.list_kpis(req, org_id="other-org"))
    asyncio.run(okrs.list_initiatives(req, org_id="other-org"))
    graph = asyncio.run(okrs.get_alignment_graph(req, org_id="other-org"))
    executive = asyncio.run(okrs.executive_dashboard(req, org_id="other-org"))
    analytics = asyncio.run(okrs.analytics_dashboard(req, org_id="other-org"))

    assert graph["org_id"] == "org-321"
    assert executive["org_id"] == "org-321"
    assert analytics["org_id"] == "org-321"
    assert all(call[1] == "org-321" for call in calls)

    got = asyncio.run(okrs.get_objective("obj-1", req))
    assert got["objective"]["org_id"] == "org-321"

    with pytest.raises(HTTPException):
        asyncio.run(okrs.get_objective("obj-2", req))
    with pytest.raises(HTTPException):
        asyncio.run(okrs.update_key_result("kr-2", okrs.KeyResultUpdate(title="x"), req))
    with pytest.raises(HTTPException):
        asyncio.run(okrs.update_kpi("kpi-2", okrs.KPIUpdate(name="x"), req))
    with pytest.raises(HTTPException):
        asyncio.run(okrs.update_initiative("init-2", okrs.InitiativeUpdate(title="x"), req))


def test_proactive_routes_bind_to_authenticated_org(monkeypatch) -> None:
    from dataclasses import dataclass

    @dataclass
    class _FakeDigest:
        org_id: str

    calls: list[tuple[str, str]] = []
    matching_alert = SimpleNamespace(alert_id="alert-1", org_id="org-654")
    other_alert = SimpleNamespace(alert_id="alert-2", org_id="other-org")
    fake_scanner = SimpleNamespace(
        list_alerts=lambda org_id="org-1", severity=None: calls.append(("alerts", org_id)) or [],
        get_alert=lambda alert_id: matching_alert if alert_id == "alert-1" else other_alert if alert_id == "alert-2" else None,
        acknowledge=lambda alert_id: calls.append(("ack", alert_id)),
        scan_kpis=lambda kpis: [],
        scan_okrs=lambda objectives: [],
        scan_budget=lambda categories: [],
    )
    fake_kpis = SimpleNamespace(kpi_status=lambda org_id="org-1": calls.append(("kpis", org_id)) or [])
    fake_okrs = SimpleNamespace(list_objectives=lambda org_id="org-1": calls.append(("okrs", org_id)) or [])
    fake_budgets = SimpleNamespace(budget_status=lambda org_id="org-1": calls.append(("budgets", org_id)) or [])
    fake_decisions = SimpleNamespace(list_decisions=lambda org_id="org-1", limit=10: calls.append(("decisions", org_id)) or [])
    fake_digest = SimpleNamespace(
        generate_weekly=lambda kpis, objectives, alerts, decisions, org_id="org-1": _FakeDigest(org_id=org_id),
        digest_to_markdown=lambda digest: "# digest",
    )
    monkeypatch.setattr(
        proactive,
        "service",
        SimpleNamespace(scanner=fake_scanner, kpis=fake_kpis, okrs=fake_okrs, budgets=fake_budgets, decisions=fake_decisions, digest=fake_digest),
    )

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-654")
    proactive.list_alerts(req, org_id="other-org")
    proactive.run_proactive_scan(req, org_id="other-org")
    proactive.weekly_digest(req, org_id="other-org")
    proactive.acknowledge_alert("alert-1", req)

    assert ("alerts", "org-654") in calls
    assert ("kpis", "org-654") in calls
    assert ("okrs", "org-654") in calls
    assert ("budgets", "org-654") in calls
    assert ("decisions", "org-654") in calls
    assert ("ack", "alert-1") in calls

    with pytest.raises(HTTPException) as exc:
        proactive.acknowledge_alert("alert-2", req)
    assert exc.value.status_code == 404


def test_conversation_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    matching_thread = SimpleNamespace(thread_id="thread-1", org_id="org-777", to_dict=lambda: {"thread_id": "thread-1", "org_id": "org-777"})
    other_thread = SimpleNamespace(thread_id="thread-2", org_id="other-org", to_dict=lambda: {"thread_id": "thread-2"})
    fake_conversations = SimpleNamespace(
        list_threads=lambda org_id="org-1": calls.append(("list", org_id)) or [matching_thread],
        create_thread=lambda org_id="org-1", workspace_id=None, title="New conversation", thread_id=None: SimpleNamespace(thread_id=thread_id or "thread-new", org_id=org_id, to_dict=lambda: {"thread_id": thread_id or "thread-new", "org_id": org_id}),
        get_thread=lambda thread_id: matching_thread if thread_id == "thread-1" else other_thread if thread_id == "thread-2" else None,
        get_messages=lambda thread_id: [SimpleNamespace(to_dict=lambda: {"thread_id": thread_id})],
        rename_thread=lambda thread_id, title: matching_thread,
        delete_thread=lambda thread_id: calls.append(("delete", thread_id)),
        branch_thread=lambda parent_thread_id, at_message_id, org_id="org-1", label=None: SimpleNamespace(thread_id="branch-1", org_id=org_id, to_dict=lambda: {"thread_id": "branch-1", "org_id": org_id}),
        get_branches=lambda thread_id: [matching_thread],
    )
    monkeypatch.setattr(
        conversations,
        "service",
        SimpleNamespace(conversations=fake_conversations, memory=SimpleNamespace(clear_conversation=lambda thread_id: calls.append(("clear", thread_id)))),
    )

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-777")
    listed = conversations.list_conversations(req, org_id="other-org")
    created = conversations.create_conversation(conversations.ConversationCreate(org_id="other-org", title="Test"), req)
    messages = conversations.get_conversation_messages("thread-1", req)
    renamed = conversations.rename_conversation("thread-1", conversations.ConversationRename(title="Renamed"), req)
    branched = conversations.branch_conversation("thread-1", conversations.BranchPayload(at_message_id="msg-1", org_id="other-org"), req)
    branches = conversations.get_conversation_branches("thread-1", req)
    conversations.delete_conversation("thread-1", req)

    assert listed[0]["org_id"] == "org-777"
    assert created["org_id"] == "org-777"
    assert messages[0]["thread_id"] == "thread-1"
    assert renamed["org_id"] == "org-777"
    assert branched["org_id"] == "org-777"
    assert branches[0]["org_id"] == "org-777"
    assert ("list", "org-777") in calls
    assert ("delete", "thread-1") in calls
    assert ("clear", "thread-1") in calls

    with pytest.raises(HTTPException) as exc:
        conversations.get_conversation_messages("thread-2", req)
    assert exc.value.status_code == 404


def test_finance_routes_bind_to_authenticated_org(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []
    matching_category = SimpleNamespace(category_id="cat-1", org_id="org-888")
    other_category = SimpleNamespace(category_id="cat-2", org_id="other-org")
    fake_invoices = SimpleNamespace(
        list_invoices=lambda org_id="org-1": calls.append(("invoices", org_id)) or [],
        create_invoice=lambda **kwargs: SimpleNamespace(to_dict=lambda: {"org_id": kwargs["org_id"]}),
    )
    fake_budgets = SimpleNamespace(
        budget_status=lambda org_id="org-1": calls.append(("budget", org_id)) or [],
        create_category=lambda name, planned_amount, org_id="org-1", period="monthly": SimpleNamespace(to_dict=lambda: {"org_id": org_id}),
        get_category=lambda category_id: matching_category if category_id == "cat-1" else other_category if category_id == "cat-2" else None,
        record_expense=lambda category_id, amount, description="": SimpleNamespace(to_dict=lambda: {"category_id": category_id}),
    )
    monkeypatch.setattr(finance, "service", SimpleNamespace(invoices=fake_invoices, budgets=fake_budgets))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-888")
    finance.list_invoices(req, org_id="other-org")
    created_invoice = finance.create_invoice(finance.InvoiceCreatePayload(client_name="Acme", org_id="other-org"), req)
    finance.budget_status(req, org_id="other-org")
    created_category = finance.create_budget_category(finance.BudgetCategoryPayload(name="Ops", planned_amount=1000, org_id="other-org"), req)
    recorded = finance.record_expense(finance.ExpensePayload(category_id="cat-1", amount=20), req)

    assert created_invoice["org_id"] == "org-888"
    assert created_category["org_id"] == "org-888"
    assert recorded["category_id"] == "cat-1"
    assert ("invoices", "org-888") in calls
    assert ("budget", "org-888") in calls

    with pytest.raises(HTTPException) as exc:
        finance.record_expense(finance.ExpensePayload(category_id="cat-2", amount=20), req)
    assert exc.value.status_code == 404


def test_workspace_routes_bind_to_authenticated_org(monkeypatch) -> None:
    from packages.projects.service import Project
    from packages.workspaces.service import Workspace, WorkspaceLink, WorkspaceMember

    calls: list[tuple[str, str]] = []
    matching_workspace = Workspace(
        workspace_id="ws-1",
        name="Ops",
        slug="ops",
        description="",
        icon="🏢",
        color="#0f5cc0",
        type="team",
        owner="user-1",
        org_id="org-999",
        visibility="open",
        default_view="overview",
        archived=False,
        created_at="2026-03-17T00:00:00Z",
        updated_at="2026-03-17T00:00:00Z",
    )
    other_workspace = Workspace(
        workspace_id="ws-2",
        name="Other",
        slug="other",
        description="",
        icon="🏢",
        color="#0f5cc0",
        type="team",
        owner="user-1",
        org_id="other-org",
        visibility="open",
        default_view="overview",
        archived=False,
        created_at="2026-03-17T00:00:00Z",
        updated_at="2026-03-17T00:00:00Z",
    )
    matching_project = Project(project_id="proj-1", workspace_id="ws-1", name="Project")
    other_project = Project(project_id="proj-2", workspace_id="ws-2", name="Other Project")
    fake_workspaces = SimpleNamespace(
        list=lambda org_id="org-1", archived=False: calls.append(("list", org_id)) or [matching_workspace],
        create=lambda name, org_id="org-1", owner="user-1", **kwargs: Workspace(
            workspace_id="ws-new",
            name=name,
            slug="ws-new",
            description=kwargs.get("description", ""),
            icon=kwargs.get("icon", "🏢"),
            color=kwargs.get("color", "#0f5cc0"),
            type=kwargs.get("type", "team"),
            owner=owner,
            org_id=org_id,
            visibility=kwargs.get("visibility", "open"),
            default_view=kwargs.get("default_view", "overview"),
            archived=False,
            created_at="2026-03-17T00:00:00Z",
            updated_at="2026-03-17T00:00:00Z",
        ),
        get=lambda workspace_id: matching_workspace if workspace_id == "ws-1" else other_workspace if workspace_id == "ws-2" else None,
        get_for_org=lambda workspace_id, org_id: matching_workspace if workspace_id == "ws-1" and org_id == "org-999" else None,
        update=lambda workspace_id, **kwargs: matching_workspace,
        update_for_org=lambda workspace_id, org_id, **kwargs: matching_workspace if workspace_id == "ws-1" and org_id == "org-999" else None,
        archive=lambda workspace_id: calls.append(("archive", workspace_id)),
        archive_for_org=lambda workspace_id, org_id: calls.append(("archive", workspace_id)) or (workspace_id == "ws-1" and org_id == "org-999"),
        list_members=lambda workspace_id: [],
        list_members_for_org=lambda workspace_id, org_id: [] if workspace_id == "ws-1" and org_id == "org-999" else [],
        add_member=lambda workspace_id, user_id, role="editor": WorkspaceMember(member_id="wm-1", workspace_id=workspace_id, user_id=user_id, role=role, joined_at="2026-03-17T00:00:00Z"),
        add_member_for_org=lambda workspace_id, org_id, user_id, role="editor": WorkspaceMember(member_id="wm-1", workspace_id=workspace_id, user_id=user_id, role=role, joined_at="2026-03-17T00:00:00Z") if workspace_id == "ws-1" and org_id == "org-999" else None,
        remove_member=lambda workspace_id, user_id: calls.append(("remove_member", workspace_id)),
        remove_member_for_org=lambda workspace_id, org_id, user_id: workspace_id == "ws-1" and org_id == "org-999",
        link_entity=lambda workspace_id, entity_type, entity_id: WorkspaceLink(link_id="wl-1", workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id, created_at="2026-03-17T00:00:00Z"),
        link_entity_for_org=lambda workspace_id, org_id, entity_type, entity_id: WorkspaceLink(link_id="wl-1", workspace_id=workspace_id, entity_type=entity_type, entity_id=entity_id, created_at="2026-03-17T00:00:00Z") if workspace_id == "ws-1" and org_id == "org-999" else None,
    )
    fake_projects = SimpleNamespace(
        list=lambda workspace_id: [matching_project],
        create=lambda workspace_id, name, description="", color="#6366f1", icon="📁": matching_project,
        get=lambda project_id: matching_project if project_id == "proj-1" else other_project if project_id == "proj-2" else None,
        update=lambda project_id, **kwargs: matching_project,
        update_for_workspace=lambda project_id, workspace_id, **kwargs: matching_project if project_id == "proj-1" and workspace_id == "ws-1" else None,
        delete=lambda project_id: calls.append(("delete_project", project_id)),
        delete_for_workspace=lambda project_id, workspace_id: calls.append(("delete_project", project_id)) or (project_id == "proj-1" and workspace_id == "ws-1"),
    )
    monkeypatch.setattr(workspaces, "service", SimpleNamespace(workspaces=fake_workspaces, projects=fake_projects))

    req = _FakeAuthedRequest(user_id="user-1", org_id="org-999")
    listed = workspaces.list_workspaces(req, org_id="other-org")
    created = workspaces.create_workspace(workspaces.WorkspaceCreate(name="Ops", org_id="other-org", owner="other-user"), req)
    fetched = workspaces.get_workspace("ws-1", req)
    projects = workspaces.list_projects("ws-1", req)
    updated_project = workspaces.update_project("proj-1", workspaces.ProjectUpdate(name="New"), req)
    workspaces.delete_workspace("ws-1", req)
    workspaces.delete_project("proj-1", req)

    assert listed[0]["org_id"] == "org-999"
    assert created["org_id"] == "org-999"
    assert fetched["org_id"] == "org-999"
    assert projects[0]["project_id"] == "proj-1"
    assert updated_project["project_id"] == "proj-1"
    assert ("list", "org-999") in calls
    assert ("archive", "ws-1") in calls
    assert ("delete_project", "proj-1") in calls

    with pytest.raises(HTTPException) as exc:
        workspaces.get_workspace("ws-2", req)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc:
        workspaces.update_project("proj-2", workspaces.ProjectUpdate(name="Nope"), req)
    assert exc.value.status_code == 404


def test_app_openapi_builds_with_slack_callback_route() -> None:
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/integrations/slack/callback"
    )
    assert route.response_model is None

    schema = app.openapi()
    assert "/integrations/slack/callback" in schema["paths"]
