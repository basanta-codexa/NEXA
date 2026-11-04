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

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: "◫" },
  { href: "/agents", label: "Agents", icon: "◎" },
  { href: "/knowledge", label: "Knowledge", icon: "▤" },
  { href: "/users", label: "Users", icon: "👥" },
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
          <div className="brand-mark" style={{ margin: "0 auto 12px" }}>N</div>
          <div className="muted">Loading NEXA…</div>
        </div>
      </div>
    );
  }

  const initials = user?.email?.charAt(0).toUpperCase() ?? "?";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/dashboard" className="brand">
          <div className="brand-mark">N</div>
          <div>
            <div className="brand-name">NEXA</div>
            <div className="brand-sub">AI WORKFORCE</div>
          </div>
        </Link>

        <nav className="nav">
          <div className="nav-label">Workspace</div>
          {NAV.map((item) => {
            const active = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-item${active ? " active" : ""}`}
              >
                <span className="nav-icon">{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="avatar">{initials}</div>
            <div>
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
