"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
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
  org_id: string;
  visibility: string;
  archived: boolean;
  created_at: string;
}

const TYPE_BADGE: Record<string, string> = {
  company: "badge badge-purple",
  team: "badge badge-info",
  client: "badge badge-warning",
  initiative: "badge badge-success",
  confidential: "badge badge-danger",
  personal: "badge badge-neutral",
};

function NewWorkspaceModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    name: "",
    type: "team",
    description: "",
    icon: "🗂️",
    color: "#6366f1",
    visibility: "open",
    owner: "user",
    org_id: "default",
  });
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setSubmitError("");
    try {
      const res = await fetch(`${API}/workspaces`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(data.detail ?? `Server error (${res.status})`);
      }
      onCreated();
      onClose();
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create workspace. Is the API running?");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={onClose}
    >
      <div className="card" style={{ width: 440 }} onClick={(e) => e.stopPropagation()}>
        <div className="card-header">
          New Workspace
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit}>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div className="form-group">
              <label className="form-label">Name *</label>
              <input className="form-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Product Team, Q2 Launch" required />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Type</label>
                <select className="form-select" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                  <option value="team">Team</option>
                  <option value="company">Company</option>
                  <option value="client">Client</option>
                  <option value="initiative">Initiative</option>
                  <option value="confidential">Confidential</option>
                  <option value="personal">Personal</option>
                </select>
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Visibility</label>
                <select className="form-select" value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value })}>
                  <option value="open">Open</option>
                  <option value="closed">Closed</option>
                  <option value="private">Private</option>
                </select>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Icon</label>
                <input className="form-input" value={form.icon} onChange={(e) => setForm({ ...form, icon: e.target.value })} placeholder="🗂️" />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label className="form-label">Color</label>
                <input type="color" className="form-input" style={{ padding: "0.25rem" }} value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea className="form-textarea" rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What does this workspace contain?" />
            </div>
          </div>
          <div className="card-footer" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
            {submitError ? (
              <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--danger)", flex: 1 }}>
                ⚠ {submitError}
              </p>
            ) : <span />}
            <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
              <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Creating…" : "Create Workspace"}</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function RenameWorkspaceModal({
  workspace,
  onClose,
  onRenamed,
}: {
  workspace: Workspace;
  onClose: () => void;
  onRenamed: () => void;
}) {
  const [name, setName] = useState(workspace.name);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch(`${API}/workspaces/${workspace.workspace_id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({})) as { detail?: string };
        throw new Error(data.detail ?? "Failed to rename");
      }
      onRenamed();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to rename workspace");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
      onClick={onClose}
    >
      <div className="card" style={{ width: 400 }} onClick={(e) => e.stopPropagation()}>
        <div className="card-header">
          Rename Workspace
          <button className="btn btn-ghost btn-sm" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={submit}>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div className="form-group">
              <label className="form-label">New name</label>
              <input
                className="form-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                required
              />
            </div>
            {error && <p style={{ margin: 0, fontSize: "0.8125rem", color: "var(--danger)" }}>⚠ {error}</p>}
          </div>
          <div className="card-footer" style={{ display: "flex", justifyContent: "flex-end", gap: "0.5rem" }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function WorkspacesPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Workspace | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [userRole, setUserRole] = useState<UserRole>("member");

  useEffect(() => {
    setUserRole(loadUserRole());
    const onRoleChange = () => setUserRole(loadUserRole());
    window.addEventListener("friday_role_changed", onRoleChange);
    return () => window.removeEventListener("friday_role_changed", onRoleChange);
  }, []);

  async function handleDelete(workspaceId: string) {
    setDeleting(true);
    try {
      await fetch(`${API}/workspaces/${workspaceId}`, { method: "DELETE" });
      setDeleteTarget(null);
      await load();
    } catch {
      // silently retry
    } finally {
      setDeleting(false);
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/workspaces?org_id=default`);
      if (!res.ok) throw new Error("Failed to load workspaces");
      setWorkspaces(await res.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error loading workspaces");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  return (
    <PageShell
      title="Workspaces"
      subtitle="Organize your work into focused contexts"
      headerActions={
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>+ New Workspace</button>
      }
    >
      {loading ? (
        <div className="loading-skeleton">
          {[...Array(4)].map((_, i) => <div key={i} className="loading-skeleton-row" style={{ height: "7rem", borderRadius: "0.75rem" }} />)}
        </div>
      ) : error ? (
        <div className="error-state">
          <div style={{ fontSize: "1.5rem" }}>⚠️</div>
          <div>{error}</div>
          <button className="btn btn-secondary btn-sm" onClick={load}>Retry</button>
        </div>
      ) : workspaces.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">🗂️</div>
          <p className="empty-state-title">No workspaces yet</p>
          <p className="empty-state-body">Create a workspace to organize projects, conversations, and OKRs together.</p>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>Create Workspace</button>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1rem" }}>
          {workspaces.map((ws) => (
            <div key={ws.workspace_id} className="card" style={{ borderTop: `3px solid ${ws.color || "#6366f1"}` }}>
              <div className="card-body">
                <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", marginBottom: "0.75rem" }}>
                  <span style={{ fontSize: "1.75rem", flexShrink: 0 }}>{ws.icon || "🗂️"}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: "1rem", color: "var(--text)", marginBottom: "0.25rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {ws.name}
                    </div>
                    <span className={TYPE_BADGE[ws.type] || "badge badge-neutral"}>{ws.type}</span>
                  </div>
                </div>
                {ws.description && (
                  <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", lineHeight: 1.5, marginBottom: "1rem", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" as const }}>
                    {ws.description}
                  </p>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {ws.visibility}
                  </span>
                  <div style={{ display: "flex", gap: "0.375rem", alignItems: "center" }}>
                    {isAdmin(userRole) && (
                      <>
                        {deleteTarget === ws.workspace_id ? (
                          <span style={{ display: "flex", gap: "0.375rem", alignItems: "center" }}>
                            <span style={{ fontSize: "0.75rem", color: "var(--danger)" }}>Delete?</span>
                            <button
                              className="btn btn-sm"
                              style={{ background: "var(--danger)", color: "#fff", border: "none" }}
                              onClick={() => handleDelete(ws.workspace_id)}
                              disabled={deleting}
                            >
                              {deleting ? "…" : "Yes"}
                            </button>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => setDeleteTarget(null)}
                            >
                              No
                            </button>
                          </span>
                        ) : (
                          <>
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => setRenameTarget(ws)}
                              title="Rename workspace"
                            >
                              ✏
                            </button>
                            <button
                              className="btn btn-ghost btn-sm"
                              style={{ color: "var(--danger)" }}
                              onClick={() => setDeleteTarget(ws.workspace_id)}
                              title="Delete workspace"
                            >
                              🗑
                            </button>
                          </>
                        )}
                      </>
                    )}
                    <Link href={`/workspaces/${ws.workspace_id}`} className="btn btn-secondary btn-sm">
                      Open →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && <NewWorkspaceModal onClose={() => setShowModal(false)} onCreated={load} />}
      {renameTarget && (
        <RenameWorkspaceModal
          workspace={renameTarget}
          onClose={() => setRenameTarget(null)}
          onRenamed={load}
        />
      )}
    </PageShell>
  );
}
