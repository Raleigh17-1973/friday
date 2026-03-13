"use client";

import { useEffect, useState } from "react";
import { PageShell } from "@/components/page-shell";

const BACKEND = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

type Integration = {
  name: string;
  connected: boolean;
  stub: boolean;
  message: string;
};

type Credential = {
  credential_id: string;
  provider: string;
  credential_type: string;
  created_at: string;
};

const INTEGRATION_ICONS: Record<string, string> = {
  google: "🔵",
  slack: "💬",
  gmail: "📧",
  calendar: "📅",
  "google calendar": "📅",
  jira: "🎯",
  linear: "🔷",
  confluence: "📝",
  notion: "📓",
  salesforce: "💼",
  hubspot: "🔶",
};

function integrationIcon(name: string): string {
  const key = name.toLowerCase();
  for (const [k, icon] of Object.entries(INTEGRATION_ICONS)) {
    if (key.includes(k)) return icon;
  }
  return "🔌";
}

function IntegrationCard({ integration }: { integration: Integration }) {
  const icon = integrationIcon(integration.name);

  let statusLabel = "Not Connected";
  let statusClass = "settings-status-disconnected";
  if (integration.connected) {
    statusLabel = "Connected";
    statusClass = "settings-status-connected";
  } else if (integration.stub) {
    statusLabel = "Stub";
    statusClass = "settings-status-stub";
  }

  const handleConnect = () => {
    alert("OAuth setup coming soon");
  };

  return (
    <div className="settings-integration-card">
      <div className="settings-integration-top">
        <span className="settings-integration-icon" aria-hidden="true">
          {icon}
        </span>
        <div className="settings-integration-info">
          <span className="settings-integration-name">{integration.name}</span>
          <span className={`settings-status-badge ${statusClass}`}>{statusLabel}</span>
        </div>
      </div>
      {integration.message && (
        <p className="settings-integration-message">{integration.message}</p>
      )}
      {!integration.connected && (
        <button className="settings-connect-btn" onClick={handleConnect}>
          Connect
        </button>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${BACKEND}/integrations/status`).then((r) => r.json()),
      fetch(`${BACKEND}/credentials`).then((r) => r.json()),
    ])
      .then(([intData, credData]: [unknown, unknown]) => {
        const intObj = intData as { integrations?: Integration[] };
        const credObj = credData as { credentials?: Credential[] };
        setIntegrations(Array.isArray(intObj?.integrations) ? intObj.integrations : []);
        setCredentials(Array.isArray(credObj?.credentials) ? credObj.credentials : []);
      })
      .catch(() => {
        setError("Failed to load settings. Is the backend running?");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageShell title="Settings" subtitle="Integrations & Configuration">
      {error && (
        <div className="error-state" role="alert" style={{ padding: "1rem", marginBottom: "1rem" }}>
          ⚠️ {error}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div className="card">
          <div className="card-header">Connected Integrations</div>
          <div className="card-body">
            {loading ? (
              <div className="loading-skeleton">
                {[...Array(3)].map((_, i) => <div key={i} className="loading-skeleton-row" style={{ height: "4rem" }} />)}
              </div>
            ) : integrations.length === 0 ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <div className="empty-state-icon">🔌</div>
                <p className="empty-state-title">No integrations configured</p>
                <p className="empty-state-body">Connect Google Workspace, Slack, Jira, and more.</p>
              </div>
            ) : (
              <div className="settings-integrations-grid">
                {integrations.map((integration) => (
                  <IntegrationCard key={integration.name} integration={integration} />
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">Active Credentials</div>
          <div className="card-body" style={{ padding: 0 }}>
            {loading ? (
              <div className="loading-skeleton" style={{ padding: "1rem" }}>
                <div className="loading-skeleton-row" />
              </div>
            ) : credentials.length === 0 ? (
              <div className="empty-state" style={{ padding: "2rem" }}>
                <div className="empty-state-icon">🔑</div>
                <p className="empty-state-title">No credentials stored</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Type</th>
                    <th>Created</th>
                  </tr>
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
            )}
          </div>
        </div>
      </div>
    </PageShell>
  );
}
