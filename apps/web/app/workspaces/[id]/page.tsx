"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PageShell } from "@/components/page-shell";

const API = "http://localhost:8000";

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

export default function WorkspaceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState("overview");
  const [addMemberForm, setAddMemberForm] = useState({ user_id: "", role: "editor" });
  const [addingMember, setAddingMember] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);

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

  useEffect(() => { load(); loadOKRs(); }, [id]);

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

  return (
    <PageShell
      title={`${workspace.icon || "🗂️"} ${workspace.name}`}
      subtitle={workspace.description || workspace.type}
      breadcrumbs={[{ label: "Workspaces", href: "/workspaces" }, { label: workspace.name }]}
      tabs={[
        { id: "overview", label: "Overview" },
        { id: "okrs", label: `OKRs (${objectives.length})` },
        { id: "members", label: `Members (${members.length})` },
      ]}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
      {/* Overview tab */}
      {activeTab === "overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div className="stat-card-row">
            <div className="stat-card">
              <div className="stat-card-label">Members</div>
              <div className="stat-card-value">{members.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">OKRs</div>
              <div className="stat-card-value">{objectives.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">On Track</div>
              <div className="stat-card-value" style={{ color: "#16a34a" }}>
                {objectives.filter((o) => o.status === "on_track").length}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-label">Visibility</div>
              <div style={{ fontSize: "1rem", fontWeight: 600, marginTop: "0.25rem" }}>{workspace.visibility}</div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">Workspace Details</div>
            <div className="card-body">
              <table className="data-table">
                <tbody>
                  <tr><td style={{ width: "30%", color: "var(--text-muted)", fontWeight: 600 }}>Type</td><td><span className="badge badge-info">{workspace.type}</span></td></tr>
                  <tr><td style={{ color: "var(--text-muted)", fontWeight: 600 }}>Owner</td><td>{workspace.owner}</td></tr>
                  <tr><td style={{ color: "var(--text-muted)", fontWeight: 600 }}>Visibility</td><td>{workspace.visibility}</td></tr>
                  <tr><td style={{ color: "var(--text-muted)", fontWeight: 600 }}>Created</td><td>{workspace.created_at.slice(0, 10)}</td></tr>
                  {workspace.slug && <tr><td style={{ color: "var(--text-muted)", fontWeight: 600 }}>Slug</td><td style={{ fontFamily: "monospace", fontSize: "0.875rem" }}>{workspace.slug}</td></tr>}
                </tbody>
              </table>
            </div>
          </div>

          {objectives.length > 0 && (
            <div className="card">
              <div className="card-header">
                Recent OKRs
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
  );
}
