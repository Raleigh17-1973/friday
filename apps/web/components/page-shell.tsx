"use client";

import React from "react";
import Link from "next/link";
import {
  BarChart2,
  Bell,
  CheckSquare,
  ClipboardCheck,
  FileText,
  Folders,
  GitBranch,
  Home,
  LayoutDashboard,
  MessageSquare,
  Palette,
  PenSquare,
  Settings,
  Target,
  Workflow,
  FlaskConical,
  type LucideIcon,
} from "lucide-react";

// ── Role helpers ─────────────────────────────────────────────────────────────
type UserRole = "member" | "tool_admin" | "dev_admin" | "developer";

function loadUserRole(): UserRole {
  if (typeof window === "undefined") return "member";
  return (localStorage.getItem("friday_user_role") as UserRole) ?? "member";
}

// ── Nav items — must mirror workspace.tsx NAV_ITEMS (plus Chat entry) ────
type NavItem = {
  href: string;
  icon: LucideIcon;
  label: string;
  children?: NavItem[];
  /** Roles that can see this item. Undefined = visible to all. */
  roles?: UserRole[];
};

const NAV_ITEMS: NavItem[] = [
  { href: "/home",       icon: Home,           label: "Home"           },
  { href: "/",           icon: MessageSquare,  label: "Chat"           },
  { href: "/tasks",      icon: CheckSquare,    label: "Tasks"          },
  { href: "/approvals",  icon: ClipboardCheck, label: "Approvals"      },
  { href: "/processes",  icon: Workflow,       label: "Process Library" },
  { href: "/documents",  icon: FileText,       label: "Documents"       },
  { href: "/analytics",  icon: BarChart2,      label: "Analytics"       },
  { href: "/okrs",       icon: Target,         label: "OKRs",           children: [
    { href: "/okrs/setup",                icon: Settings,        label: "Setup"          },
    { href: "/okrs/plan",                 icon: PenSquare,       label: "Plan"           },
    { href: "/okrs/alignment",            icon: GitBranch,       label: "Alignment"      },
    { href: "/okrs/dashboards/executive", icon: LayoutDashboard, label: "Exec Dashboard" },
  ]},
  { href: "/workspaces", icon: Folders,        label: "Workspaces"      },
  { href: "/qa",             icon: FlaskConical,   label: "QA Registry",    roles: ["developer", "dev_admin"] },
  { href: "/settings",       icon: Settings,       label: "Settings",       roles: ["developer", "dev_admin", "tool_admin"] },
  { href: "/design-system",  icon: Palette,        label: "Design System",  roles: ["developer", "dev_admin"] },
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
  const [userRole, setUserRole] = React.useState<UserRole>("member");
  const [unreadCount, setUnreadCount] = React.useState(0);
  const BACKEND_URL = process.env.NEXT_PUBLIC_FRIDAY_BACKEND_URL ?? "http://127.0.0.1:8000";

  React.useEffect(() => {
    setCurrentPath(window.location.pathname);
    setUserRole(loadUserRole());

    const onRoleChange = () => setUserRole(loadUserRole());
    window.addEventListener("friday_role_changed", onRoleChange);
    return () => window.removeEventListener("friday_role_changed", onRoleChange);
  }, []);

  // Poll unread notification count every 60 seconds
  React.useEffect(() => {
    const fetchCount = () => {
      fetch(`${BACKEND_URL}/notifications/unread-count?recipient_id=user-1`)
        .then((r) => r.ok ? r.json() : { count: 0 })
        .then((d: { count?: number }) => setUnreadCount(d.count ?? 0))
        .catch(() => {});
    };
    fetchCount();
    const timer = setInterval(fetchCount, 60_000);
    return () => clearInterval(timer);
  }, [BACKEND_URL]);

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
        {/* Logo + notification bell */}
        <div
          style={{
            padding: "0.5rem 1rem 1.25rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span style={{ fontWeight: 700, fontSize: "1.125rem", color: "var(--accent)", letterSpacing: "-0.02em" }}>
            Friday
          </span>
          <Link href="/home" className="notif-bell" title="Notifications" aria-label={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}>
            <Bell size={16} strokeWidth={1.75} />
            {unreadCount > 0 && (
              <span className="notif-badge">{unreadCount > 99 ? "99+" : unreadCount}</span>
            )}
          </Link>
        </div>

        {/* Nav Links */}
        {NAV_ITEMS.filter(({ roles }) => !roles || roles.includes(userRole)).map(({ href, icon: Icon, label, children }) => {
          const isActive = href === "/" ? currentPath === "/" : currentPath === href || currentPath.startsWith(href + "/") || currentPath === href;
          const isSectionActive = children ? currentPath.startsWith(href) : false;
          return (
            <React.Fragment key={href}>
              <Link
                href={href}
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
                <Icon size={16} strokeWidth={1.75} aria-hidden="true" color={isActive ? "var(--accent)" : "var(--text-muted)"} />
                {label}
              </Link>
              {/* Nested children — always visible when section is active */}
              {children && isSectionActive && children.map(child => {
                const childActive = currentPath === child.href || currentPath.startsWith(child.href + "/");
                const ChildIcon = child.icon;
                return (
                  <Link
                    key={child.href}
                    href={child.href}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.5rem",
                      padding: "0.3rem 1rem 0.3rem 2.5rem",
                      fontSize: "0.8rem",
                      fontWeight: childActive ? 600 : 400,
                      color: childActive ? "var(--accent)" : "var(--text-muted)",
                      background: childActive ? "rgba(var(--accent-rgb, 99,102,241), 0.08)" : "transparent",
                      borderRadius: "0.375rem",
                      margin: "0 0.5rem",
                      textDecoration: "none",
                      transition: "background 0.15s, color 0.15s",
                    }}
                  >
                    <ChildIcon size={13} strokeWidth={1.75} aria-hidden="true" color={childActive ? "var(--accent)" : "var(--text-muted)"} />
                    {child.label}
                  </Link>
                );
              })}
            </React.Fragment>
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
