"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  clearAuth,
  fetchMe,
  getStoredUser,
  getToken,
  type NexaUser,
} from "@/lib/api";

function Icon({ name }: { name: "grid" | "agent" | "knowledge" | "team" | "invite" }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  if (name === "grid") {
    return (
      <svg {...common}>
        <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
        <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
        <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
        <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
      </svg>
    );
  }
  if (name === "agent") {
    return (
      <svg {...common}>
        <path d="M12 3l2.2 4.9 5.3.4-4 3.3 1.3 5.1L12 14.6 7.2 16.7l1.3-5.1-4-3.3 5.3-.4L12 3z" />
      </svg>
    );
  }
  if (name === "knowledge") {
    return (
      <svg {...common}>
        <path d="M4 6.5A2.5 2.5 0 016.5 4H20v14.5a1 1 0 01-1 1H6.5A2.5 2.5 0 014 17V6.5z" />
        <path d="M8 8h8M8 12h5" />
      </svg>
    );
  }
  if (name === "invite") {
    return (
      <svg {...common}>
        <path d="M4 12h13" />
        <path d="M13 6l6 6-6 6" />
        <path d="M4 5v14" strokeOpacity="0.5" />
      </svg>
    );
  }
  // team
  return (
    <svg {...common}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 19c.6-3.2 2.8-5 5.5-5s4.9 1.8 5.5 5" />
      <circle cx="17" cy="9.5" r="2.6" />
      <path d="M15 14.6c2.2.3 4 2 4.6 4.4" />
    </svg>
  );
}

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "grid" as const },
  { href: "/agents", label: "Agents", icon: "agent" as const },
  { href: "/knowledge", label: "Knowledge", icon: "knowledge" as const },
  { href: "/users", label: "Team", icon: "team" as const },
];

const ADMIN_NAV = [
  { href: "/invites", label: "Invites", icon: "invite" as const },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<NexaUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    const stored = getStoredUser();
    if (stored) setUser(stored);

    fetchMe()
      .then((me) => {
        setUser(me);
        setChecked(true);
      })
      .catch(() => {
        clearAuth();
        router.replace("/login");
      });
  }, [router]);

  if (!checked) {
    return (
      <div className="auth-wrap">
        <div className="auth-card" style={{ textAlign: "center" }}>
          <div className="brand-mark" style={{ margin: "0 auto 14px" }}>N</div>
          <div className="muted">Loading workspace…</div>
        </div>
      </div>
    );
  }

  const initial = user?.email?.charAt(0).toUpperCase() ?? "?";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="brand">
          <div className="brand-mark">N</div>
          <div>
            <div className="brand-name">NEXA</div>
            <div className="brand-sub">Workforce</div>
          </div>
        </Link>

        <nav className="nav">
          <div className="nav-label">Workspace</div>
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href} className={`nav-item${active ? " active" : ""}`}>
                <span className="nav-icon"><Icon name={item.icon} /></span>
                <span>{item.label}</span>
              </Link>
            );
          })}
          {user?.role === "admin" ? (
            <>
              <div className="nav-label">Admin</div>
              {ADMIN_NAV.map((item) => {
                const active = pathname?.startsWith(item.href);
                return (
                  <Link key={item.href} href={item.href} className={`nav-item${active ? " active" : ""}`}>
                    <span className="nav-icon"><Icon name={item.icon} /></span>
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </>
          ) : null}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="avatar">{initial}</div>
            <div style={{ minWidth: 0 }}>
              <div className="user-role">{user?.role ?? "member"}</div>
              <div className="user-email">{user?.email}</div>
            </div>
          </div>
          <button
            className="btn btn-ghost"
            style={{ width: "100%", justifyContent: "center" }}
            onClick={() => {
              clearAuth();
              router.replace("/login");
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  );
}
