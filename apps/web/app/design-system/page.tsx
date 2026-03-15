"use client";

import { PageShell } from "@/components/page-shell";

// ── Token data ────────────────────────────────────────────────────────────

const COLOR_TOKENS = [
  { name: "--accent",         value: "#6366f1", label: "Accent / Primary" },
  { name: "--bg",             value: "#f9fafb", label: "Page Background" },
  { name: "--surface",        value: "#ffffff", label: "Surface" },
  { name: "--surface-1",      value: "#f3f4f6", label: "Surface Raised" },
  { name: "--border",         value: "#e5e7eb", label: "Border" },
  { name: "--text",           value: "#111827", label: "Text Primary" },
  { name: "--text-muted",     value: "#6b7280", label: "Text Muted" },
  { name: "--success",        value: "#16a34a", label: "Success" },
  { name: "--danger",         value: "#dc2626", label: "Danger" },
  { name: "--warning",        value: "#d97706", label: "Warning" },
];

const TYPE_SCALE = [
  { label: "2xl / 1.5rem",  style: { fontSize: "1.5rem",    fontWeight: 600, lineHeight: 1.2 }, sample: "Section Heading" },
  { label: "xl / 1.25rem",  style: { fontSize: "1.25rem",   fontWeight: 600, lineHeight: 1.3 }, sample: "Page Title" },
  { label: "lg / 1.125rem", style: { fontSize: "1.125rem",  fontWeight: 500, lineHeight: 1.4 }, sample: "Card Heading" },
  { label: "base / 1rem",   style: { fontSize: "1rem",      fontWeight: 400, lineHeight: 1.5 }, sample: "Body text. Used for all default prose and labels." },
  { label: "sm / 0.875rem", style: { fontSize: "0.875rem",  fontWeight: 400, lineHeight: 1.5 }, sample: "Secondary text, descriptions, and table rows." },
  { label: "xs / 0.75rem",  style: { fontSize: "0.75rem",   fontWeight: 400, lineHeight: 1.5 }, sample: "Meta labels, timestamps, badge text." },
  { label: "2xs / 0.675rem",style: { fontSize: "0.675rem",  fontWeight: 700, lineHeight: 1.5, textTransform: "uppercase" as const, letterSpacing: "0.07em" }, sample: "SECTION LABELS" },
];

const SPACING = [
  { label: "--space-1", px: 4  },
  { label: "--space-2", px: 8  },
  { label: "--space-3", px: 12 },
  { label: "--space-4", px: 16 },
  { label: "--space-5", px: 24 },
  { label: "--space-6", px: 32 },
  { label: "--space-7", px: 48 },
];

const RADII = [
  { label: "--radius-s", value: "4px" },
  { label: "--radius-m", value: "8px" },
  { label: "--radius-l", value: "12px" },
];

const ELEVATION_LEVELS = [
  { label: "Flat",      shadow: "none",                                              bg: "#f3f4f6" },
  { label: "Resting",   shadow: "0 1px 3px rgba(0,0,0,0.08)",                       bg: "#fff" },
  { label: "Raised",    shadow: "0 4px 12px rgba(0,0,0,0.10)",                      bg: "#fff" },
  { label: "Floating",  shadow: "0 8px 24px rgba(0,0,0,0.12), 0 2px 6px rgba(0,0,0,0.06)", bg: "#fff" },
];

// ── Section component ─────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ds-section">
      <div className="ds-section-title">{title}</div>
      {children}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function DesignSystemPage() {
  return (
    <PageShell title="Design System" breadcrumbs={[{ label: "Design System" }]}>
      <div className="ds-page">

        {/* Color Tokens */}
        <Section title="Color Tokens">
          <div className="ds-swatch-grid">
            {COLOR_TOKENS.map(({ name, value, label }) => (
              <div key={name} className="ds-swatch" title={name}>
                <div
                  className="ds-swatch-color"
                  style={{ background: `var(${name}, ${value})` }}
                />
                <span className="ds-swatch-label">{name}</span>
                <span className="ds-swatch-label" style={{ opacity: 0.6 }}>{label}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Typography Scale */}
        <Section title="Typography Scale">
          <div className="ds-type-scale">
            {TYPE_SCALE.map(({ label, style, sample }) => (
              <div key={label} className="ds-type-row">
                <span className="ds-type-label">{label}</span>
                <span style={{ ...style, color: "var(--text, #111827)" }}>{sample}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Spacing Scale */}
        <Section title="Spacing Scale (8px base grid)">
          <div className="ds-space-grid">
            {SPACING.map(({ label, px }) => (
              <div key={label} className="ds-space-bar">
                <span className="ds-swatch-label">{px}px</span>
                <div className="ds-space-block" style={{ height: px }} />
                <span className="ds-swatch-label">{label}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Border Radius */}
        <Section title="Border Radius">
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
            {RADII.map(({ label, value }) => (
              <div key={label} className="ds-swatch">
                <div
                  className="ds-swatch-color"
                  style={{ background: "var(--accent, #6366f1)", borderRadius: value, opacity: 0.7 }}
                />
                <span className="ds-swatch-label">{label}</span>
                <span className="ds-swatch-label" style={{ opacity: 0.6 }}>{value}</span>
              </div>
            ))}
          </div>
        </Section>

        {/* Elevation */}
        <Section title="Elevation / Shadow">
          <div className="ds-elevation-grid">
            {ELEVATION_LEVELS.map(({ label, shadow, bg }) => (
              <div
                key={label}
                className="ds-elev-card"
                style={{ boxShadow: shadow, background: bg, border: shadow === "none" ? "1px solid var(--border, #e5e7eb)" : "none" }}
              >
                {label}
              </div>
            ))}
          </div>
        </Section>

        {/* Buttons */}
        <Section title="Buttons">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", alignItems: "center" }}>
            <button className="btn btn-primary">Primary</button>
            <button className="btn btn-secondary">Secondary</button>
            <button className="btn btn-ghost">Ghost</button>
            <button className="btn btn-danger">Danger</button>
            <button className="btn btn-primary btn-sm">Primary SM</button>
            <button className="btn btn-secondary btn-sm">Secondary SM</button>
            <button className="btn btn-ghost btn-sm">Ghost SM</button>
            <button className="btn btn-danger btn-sm">Danger SM</button>
            <button className="btn btn-primary" disabled>Disabled</button>
          </div>
        </Section>

        {/* Badges */}
        <Section title="Badges">
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
            <span className="badge badge-success">Success</span>
            <span className="badge badge-warning">Warning</span>
            <span className="badge badge-danger">Danger</span>
            <span className="badge badge-neutral">Neutral</span>
            <span className="badge">Default</span>
          </div>
        </Section>

        {/* Cards */}
        <Section title="Cards">
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
            <div className="card" style={{ width: 220 }}>
              <div className="card-header">Card Title</div>
              <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", margin: 0 }}>
                Default card with header. Used for content groupings across all pages.
              </p>
            </div>
            <div className="card card-clickable" style={{ width: 220 }}>
              <div className="card-header">Clickable Card</div>
              <p style={{ fontSize: "0.875rem", color: "var(--text-muted)", margin: 0 }}>
                Hover to see the raised state applied on interactive cards.
              </p>
            </div>
          </div>
        </Section>

        {/* Form Inputs */}
        <Section title="Form Inputs">
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxWidth: 360 }}>
            <input className="form-input" type="text" placeholder="Text input" />
            <input className="form-input" type="text" placeholder="Disabled input" disabled />
            <textarea className="form-input" rows={3} placeholder="Textarea" />
            <select className="form-input">
              <option>Select option 1</option>
              <option>Select option 2</option>
            </select>
          </div>
        </Section>

        {/* Status Dot */}
        <Section title="Status Indicators">
          <div style={{ display: "flex", gap: "1.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="status-dot-wrap">
                <span className="status-dot status-dot-green" />
              </span>
              <span style={{ fontSize: "0.875rem" }}>Connected</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="status-dot-wrap">
                <span className="status-dot status-dot-amber" />
              </span>
              <span style={{ fontSize: "0.875rem" }}>Reconnecting</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span className="status-dot-wrap">
                <span className="status-dot status-dot-red" />
              </span>
              <span style={{ fontSize: "0.875rem" }}>Offline</span>
            </div>
          </div>
        </Section>

        {/* Segmented Control */}
        <Section title="Segmented Control">
          <div className="segmented-control" role="radiogroup">
            {(["ASK", "PLAN", "ACT"] as const).map((label, i) => (
              <button
                key={label}
                type="button"
                className={`segmented-btn${i === 0 ? " segmented-btn-active" : ""}`}
              >
                {label}
              </button>
            ))}
          </div>
        </Section>

        {/* Data Table */}
        <Section title="Data Table">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: "Q2 Engineering OKR", status: "On track", created: "Mar 1" },
                { name: "Customer Onboarding SOP", status: "Needs attention", created: "Feb 14" },
                { name: "Weekly Digest", status: "Complete", created: "Mar 10" },
              ].map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td>
                    <span className={`badge ${row.status === "On track" || row.status === "Complete" ? "badge-success" : "badge-warning"}`}>
                      {row.status}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>{row.created}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm">View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        {/* Empty State */}
        <Section title="Empty State">
          <div className="empty-state">
            <p className="empty-state-title">No items yet</p>
            <p className="empty-state-body">Items will appear here once created.</p>
            <button className="btn btn-primary btn-sm">Create your first item</button>
          </div>
        </Section>

      </div>
    </PageShell>
  );
}
