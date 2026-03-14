"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { PageShell } from "@/components/page-shell";

const API = "http://localhost:8000";

type UserRole = "member" | "tool_admin" | "dev_admin" | "developer";
function loadUserRole(): UserRole {
  if (typeof window === "undefined") return "member";
  return (localStorage.getItem("friday_user_role") as UserRole) ?? "member";
}
function isAdmin(role: UserRole): boolean {
  return role === "dev_admin" || role === "developer" || role === "tool_admin";
}

interface Workspace {
  workspace_id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  color: string;
  type: string;
  owner: string;
  visibility: string;
  default_view: string;
  archived: boolean;
  created_at: string;
}

interface WorkspaceMember {
  member_id: string;
  user_id: string;
  role: string;
  joined_at: string;
}

interface Objective {
  obj_id: string;
  title: string;
  level: string;
  status: string;
  owner: string;
  progress: number;
}

interface Project {
  project_id: string;
  workspace_id: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  created_at: string;
}

const STATUS_BADGE: Record<string, string> = {
  on_track: "badge badge-success",
  at_risk: "badge badge-warning",
  behind: "badge badge-danger",
  completed: "badge badge-neutral",
  active: "badge badge-info",
};

const ROLE_BADGE: Record<string, string> = {
  owner: "badge badge-purple",
  editor: "badge badge-info",
  viewer: "badge badge-neutral",
};

function statusLabel(s: string) {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="progress-bar-wrap" style={{ minWidth: 60 }}>
      <div className="progress-bar-fill" style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }} />
    </div>
  );
}

type PendingApproval = {
  approval_id: string;
  request_type: string;
  reason?: string;
  action_summary?: string;
  status: string;
};

export default function WorkspaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [addMemberForm, setAddMemberForm] = useState({ user_id: "", role: "editor" });
  const [addingMember, setAddingMember] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApproval[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [showAddProject, setShowAddProject] = useState(false);
  const [newProjectForm, setNewProjectForm] = useState({ name: "", description: "", icon: "📁", color: "#6366f1" });
  const [addingProject, setAddingProject] = useState(false);
  const [userRole, setUserRole] = useState<UserRole>("member");
  const [showRename, setShowRename] = useState(false);
  const [renameName, setRenameName] = useState("");
  const [renameSaving, setRenameSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setUserRole(loadUserRole());
    const onChange = () => setUserRole(loadUserRole());
    window.addEventListener("friday_role_changed", onChange);
    return () => window.removeEventListener("friday_role_changed", onChange);
  }, []);

  async function handleRename(e: React.FormEvent) {
    e.preventDefault();
    if (!renameName.trim()) return;
    setRenameSaving(true);
    try {
      const res = await fetch(`${API}/workspaces/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: renameName.trim() }),
      });
      if (res.ok) {
        setWorkspace((prev) => prev ? { ...prev, name: renameName.trim() } : prev);
        setShowRename(false);
      }
    } finally {
      setRenameSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await fetch(`${API}/workspaces/${id}`, { method: "DELETE" });
      router.push("/workspaces");
    } finally {
      setDeleting(false);
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const [wsRes, membersRes] = await Promise.all([
        fetch(`${API}/workspaces/${id}`),
        fetch(`${API}/workspaces/${id}/members`),
      ]);
      if (wsRes.status === 404) { setError("Workspace not found"); return; }
      if (!wsRes.ok) throw new Error("Failed to load workspace");
      setWorkspace(await wsRes.json());
      if (membersRes.ok) setMembers(await membersRes.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error loading");
    } finally {
      setLoading(false);
    }
  }

  async function loadOKRs() {
    try {
      const res = await fetch(`${API}/okrs?workspace_id=${id}&org_id=default`);
      if (res.ok) setObjectives(await res.json());
    } catch { /* non-critical */ }
  }

  async function loadProjects() {
    try {
      const res = await fetch(`${API}/workspaces/${id}/projects`);
      if (res.ok) setProjects(await res.json());
    } catch { /* non-critical */ }
  }

  async function addProject(e: React.FormEvent) {
    e.preventDefault();
    if (!newProjectForm.name.trim()) return;
    setAddingProject(true);
    try {
      const res = await fetch(`${API}/workspaces/${id}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newProjectForm),
      });
      if (res.ok) {
        setNewProjectForm({ name: "", description: "", icon: "📁", color: "#6366f1" });
        setShowAddProject(false);
        await loadProjects();
      }
    } finally {
      setAddingProject(false);
    }
  }

  async function deleteProject(projectId: string) {
    await fetch(`${API}/projects/${projectId}`, { method: "DELETE" });
    await loadProjects();
  }

  async function loadApprovals() {
    try {
      const res = await fetch(`${API}/approvals`);
      if (!res.ok) return;
      const data = await res.json() as { approvals?: PendingApproval[] } | PendingApproval[];
      const list = Array.isArray(data) ? data : (data as { approvals?: PendingApproval[] }).approvals ?? [];
      setPendingApprovals(list.filter((a) => a.status === "pending"));
    } catch { /* non-critical */ }
  }

  useEffect(() => { load(); loadOKRs(); loadApprovals(); loadProjects(); }, [id]);

  async function addMember(e: React.FormEvent) {
    e.preventDefault();
    if (!addMemberForm.user_id.trim()) return;
    setAddingMember(true);
    try {
      await fetch(`${API}/workspaces/${id}/members`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(addMemberForm),
      });
      setAddMemberForm({ user_id: "", role: "editor" });
      setShowAddMember(false);
      const res = await fetch(`${API}/workspaces/${id}/members`);
      if (res.ok) setMembers(await res.json());
    } finally {
      setAddingMember(false);
    }
  }

  if (loading) {
    return (
      <PageShell title="Loading…" breadcrumbs={[{ label: "Workspaces", href: "/workspaces" }, { label: "…" }]}>
        <div className="loading-skeleton">
          {[...Array(6)].map((_, i) => <div key={i} className="loading-skeleton-row" />)}
        </div>
      </PageShell>
    );
  }

  if (error || !workspace) {
    return (
      <PageShell title="Not Found" breadcrumbs={[{ label: "Workspaces", href: "/workspaces" }]}>
        <div className="error-state">
          <div style={{ fontSize: "2rem" }}>🗂️</div>
          <div>{error || "Workspace not found"}</div>
          <Link href="/workspaces" className="btn btn-secondary btn-sm">← Back to Workspaces</Link>
        </div>
      </PageShell>
    );
  }

  const adminActions = isAdmin(userRole) ? (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
      {confirmDelete ? (
        <>
          <span style={{ fontSize: "0.8125rem", color: "var(--danger)" }}>Delete this workspace?</span>
          <button
            className="btn btn-sm"
            style={{ background: "var(--danger)", color: "#fff", border: "none" }}
            onClick={handleDelete}
            disabled={deleting}
          >
            {deleting ? "Deleting…" : "Delete"}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => setConfirmDelete(false)}>
            Cancel
          </button>
        </>
      ) : (
        <>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => { setRenameName(workspace.name); setShowRename(true); }}
          >
            ✏ Rename
          </button>
          <button
            className="btn btn-secondary btn-sm"
            style={{ color: "var(--danger)" }}
            onClick={() => setConfirmDelete(true)}
          >
            🗑 Delete
          </button>
        </>
      )}
    </div>
  ) : null;

  return (
    <>
    {showRename && (
      <div
        style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
        onClick={() => setShowRename(false)}
      >
        <div className="card" style={{ width: 400 }} onClick={(e) => e.stopPropagation()}>
          <div className="card-header">
            Rename Workspace
            <button className="btn btn-ghost btn-sm" onClick={() => setShowRename(false)}>✕</button>
          </div>
          <form onSubmit={handleRename}>
            <div className="card-body">
              <div className="form-group">
                <label className="form-label">New name</label>
                <input
                  className="form-input"
                  value={renameName}
                  onChange={(e) => setRenameName(e.target.value)}
                  autoFocus
                  required
                />
              </div>
            </div>
            <div className="card-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
              <button type="button" className="btn btn-secondary" onClick={() => setShowRename(false)}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={renameSaving}>{renameSaving ? "Saving…" : "Save"}</button>
            </div>
          </form>
        </div>
      </div>
    )}
    <PageShell
      title={`${workspace.icon || "🗂️"} ${workspace.name}`}
      subtitle={workspace.description || workspace.type}
      breadcrumbs={[{ label: "Workspaces", href: "/workspaces" }, { label: workspace.name }]}
      tabs={[
        { id: "overview", label: "Overview" },
        { id: "projects", label: `Projects (${projects.length})` },
        { id: "okrs", label: `OKRs (${objectives.length})` },
        { id: "members", label: `Members (${members.length})` },
      ]}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      headerActions={adminActions}
    >
      {/* Overview tab */}
      {activeTab === "overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

          {/* Pending approvals banner */}
          {pendingApprovals.length > 0 && (
            <div className="card" style={{ border: "1px solid #f59e0b", background: "#fffbeb" }}>
              <div className="card-body" style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "1.25rem" }}>⏳</span>
                <div style={{ flex: 1 }}>
                  <p style={{ margin: 0, fontWeight: 600, fontSize: "0.9375rem" }}>
                    {pendingApprovals.length} pending approval{pendingApprovals.length !== 1 ? "s" : ""}
                  </p>
                  <p style={{ margin: "0.125rem 0 0", fontSize: "0.8125rem", color: "var(--muted)" }}>
                    Friday is waiting for your review before proceeding.
                  </p>
                </div>
                <Link href="/" className="btn btn-secondary btn-sm">Review in Chat →</Link>
              </div>
            </div>
          )}

          {/* Stat cards */}
          <div className="stat-card-row">
            <div className="stat-card">
              <div className="stat-card-label">Members</div>
              <div className="stat-card-value">{members.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Active OKRs</div>
              <div className="stat-card-value">{objectives.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">On Track</div>
              <div className="stat-card-value" style={{ color: "#16a34a" }}>
                {objectives.filter((o) => o.status === "on_track").length}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">At Risk</div>
              <div className="stat-card-value" style={{ color: "#b45309" }}>
                {objectives.filter((o) => o.status === "at_risk" || o.status === "behind").length}
              </div>
            </div>
          </div>

          {/* Quick actions */}
          <div className="card">
            <div className="card-header">Quick Actions</div>
            <div className="card-body" style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <Link
                href={`/?new_chat=1&workspace_id=${id}&workspace_name=${encodeURIComponent(workspace.name)}`}
                className="btn btn-primary"
                style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}
              >
                💬 Ask Friday about {workspace.name}
              </Link>
              <Link href={`/okrs?workspace_id=${id}`} className="btn btn-secondary">
                🎯 View OKRs
              </Link>
              <Link href="/documents" className="btn btn-secondary">
                📄 Documents
              </Link>
              <Link href="/analytics" className="btn btn-secondary">
                📊 Analytics
              </Link>
            </div>
          </div>

          {/* OKR health */}
          {objectives.length > 0 && (
            <div className="card">
              <div className="card-header">
                OKR Health
                <Link href={`/okrs?workspace_id=${id}`} className="btn btn-ghost btn-sm">View all →</Link>
              </div>
              <table className="data-table">
                <thead><tr><th>Objective</th><th>Level</th><th>Status</th><th>Progress</th></tr></thead>
                <tbody>
                  {objectives.slice(0, 5).map((o) => (
                    <tr key={o.obj_id}>
                      <td><Link href={`/okrs/${o.obj_id}`} style={{ color: "var(--accent)", textDecoration: "none" }}>{o.title}</Link></td>
                      <td><span className="badge badge-neutral">{o.level}</span></td>
                      <td><span className={STATUS_BADGE[o.status] || "badge badge-neutral"}>{statusLabel(o.status)}</span></td>
                      <td><div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}><ProgressBar value={o.progress} /><span style={{ fontSize: "0.75rem" }}>{Math.round(o.progress * 100)}%</span></div></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Workspace details */}
          <div className="card">
            <div className="card-header">Details</div>
            <div className="card-body">
              <table className="data-table">
                <tbody>
                  <tr><td style={{ width: "30%", color: "var(--muted)", fontWeight: 600 }}>Type</td><td><span className="badge badge-info">{workspace.type}</span></td></tr>
                  <tr><td style={{ color: "var(--muted)", fontWeight: 600 }}>Owner</td><td>{workspace.owner}</td></tr>
                  <tr><td style={{ color: "var(--muted)", fontWeight: 600 }}>Visibility</td><td>{workspace.visibility}</td></tr>
                  <tr><td style={{ color: "var(--muted)", fontWeight: 600 }}>Created</td><td>{workspace.created_at.slice(0, 10)}</td></tr>
                  {workspace.slug && <tr><td style={{ color: "var(--muted)", fontWeight: 600 }}>Slug</td><td style={{ fontFamily: "monospace", fontSize: "0.875rem" }}>{workspace.slug}</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Projects tab */}
      {activeTab === "projects" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.875rem" }}>
              Projects group documents, conversations, and tasks within this workspace.
            </p>
            <button className="btn btn-primary btn-sm" onClick={() => setShowAddProject(true)}>
              + New Project
            </button>
          </div>

          {showAddProject && (
            <div className="card">
              <div className="card-header">New Project</div>
              <form onSubmit={addProject}>
                <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div className="form-group">
                    <label className="form-label">Name *</label>
                    <input
                      className="form-input"
                      value={newProjectForm.name}
                      onChange={(e) => setNewProjectForm({ ...newProjectForm, name: e.target.value })}
                      placeholder="e.g. Website Redesign"
                      required
                      autoFocus
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Description</label>
                    <input
                      className="form-input"
                      value={newProjectForm.description}
                      onChange={(e) => setNewProjectForm({ ...newProjectForm, description: e.target.value })}
                      placeholder="Optional"
                    />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                    <div className="form-group" style={{ margin: 0 }}>
                      <label className="form-label">Icon</label>
                      <input
                        className="form-input"
                        value={newProjectForm.icon}
                        onChange={(e) => setNewProjectForm({ ...newProjectForm, icon: e.target.value })}
                        placeholder="📁"
                      />
                    </div>
                    <div className="form-group" style={{ margin: 0 }}>
                      <label className="form-label">Color</label>
                      <input
                        type="color"
                        className="form-input"
                        style={{ padding: "0.25rem" }}
                        value={newProjectForm.color}
                        onChange={(e) => setNewProjectForm({ ...newProjectForm, color: e.target.value })}
                      />
                    </div>
                  </div>
                </div>
                <div className="card-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setShowAddProject(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={addingProject}>{addingProject ? "Creating…" : "Create Project"}</button>
                </div>
              </form>
            </div>
          )}

          {projects.length === 0 && !showAddProject ? (
            <div className="empty-state">
              <div className="empty-state-icon">📁</div>
              <p className="empty-state-title">No projects yet</p>
              <p className="empty-state-body">Create a project to group documents, conversations, and tasks together.</p>
              <button className="btn btn-primary" onClick={() => setShowAddProject(true)}>Create Project</button>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "0.75rem" }}>
              {projects.map((proj) => (
                <div key={proj.project_id} className="card" style={{ borderLeft: `3px solid ${proj.color}` }}>
                  <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "1.25rem" }}>{proj.icon}</span>
                      <span style={{ fontWeight: 600, fontSize: "0.9375rem", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{proj.name}</span>
                      {isAdmin(userRole) && (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: "var(--danger)", padding: "0 4px", fontSize: "0.75rem" }}
                          onClick={() => deleteProject(proj.project_id)}
                          title="Delete project"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                    {proj.description && (
                      <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--text-muted)", lineHeight: 1.4 }}>{proj.description}</p>
                    )}
                    <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Created {proj.created_at.slice(0, 10)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* OKRs tab */}
      {activeTab === "okrs" && (
        <div className="card">
          {objectives.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🎯</div>
              <p className="empty-state-title">No OKRs in this workspace</p>
              <p className="empty-state-body">Create an objective and assign it to this workspace.</p>
              <Link href="/okrs" className="btn btn-primary">Go to OKRs</Link>
            </div>
          ) : (
            <table className="data-table">
              <thead><tr><th>Objective</th><th>Level</th><th>Owner</th><th>Status</th><th>Progress</th></tr></thead>
              <tbody>
                {objectives.map((o) => (
                  <tr key={o.obj_id}>
                    <td><Link href={`/okrs/${o.obj_id}`} style={{ color: "var(--accent)", textDecoration: "none", fontWeight: 500 }}>{o.title}</Link></td>
                    <td><span className="badge badge-neutral">{o.level}</span></td>
                    <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{o.owner || "—"}</td>
                    <td><span className={STATUS_BADGE[o.status] || "badge badge-neutral"}>{statusLabel(o.status)}</span></td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <ProgressBar value={o.progress} />
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{Math.round(o.progress * 100)}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Members tab */}
      {activeTab === "members" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <div className="card">
            <div className="card-header">
              Members
              <button className="btn btn-secondary btn-sm" onClick={() => setShowAddMember((v) => !v)}>
                {showAddMember ? "Cancel" : "+ Add Member"}
              </button>
            </div>
            {showAddMember && (
              <div style={{ padding: "1rem", borderBottom: "1px solid var(--border)" }}>
                <form onSubmit={addMember} style={{ display: "flex", gap: "0.75rem", alignItems: "flex-end" }}>
                  <div className="form-group" style={{ margin: 0, flex: 1 }}>
                    <label className="form-label">User ID</label>
                    <input className="form-input" placeholder="alice@company.com" value={addMemberForm.user_id} onChange={(e) => setAddMemberForm({ ...addMemberForm, user_id: e.target.value })} required />
                  </div>
                  <div className="form-group" style={{ margin: 0 }}>
                    <label className="form-label">Role</label>
                    <select className="form-select" value={addMemberForm.role} onChange={(e) => setAddMemberForm({ ...addMemberForm, role: e.target.value })}>
                      <option value="viewer">Viewer</option>
                      <option value="editor">Editor</option>
                      <option value="owner">Owner</option>
                    </select>
                  </div>
                  <button type="submit" className="btn btn-primary" disabled={addingMember}>{addingMember ? "Adding…" : "Add"}</button>
                </form>
              </div>
            )}
            {members.length === 0 ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <div className="empty-state-icon">👥</div>
                <p className="empty-state-title">No members yet</p>
                <p className="empty-state-body">Add members to collaborate in this workspace.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead><tr><th>User</th><th>Role</th><th>Joined</th></tr></thead>
                <tbody>
                  {members.map((m) => (
                    <tr key={m.member_id}>
                      <td style={{ fontWeight: 500 }}>{m.user_id}</td>
                      <td><span className={ROLE_BADGE[m.role] || "badge badge-neutral"}>{m.role}</span></td>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>{m.joined_at.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </PageShell>
    </>
  );
}
