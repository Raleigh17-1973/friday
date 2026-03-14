"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────────────────────────────
type Integration = { name: string; connected: boolean; stub: boolean; message: string };
type Credential = { credential_id: string; provider: string; credential_type: string; created_at: string };

type Member = {
  member_id: string;
  name: string;
  email: string;
  role: "developer" | "dev_admin" | "tool_admin" | "member";
  created_at: string;
};

type OKRConfig = {
  reminder_cadence: string;    // weekly | biweekly | monthly
  sync_cadence: string;        // daily | weekly | disabled
  reminder_day: string;        // monday | tuesday | ...
  reminder_time: string;       // HH:MM
};

// ── Constants ─────────────────────────────────────────────────────────────
const DEFAULT_OKR_CONFIG: OKRConfig = {
  reminder_cadence: "weekly",
  sync_cadence: "daily",
  reminder_day: "monday",
  reminder_time: "09:00",
};

const KNOWN_INTEGRATIONS = [
  { name: "Slack",      icon: "💬", category: "Messaging",    description: "Post OKR updates, alerts, and Friday responses to Slack channels" },
  { name: "Google Workspace", icon: "🔵", category: "Productivity", description: "Connect Gmail, Google Drive, and Google Calendar" },
  { name: "Microsoft 365",    icon: "🟦", category: "Productivity", description: "Connect Outlook, OneDrive, and Teams" },
  { name: "Jira",       icon: "🎯", category: "Engineering",  description: "Link Jira issues to initiatives and auto-sync progress" },
  { name: "Confluence", icon: "📝", category: "Engineering",  description: "Import Confluence documents and OKR templates" },
  { name: "Tableau",    icon: "📊", category: "Analytics",    description: "Pull KPI data from Tableau dashboards automatically" },
  { name: "OpenAI",     icon: "🤖", category: "AI APIs",      description: "Configure GPT-4 as a Friday AI backend" },
  { name: "Claude (Anthropic)", icon: "🧠", category: "AI APIs", description: "Configure Claude as a Friday AI backend (already active)" },
  { name: "Salesforce", icon: "💼", category: "CRM",          description: "Sync sales metrics and CRM data to KPIs" },
  { name: "HubSpot",    icon: "🔶", category: "CRM",          description: "Pull marketing and sales KPIs from HubSpot" },
];

const ROLE_LABELS: Record<string, string> = {
  developer: "Developer",
  dev_admin: "Dev Admin",
  tool_admin: "Tool Admin",
  member: "Member",
};

const ROLE_DESCRIPTIONS: Record<string, string> = {
  developer: "Full access including QA Registry and Settings",
  dev_admin: "Admin access including Settings and member management",
  tool_admin: "Can manage Settings and members, no QA Registry access",
  member: "Standard access to Chat, OKRs, Workspaces, and Documents",
};

// ── Helpers ────────────────────────────────────────────────────────────────
function integrationIcon(name: string): string {
  const found = KNOWN_INTEGRATIONS.find((i) => i.name.toLowerCase().includes(name.toLowerCase()) || name.toLowerCase().includes(i.name.toLowerCase().split(" ")[0]));
  return found?.icon ?? "🔌";
}

function loadOKRConfig(): OKRConfig {
  if (typeof window === "undefined") return DEFAULT_OKR_CONFIG;
  try {
    const raw = localStorage.getItem("friday_okr_config");
    return raw ? { ...DEFAULT_OKR_CONFIG, ...JSON.parse(raw) } : DEFAULT_OKR_CONFIG;
  } catch {
    return DEFAULT_OKR_CONFIG;
  }
}

function saveOKRConfig(cfg: OKRConfig) {
  localStorage.setItem("friday_okr_config", JSON.stringify(cfg));
}

function loadUserRole(): string {
  if (typeof window === "undefined") return "member";
  return localStorage.getItem("friday_user_role") ?? "member";
}

function saveUserRole(role: string) {
  localStorage.setItem("friday_user_role", role);
  window.dispatchEvent(new Event("friday_role_changed"));
}

// ── Integration Card ───────────────────────────────────────────────────────
function IntegrationCard({
  integration,
  knownInfo,
  onConnect,
}: {
  integration?: Integration;
  knownInfo: typeof KNOWN_INTEGRATIONS[number];
  onConnect: (name: string) => void;
}) {
  const connected = integration?.connected ?? false;
  const stub = integration?.stub ?? false;

  return (
    <div className="settings-integration-card" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <span style={{ fontSize: "1.5rem" }}>{knownInfo.icon}</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{knownInfo.name}</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{knownInfo.category}</div>
        </div>
        {connected ? (
          <span className="badge badge-success">Connected</span>
        ) : stub ? (
          <span className="badge badge-neutral">Stub</span>
        ) : (
          <span className="badge badge-neutral">Not Connected</span>
        )}
      </div>
      <p style={{ fontSize: "0.8125rem", color: "var(--text-muted)", margin: 0 }}>{knownInfo.description}</p>
      {integration?.message && (
        <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", margin: 0, fontStyle: "italic" }}>{integration.message}</p>
      )}
      {!connected && (
        <button
          className="btn btn-secondary btn-sm"
          style={{ alignSelf: "flex-start" }}
          onClick={() => onConnect(knownInfo.name)}
        >
          Configure →
        </button>
      )}
    </div>
  );
}

// ── Member Row ─────────────────────────────────────────────────────────────
function MemberRow({ member, onRoleChange, onRemove }: {
  member: Member;
  onRoleChange: (id: string, role: string) => void;
  onRemove: (id: string) => void;
}) {
  return (
    <tr>
      <td>
        <div style={{ fontWeight: 500, fontSize: "0.875rem" }}>{member.name}</div>
        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{member.email}</div>
      </td>
      <td>
        <select
          className="form-select"
          value={member.role}
          onChange={(e) => onRoleChange(member.member_id, e.target.value)}
          style={{ fontSize: "0.82rem" }}
        >
          <option value="member">Member</option>
          <option value="tool_admin">Tool Admin</option>
          <option value="dev_admin">Dev Admin</option>
          <option value="developer">Developer</option>
        </select>
      </td>
      <td style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>
        {new Date(member.created_at).toLocaleDateString()}
      </td>
      <td>
        <button
          className="btn btn-ghost btn-sm"
          style={{ color: "#dc2626", fontSize: "0.75rem" }}
          onClick={() => onRemove(member.member_id)}
        >
          Remove
        </button>
      </td>
    </tr>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────
export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState("integrations");
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [okrConfig, setOkrConfigState] = useState<OKRConfig>(DEFAULT_OKR_CONFIG);
  const [okrSaved, setOkrSaved] = useState(false);
  const [currentRole, setCurrentRole] = useState("member");
  const [members, setMembers] = useState<Member[]>([]);
  const [showAddMember, setShowAddMember] = useState(false);
  const [newMember, setNewMember] = useState({ name: "", email: "", role: "member" });
  const [connectModal, setConnectModal] = useState<string | null>(null);

  useEffect(() => {
    setOkrConfigState(loadOKRConfig());
    setCurrentRole(loadUserRole());

    // Load members from localStorage
    try {
      const raw = localStorage.getItem("friday_members");
      if (raw) setMembers(JSON.parse(raw));
    } catch { /* empty */ }

    Promise.all([
      fetch(`${BACKEND}/integrations/status`).then((r) => r.ok ? r.json() : { integrations: [] }),
      fetch(`${BACKEND}/credentials`).then((r) => r.ok ? r.json() : { credentials: [] }),
    ])
      .then(([intData, credData]: [unknown, unknown]) => {
        const intObj = intData as { integrations?: Integration[] };
        const credObj = credData as { credentials?: Credential[] };
        setIntegrations(Array.isArray(intObj?.integrations) ? intObj.integrations : []);
        setCredentials(Array.isArray(credObj?.credentials) ? credObj.credentials : []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function handleOKRConfigChange(field: keyof OKRConfig, value: string) {
    setOkrConfigState((prev) => ({ ...prev, [field]: value }));
    setOkrSaved(false);
  }

  function handleOKRConfigSave() {
    saveOKRConfig(okrConfig);
    setOkrSaved(true);
    setTimeout(() => setOkrSaved(false), 2000);
  }

  function handleRoleChange(role: string) {
    setCurrentRole(role);
    saveUserRole(role);
  }

  function handleMemberRoleChange(memberId: string, role: string) {
    const updated = members.map((m) => m.member_id === memberId ? { ...m, role: role as Member["role"] } : m);
    setMembers(updated);
    localStorage.setItem("friday_members", JSON.stringify(updated));
  }

  function handleMemberRemove(memberId: string) {
    const updated = members.filter((m) => m.member_id !== memberId);
    setMembers(updated);
    localStorage.setItem("friday_members", JSON.stringify(updated));
  }

  function handleAddMember(e: React.FormEvent) {
    e.preventDefault();
    if (!newMember.name.trim() || !newMember.email.trim()) return;
    const member: Member = {
      member_id: `mem_${Date.now()}`,
      name: newMember.name.trim(),
      email: newMember.email.trim(),
      role: newMember.role as Member["role"],
      created_at: new Date().toISOString(),
    };
    const updated = [...members, member];
    setMembers(updated);
    localStorage.setItem("friday_members", JSON.stringify(updated));
    setNewMember({ name: "", email: "", role: "member" });
    setShowAddMember(false);
  }

  const tabs = [
    { id: "integrations", label: "Integrations" },
    { id: "okr_config", label: "OKR Configuration" },
    { id: "members", label: "Members" },
    { id: "account", label: "Account & Role" },
  ];

  return (
    <PageShell
      title="Settings"
      subtitle="Configuration, integrations, and team management"
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

        {/* ── Integrations Tab ───────────────────────────────────────────── */}
        {activeTab === "integrations" && (
          <>
            <div className="card">
              <div className="card-header">Available Integrations</div>
              <div className="card-body">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: "1rem" }}>
                  {KNOWN_INTEGRATIONS.map((ki) => {
                    const live = integrations.find((i) => i.name.toLowerCase().includes(ki.name.toLowerCase().split(" ")[0]));
                    return (
                      <IntegrationCard
                        key={ki.name}
                        integration={live}
                        knownInfo={ki}
                        onConnect={(name) => setConnectModal(name)}
                      />
                    );
                  })}
                </div>
              </div>
            </div>

            {credentials.length > 0 && (
              <div className="card">
                <div className="card-header">Active Credentials</div>
                <div className="card-body" style={{ padding: 0 }}>
                  <table className="data-table">
                    <thead>
                      <tr><th>Provider</th><th>Type</th><th>Created</th></tr>
                    </thead>
                    <tbody>
                      {credentials.map((cred) => (
                        <tr key={cred.credential_id}>
                          <td>
                            <span aria-hidden="true">{integrationIcon(cred.provider)}</span>{" "}
                            {cred.provider}
                          </td>
                          <td><span className="badge badge-neutral">{cred.credential_type}</span></td>
                          <td style={{ color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                            {new Date(cred.created_at).toLocaleDateString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {/* ── OKR Configuration Tab ──────────────────────────────────────── */}
        {activeTab === "okr_config" && (
          <>
            <div className="card">
              <div className="card-header">
                Update Reminders
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: 400 }}>
                  When to prompt KR owners to log progress
                </span>
              </div>
              <div className="card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "1rem" }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.85rem", fontWeight: 600 }}>
                    Reminder Frequency
                    <select
                      className="form-select"
                      value={okrConfig.reminder_cadence}
                      onChange={(e) => handleOKRConfigChange("reminder_cadence", e.target.value)}
                    >
                      <option value="weekly">Weekly</option>
                      <option value="biweekly">Bi-weekly</option>
                      <option value="monthly">Monthly</option>
                      <option value="disabled">Disabled</option>
                    </select>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                      How often to prompt KR owners
                    </span>
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.85rem", fontWeight: 600 }}>
                    Reminder Day
                    <select
                      className="form-select"
                      value={okrConfig.reminder_day}
                      onChange={(e) => handleOKRConfigChange("reminder_day", e.target.value)}
                      disabled={okrConfig.reminder_cadence === "disabled"}
                    >
                      <option value="monday">Monday</option>
                      <option value="tuesday">Tuesday</option>
                      <option value="wednesday">Wednesday</option>
                      <option value="thursday">Thursday</option>
                      <option value="friday">Friday</option>
                    </select>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                      Day of week for reminders
                    </span>
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.85rem", fontWeight: 600 }}>
                    Reminder Time
                    <input
                      className="form-input"
                      type="time"
                      value={okrConfig.reminder_time}
                      onChange={(e) => handleOKRConfigChange("reminder_time", e.target.value)}
                      disabled={okrConfig.reminder_cadence === "disabled"}
                    />
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontWeight: 400 }}>
                      Time of day (your local timezone)
                    </span>
                  </label>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                Data Sync
                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontWeight: 400 }}>
                  Auto-pull KPI values from connected integrations
                </span>
              </div>
              <div className="card-body">
                <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "1rem", alignItems: "start" }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "0.85rem", fontWeight: 600 }}>
                    Sync Frequency
                    <select
                      className="form-select"
                      value={okrConfig.sync_cadence}
                      onChange={(e) => handleOKRConfigChange("sync_cadence", e.target.value)}
                    >
                      <option value="daily">Daily</option>
                      <option value="weekly">Weekly</option>
                      <option value="disabled">Disabled (manual only)</option>
                    </select>
                  </label>
                  <div style={{ padding: "0.75rem", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", fontSize: "0.8125rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                    When sync is enabled, Friday will automatically pull updated values from Jira, Tableau,
                    Salesforce, and other connected integrations and update the corresponding KPIs.
                    You can always trigger a manual sync from any KR.
                  </div>
                </div>
              </div>
            </div>

            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}>
              <button className="btn btn-primary" onClick={handleOKRConfigSave}>
                {okrSaved ? "✓ Saved" : "Save OKR Config"}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => { setOkrConfigState(DEFAULT_OKR_CONFIG); setOkrSaved(false); }}
              >
                Reset to defaults
              </button>
            </div>
          </>
        )}

        {/* ── Members Tab ────────────────────────────────────────────────── */}
        {activeTab === "members" && (
          <>
            <div className="card">
              <div className="card-header">
                Team Members
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setShowAddMember((v) => !v)}
                >
                  {showAddMember ? "Cancel" : "+ Add Member"}
                </button>
              </div>
              <div className="card-body" style={{ padding: showAddMember ? "1rem" : 0 }}>
                {showAddMember && (
                  <form onSubmit={handleAddMember} style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto auto", gap: "0.5rem", alignItems: "end", marginBottom: "1rem", padding: "1rem", background: "var(--bg)", borderRadius: "0.5rem", border: "1px solid var(--border)" }}>
                    <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
                      Name
                      <input className="form-input" placeholder="Full name" value={newMember.name} onChange={(e) => setNewMember({ ...newMember, name: e.target.value })} required />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
                      Email
                      <input className="form-input" type="email" placeholder="email@company.com" value={newMember.email} onChange={(e) => setNewMember({ ...newMember, email: e.target.value })} required />
                    </label>
                    <label style={{ display: "flex", flexDirection: "column", gap: "3px", fontSize: "0.82rem", fontWeight: 600 }}>
                      Role
                      <select className="form-select" value={newMember.role} onChange={(e) => setNewMember({ ...newMember, role: e.target.value })}>
                        <option value="member">Member</option>
                        <option value="tool_admin">Tool Admin</option>
                        <option value="dev_admin">Dev Admin</option>
                        <option value="developer">Developer</option>
                      </select>
                    </label>
                    <button type="submit" className="btn btn-primary btn-sm" style={{ height: "fit-content" }}>Add</button>
                  </form>
                )}
                {members.length === 0 ? (
                  <div className="empty-state" style={{ padding: "2rem" }}>
                    <div className="empty-state-icon">👥</div>
                    <p className="empty-state-title">No members added yet</p>
                    <p className="empty-state-body">Add team members to control their access levels.</p>
                  </div>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr><th>Member</th><th>Role</th><th>Added</th><th></th></tr>
                    </thead>
                    <tbody>
                      {members.map((m) => (
                        <MemberRow
                          key={m.member_id}
                          member={m}
                          onRoleChange={handleMemberRoleChange}
                          onRemove={handleMemberRemove}
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header">Role Permissions</div>
              <div className="card-body">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Role</th>
                      <th>Chat & OKRs</th>
                      <th>Workspaces</th>
                      <th>Settings</th>
                      <th>QA Registry</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(["member", "tool_admin", "dev_admin", "developer"] as const).map((role) => (
                      <tr key={role}>
                        <td><span className="badge badge-neutral">{ROLE_LABELS[role]}</span></td>
                        <td>✅</td>
                        <td>✅</td>
                        <td>{role === "member" ? "❌" : "✅"}</td>
                        <td>{role === "developer" || role === "dev_admin" ? "✅" : "❌"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* ── Account & Role Tab ─────────────────────────────────────────── */}
        {activeTab === "account" && (
          <div className="card">
            <div className="card-header">Your Access Role</div>
            <div className="card-body">
              <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", marginBottom: "1rem", lineHeight: 1.6 }}>
                Your role controls which parts of Friday you can access. Set this to match your actual access level.
                This setting is stored locally in your browser.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {(["member", "tool_admin", "dev_admin", "developer"] as const).map((role) => (
                  <label
                    key={role}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "0.75rem",
                      padding: "0.875rem 1rem",
                      border: `2px solid ${currentRole === role ? "var(--accent)" : "var(--border)"}`,
                      borderRadius: "0.5rem",
                      cursor: "pointer",
                      background: currentRole === role ? "var(--accent-subtle, #eef2ff)" : "var(--bg)",
                    }}
                  >
                    <input
                      type="radio"
                      name="role"
                      value={role}
                      checked={currentRole === role}
                      onChange={() => handleRoleChange(role)}
                      style={{ marginTop: "3px" }}
                    />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: "0.9rem" }}>{ROLE_LABELS[role]}</div>
                      <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)", marginTop: "2px" }}>{ROLE_DESCRIPTIONS[role]}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Connect Integration Modal ────────────────────────────────────── */}
      {connectModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200 }}>
          <div style={{ background: "var(--surface-1)", borderRadius: "0.75rem", padding: "1.5rem", minWidth: 380, maxWidth: 480, width: "100%" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
              <h2 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700 }}>Configure {connectModal}</h2>
              <button onClick={() => setConnectModal(null)} style={{ background: "none", border: "none", cursor: "pointer", fontSize: "1rem", color: "var(--text-muted)" }}>✕</button>
            </div>
            <div style={{ padding: "1rem", background: "var(--bg)", border: "1px solid var(--border)", borderRadius: "0.5rem", fontSize: "0.875rem", color: "var(--text-muted)", lineHeight: 1.6, marginBottom: "1rem" }}>
              <strong>OAuth / API key setup for {connectModal} is coming soon.</strong>
              <br /><br />
              To configure this integration manually today, add your API credentials to the{" "}
              <code style={{ background: "var(--surface-2)", padding: "1px 4px", borderRadius: "3px", fontSize: "0.8em" }}>.env</code>{" "}
              file on the server and restart the API. Full UI-based OAuth flow will be available in a future release.
            </div>
            <button className="btn btn-secondary" onClick={() => setConnectModal(null)}>Close</button>
          </div>
        </div>
      )}
    </PageShell>
  );
}
