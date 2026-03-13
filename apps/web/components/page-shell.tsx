"use client";

import React from "react";
import Link from "next/link";

// LeftRail nav items — mirrors workspace.tsx navigation
const NAV_ITEMS = [
  { href: "/", icon: "💬", label: "Chat" },
  { href: "/processes", icon: "⚙️", label: "Processes" },
  { href: "/documents", icon: "📄", label: "Documents" },
  { href: "/analytics", icon: "📊", label: "Analytics" },
  { href: "/okrs", icon: "🎯", label: "OKRs" },
  { href: "/workspaces", icon: "🗂️", label: "Workspaces" },
  { href: "/settings", icon: "⚙️", label: "Settings" },
];

interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface PageShellProps {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
  breadcrumbs?: BreadcrumbItem[];
  headerActions?: React.ReactNode;
  tabs?: { label: string; id: string }[];
  activeTab?: string;
  onTabChange?: (id: string) => void;
  rightRail?: React.ReactNode;
}

export function PageShell({
  children,
  title,
  subtitle,
  breadcrumbs,
  headerActions,
  tabs,
  activeTab,
  onTabChange,
  rightRail,
}: PageShellProps) {
  const [currentPath, setCurrentPath] = React.useState("");

  React.useEffect(() => {
    setCurrentPath(window.location.pathname);
  }, []);

  return (
    <div className="page-shell">
      {/* Left Rail */}
      <nav
        style={{
          width: "220px",
          flexShrink: 0,
          background: "var(--surface)",
          borderRight: "1px solid var(--border)",
          display: "flex",
          flexDirection: "column",
          padding: "1rem 0",
          gap: "0.125rem",
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: "0.5rem 1rem 1.25rem",
            fontWeight: 700,
            fontSize: "1.125rem",
            color: "var(--accent)",
            letterSpacing: "-0.02em",
          }}
        >
          Friday
        </div>

        {/* Nav Links */}
        {NAV_ITEMS.map((item) => {
          const isActive = currentPath === item.href || (item.href !== "/" && currentPath.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.625rem",
                padding: "0.5rem 1rem",
                fontSize: "0.875rem",
                fontWeight: isActive ? 600 : 400,
                color: isActive ? "var(--accent)" : "var(--text-muted)",
                background: isActive ? "rgba(var(--accent-rgb, 99,102,241), 0.08)" : "transparent",
                borderRadius: "0.375rem",
                margin: "0 0.5rem",
                textDecoration: "none",
                transition: "background 0.15s, color 0.15s",
              }}
            >
              <span style={{ fontSize: "1rem" }}>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Main content area */}
      <div className="page-content">
        {/* Header */}
        <header className="page-header">
          <div className="page-header-left">
            {breadcrumbs && breadcrumbs.length > 0 && (
              <nav className="breadcrumb">
                {breadcrumbs.map((crumb, i) => (
                  <React.Fragment key={i}>
                    {i > 0 && <span className="breadcrumb-sep">/</span>}
                    {crumb.href ? (
                      <Link href={crumb.href} className="breadcrumb-item">
                        {crumb.label}
                      </Link>
                    ) : (
                      <span className="breadcrumb-current">{crumb.label}</span>
                    )}
                  </React.Fragment>
                ))}
              </nav>
            )}
            <h1 className="page-header-title">{title}</h1>
            {subtitle && <p className="page-header-subtitle">{subtitle}</p>}
          </div>
          {headerActions && (
            <div className="page-header-actions">{headerActions}</div>
          )}
        </header>

        {/* Tabs (optional) */}
        {tabs && tabs.length > 0 && (
          <div className="tab-bar">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                className={`tab-item${activeTab === tab.id ? " active" : ""}`}
                onClick={() => onTabChange?.(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}

        {/* Page body */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          <main className="page-main">{children}</main>
          {rightRail && <aside className="panel">{rightRail}</aside>}
        </div>
      </div>
    </div>
  );
}
