"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export function UserMenu() {
  const { user, isGuest, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    setMounted(true);
  }, []);

  // Close on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  async function handleSignOut() {
    setOpen(false);
    await logout();
    router.push("/login");
  }

  if (!mounted || !user) return null;

  const usedMB = (user.storage_used_bytes / 1_048_576).toFixed(1);
  const quotaMB = user.storage_quota_bytes > 0 ? (user.storage_quota_bytes / 1_048_576).toFixed(0) : null;
  const usedPct = quotaMB
    ? Math.min(100, (user.storage_used_bytes / user.storage_quota_bytes) * 100)
    : 0;
  const isWarn = usedPct > 80;
  const initials = user.username.slice(0, 2);

  return (
    <div className="user-menu" ref={ref}>
      <button
        id="user-menu-btn"
        className="user-avatar-btn"
        onClick={() => setOpen((v) => !v)}
        aria-label="User menu"
        aria-expanded={open}
      >
        <span className="user-avatar">{initials}</span>
        <span className="hidden sm:inline">{user.username}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="user-dropdown" role="menu">
          {/* Header */}
          <div className="user-dropdown-header">
            <div className="user-dropdown-name">{user.username}</div>
            <div className="user-dropdown-tier">
              {isGuest ? "👤 Guest session" : "✅ Registered"}
            </div>

            {/* Storage bar — registered users only */}
            {!isGuest && quotaMB && (
              <div className="storage-bar-wrap">
                <div className="storage-bar-label">
                  <span>Storage</span>
                  <span>{usedMB} / {quotaMB} MB</span>
                </div>
                <div className="storage-bar-track">
                  <div
                    className={`storage-bar-fill ${isWarn ? "storage-bar-warn" : ""}`}
                    style={{ width: `${usedPct}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Guest upgrade banner */}
          {isGuest && (
            <Link href="/register" onClick={() => setOpen(false)}>
              <div className="guest-upgrade-banner">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                </svg>
                Upgrade · Save results (30 MB free)
              </div>
            </Link>
          )}

          {/* Sign out */}
          <button
            id="user-signout-btn"
            className="user-dropdown-signout"
            onClick={handleSignOut}
            role="menuitem"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            {isGuest ? "End session & clear data" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
