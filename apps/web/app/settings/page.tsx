"use client";

import { useEffect, useState } from "react";

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
    <main className="settings-page">
      <header className="settings-header">
        <div>
          <h1>Settings</h1>
          <p className="settings-subtitle">Integrations &amp; Configuration</p>
        </div>
      </header>

      {error && (
        <div className="settings-error" role="alert">
          {error}
        </div>
      )}

      <section className="settings-section" aria-labelledby="integrations-heading">
        <h2 id="integrations-heading" className="settings-section-title">
          Connected Integrations
        </h2>

        {loading ? (
          <p className="settings-loading">Loading integrations…</p>
        ) : integrations.length === 0 ? (
          <p className="settings-empty">No integrations configured.</p>
        ) : (
          <div className="settings-integrations-grid">
            {integrations.map((integration) => (
              <IntegrationCard key={integration.name} integration={integration} />
            ))}
          </div>
        )}
      </section>

      <section className="settings-section" aria-labelledby="credentials-heading">
        <h2 id="credentials-heading" className="settings-section-title">
          Active Credentials
        </h2>

        {loading ? (
          <p className="settings-loading">Loading credentials…</p>
        ) : credentials.length === 0 ? (
          <p className="settings-empty">No credentials stored.</p>
        ) : (
          <div className="settings-credentials-table-wrap">
            <table className="settings-credentials-table">
              <thead>
                <tr>
                  <th scope="col">Provider</th>
                  <th scope="col">Type</th>
                  <th scope="col">Created</th>
                </tr>
              </thead>
              <tbody>
                {credentials.map((cred) => (
                  <tr key={cred.credential_id}>
                    <td>
                      <span aria-hidden="true">{integrationIcon(cred.provider)}</span>{" "}
                      {cred.provider}
                    </td>
                    <td className="settings-cred-type">{cred.credential_type}</td>
                    <td className="settings-cred-date">
                      <time dateTime={cred.created_at}>
                        {new Date(cred.created_at).toLocaleDateString()}
                      </time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
