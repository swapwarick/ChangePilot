/**
 * Lightweight auth client that wraps our custom FastAPI JWT auth endpoints.
 * This is NOT using Better Auth's server adapter — our backend is FastAPI,
 * so we call our own /auth/* REST endpoints and manage tokens in localStorage.
 */

import { getApiBaseUrl } from "./api-config";

export interface AuthUser {
  id: string;
  username: string;
  email: string | null;
  tier: "guest" | "registered";
  storage_used_bytes: number;
  storage_quota_bytes: number;
  email_verified: boolean;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  user_id: string;
  username: string;
  tier: string;
}

// ---------------------------------------------------------------------------
// Token storage (localStorage — SSR safe)
// ---------------------------------------------------------------------------

const KEYS = {
  access: "cp_access_token",
  refresh: "cp_refresh_token",
  user: "cp_user",
} as const;

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEYS.access);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEYS.user);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function storeTokens(tokens: AuthTokens): void {
  localStorage.setItem(KEYS.access, tokens.access_token);
  localStorage.setItem(KEYS.refresh, tokens.refresh_token);
  // Set lightweight cookie for middleware auth-gating (no sensitive data)
  document.cookie = "cp_authed=1; path=/; SameSite=Lax; Max-Age=2592000";
}

function clearTokens(): void {
  localStorage.removeItem(KEYS.access);
  localStorage.removeItem(KEYS.refresh);
  localStorage.removeItem(KEYS.user);
  // Clear middleware cookie
  document.cookie = "cp_authed=; path=/; Max-Age=0";
}

function storeUser(user: AuthUser): void {
  localStorage.setItem(KEYS.user, JSON.stringify(user));
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBaseUrl()}/auth${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

async function authFetchAuthed(path: string, init?: RequestInit): Promise<Response> {
  const token = getAccessToken();
  return fetch(`${getApiBaseUrl()}/auth${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...init,
  });
}

// ---------------------------------------------------------------------------
// Auth actions
// ---------------------------------------------------------------------------

export async function signUp(
  username: string,
  password: string,
  email?: string
): Promise<AuthUser> {
  const res = await authFetch("/register", {
    method: "POST",
    body: JSON.stringify({ username, password, email: email || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Registration failed" }));
    throw new Error(err.detail || "Registration failed");
  }
  const tokens: AuthTokens = await res.json();
  storeTokens(tokens);
  return fetchMe();
}

export async function signIn(usernameOrEmail: string, password: string): Promise<AuthUser> {
  const res = await authFetch("/login", {
    method: "POST",
    body: JSON.stringify({ username: usernameOrEmail, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new Error(err.detail || "Invalid credentials");
  }
  const tokens: AuthTokens = await res.json();
  storeTokens(tokens);
  return fetchMe();
}

export async function signInAsGuest(): Promise<AuthUser> {
  const res = await authFetch("/guest", { method: "POST" });
  if (!res.ok) throw new Error("Failed to create guest session");
  const tokens: AuthTokens = await res.json();
  storeTokens(tokens);
  return fetchMe();
}

export async function signOut(): Promise<void> {
  try {
    await authFetchAuthed("/logout", { method: "POST" });
  } catch {
    // Best-effort — clear local state regardless
  } finally {
    clearTokens();
  }
}

export async function fetchMe(): Promise<AuthUser> {
  const res = await authFetchAuthed("/me");
  if (!res.ok) throw new Error("Not authenticated");
  const user: AuthUser = await res.json();
  storeUser(user);
  return user;
}

export async function refreshAccessToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  const refresh = localStorage.getItem(KEYS.refresh);
  if (!refresh) return null;
  const res = await authFetch("/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearTokens();
    return null;
  }
  const tokens: AuthTokens = await res.json();
  storeTokens(tokens);
  return tokens.access_token;
}

/** Build an Authorization header object for use with the API. */
export function authHeader(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Check whether the user is currently authenticated (has an access token). */
export function isAuthenticated(): boolean {
  return Boolean(getAccessToken());
}

/** Check backend config (e.g. is_cloud). */
export async function getAuthConfig(): Promise<{ is_cloud: boolean }> {
  const res = await fetch(`${getApiBaseUrl()}/auth/config`);
  if (!res.ok) return { is_cloud: false };
  return res.json();
}
