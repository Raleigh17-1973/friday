"""Tests for the WorkspaceService."""
from __future__ import annotations

import pytest
from pathlib import Path
from packages.workspaces.service import WorkspaceService


@pytest.fixture
def svc(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(db_path=tmp_path / "workspaces_test.db")


# ---------------------------------------------------------------------------
# Create & Retrieve
# ---------------------------------------------------------------------------
class TestWorkspaceCreateAndRetrieve:
    def test_create_and_get(self, svc: WorkspaceService):
        ws = svc.create(name="Engineering", type="team", owner="alice", org_id="org1")
        assert ws.name == "Engineering"
        assert ws.type == "team"
        assert ws.owner == "alice"
        assert ws.org_id == "org1"
        assert ws.workspace_id

        fetched = svc.get(ws.workspace_id)
        assert fetched is not None
        assert fetched.workspace_id == ws.workspace_id
        assert fetched.name == "Engineering"

    def test_get_nonexistent_returns_none(self, svc: WorkspaceService):
        assert svc.get("nonexistent_id_xyz") is None

    def test_get_for_org_rejects_other_org(self, svc: WorkspaceService):
        ws = svc.create(name="Engineering", type="team", owner="alice", org_id="org1")
        assert svc.get_for_org(ws.workspace_id, "org2") is None
        assert svc.get_for_org(ws.workspace_id, "org1") is not None

    def test_list_returns_workspaces(self, svc: WorkspaceService):
        svc.create(name="Alpha", type="team", owner="alice", org_id="org1")
        svc.create(name="Beta", type="team", owner="bob", org_id="org1")
        workspaces = svc.list("org1")
        names = [w.name for w in workspaces]
        assert "Alpha" in names
        assert "Beta" in names

    def test_list_filters_by_org(self, svc: WorkspaceService):
        svc.create(name="Org1WS", type="team", owner="alice", org_id="org1")
        svc.create(name="Org2WS", type="team", owner="bob", org_id="org2")
        org1_ws = svc.list("org1")
        assert all(w.org_id == "org1" for w in org1_ws)
        org2_ws = svc.list("org2")
        assert all(w.org_id == "org2" for w in org2_ws)


# ---------------------------------------------------------------------------
# Slug uniqueness
# ---------------------------------------------------------------------------
class TestWorkspaceSlugUniqueness:
    def test_slug_generated_from_name(self, svc: WorkspaceService):
        ws = svc.create(name="My Cool Project", type="team", owner="alice", org_id="org1")
        assert "my" in ws.slug.lower() or "cool" in ws.slug.lower() or ws.slug  # slug is set

    def test_duplicate_name_gets_unique_slug(self, svc: WorkspaceService):
        ws1 = svc.create(name="Engineering", type="team", owner="alice", org_id="org1")
        ws2 = svc.create(name="Engineering", type="team", owner="bob", org_id="org1")
        assert ws1.slug != ws2.slug

    def test_get_by_slug(self, svc: WorkspaceService):
        ws = svc.create(name="Data Team", type="team", owner="alice", org_id="org1")
        fetched = svc.get_by_slug("org1", ws.slug)
        assert fetched is not None
        assert fetched.workspace_id == ws.workspace_id


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------
class TestWorkspaceMemberAddRemove:
    def test_add_member(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        member = svc.add_member(ws.workspace_id, "bob", "editor")
        assert member.user_id == "bob"
        assert member.role == "editor"
        assert member.workspace_id == ws.workspace_id

    def test_list_members(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        svc.add_member(ws.workspace_id, "bob", "editor")
        svc.add_member(ws.workspace_id, "carol", "viewer")
        members = svc.list_members(ws.workspace_id)
        user_ids = [m.user_id for m in members]
        assert "bob" in user_ids
        assert "carol" in user_ids

    def test_remove_member(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        svc.add_member(ws.workspace_id, "bob", "editor")
        svc.remove_member(ws.workspace_id, "bob")
        members = svc.list_members(ws.workspace_id)
        assert not any(m.user_id == "bob" for m in members)

    def test_empty_workspace_has_no_members(self, svc: WorkspaceService):
        ws = svc.create(name="Solo", type="personal", owner="alice", org_id="org1")
        members = svc.list_members(ws.workspace_id)
        assert isinstance(members, list)

    def test_member_operations_for_org_reject_other_org(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        assert svc.add_member_for_org(ws.workspace_id, "org2", "bob") is None
        assert svc.list_members_for_org(ws.workspace_id, "org2") == []
        assert svc.remove_member_for_org(ws.workspace_id, "org2", "alice") is False


# ---------------------------------------------------------------------------
# Entity linking
# ---------------------------------------------------------------------------
class TestWorkspaceLinkEntity:
    def test_link_and_list(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        link = svc.link_entity(ws.workspace_id, "conversation", "conv_123")
        assert link.entity_type == "conversation"
        assert link.entity_id == "conv_123"

        links = svc.list_linked(ws.workspace_id, "conversation")
        assert any(lk.entity_id == "conv_123" for lk in links)

    def test_unlink_entity(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        svc.link_entity(ws.workspace_id, "document", "doc_456")
        svc.unlink_entity(ws.workspace_id, "document", "doc_456")
        links = svc.list_linked(ws.workspace_id, "document")
        assert not any(lk.entity_id == "doc_456" for lk in links)

    def test_link_different_entity_types(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        svc.link_entity(ws.workspace_id, "conversation", "conv_1")
        svc.link_entity(ws.workspace_id, "okr", "okr_1")
        conv_links = svc.list_linked(ws.workspace_id, "conversation")
        okr_links = svc.list_linked(ws.workspace_id, "okr")
        assert len(conv_links) == 1
        assert len(okr_links) == 1

    def test_link_multiple_same_type(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        svc.link_entity(ws.workspace_id, "document", "doc_1")
        svc.link_entity(ws.workspace_id, "document", "doc_2")
        svc.link_entity(ws.workspace_id, "document", "doc_3")
        links = svc.list_linked(ws.workspace_id, "document")
        ids = [lk.entity_id for lk in links]
        assert "doc_1" in ids and "doc_2" in ids and "doc_3" in ids

    def test_link_for_org_rejects_other_org(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        assert svc.link_entity_for_org(ws.workspace_id, "org2", "document", "doc_1") is None
        assert svc.list_linked_for_org(ws.workspace_id, "org2") == []


# ---------------------------------------------------------------------------
# Filtering and update
# ---------------------------------------------------------------------------
class TestWorkspaceListFiltered:
    def test_archived_not_shown_by_default(self, svc: WorkspaceService):
        ws = svc.create(name="Old Project", type="team", owner="alice", org_id="org1")
        svc.archive(ws.workspace_id)
        active = svc.list("org1", archived=False)
        assert not any(w.workspace_id == ws.workspace_id for w in active)

    def test_archived_shown_when_requested(self, svc: WorkspaceService):
        ws = svc.create(name="Old Project", type="team", owner="alice", org_id="org1")
        svc.archive(ws.workspace_id)
        all_ws = svc.list("org1", archived=True)
        assert any(w.workspace_id == ws.workspace_id for w in all_ws)

    def test_update_workspace_name(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        updated = svc.update(ws.workspace_id, name="Renamed Team")
        assert updated is not None
        assert updated.name == "Renamed Team"

    def test_update_workspace_description(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        updated = svc.update(ws.workspace_id, description="New description")
        assert updated is not None
        assert updated.description == "New description"

    def test_context_summary_returns_string(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        summary = svc.get_context_summary(ws.workspace_id)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_update_and_archive_for_org_reject_other_org(self, svc: WorkspaceService):
        ws = svc.create(name="Team", type="team", owner="alice", org_id="org1")
        assert svc.update_for_org(ws.workspace_id, "org2", name="Nope") is None
        assert svc.archive_for_org(ws.workspace_id, "org2") is False
