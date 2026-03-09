export type UserRole = "member" | "intermediate" | "advanced" | "admin";
export const AUTH_CHANGED_EVENT = "stockgo-auth-changed";

export interface CurrentUser {
  id: number;
  email: string;
  full_name?: string | null;
  role?: UserRole;
}

const ROLE_RANK: Record<UserRole, number> = {
  member: 1,
  intermediate: 2,
  advanced: 3,
  admin: 4,
};

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("stockgo_token");
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    window.localStorage.setItem("stockgo_token", token);
  } else {
    window.localStorage.removeItem("stockgo_token");
  }
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function hasMinRole(role: string | undefined, required: UserRole): boolean {
  if (!role) return false;
  const current = ROLE_RANK[(role as UserRole) || "member"] || 0;
  const target = ROLE_RANK[required] || 0;
  return current >= target;
}

export async function fetchCurrentUser(apiBase: string, token: string): Promise<CurrentUser | null> {
  try {
    const resp = await fetch(`${apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return null;
    return (await resp.json()) as CurrentUser;
  } catch {
    return null;
  }
}

export async function authedJson<T>(url: string, token: string): Promise<T> {
  const resp = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) {
    const err = new Error(`HTTP_${resp.status}`) as Error & { status?: number };
    err.status = resp.status;
    throw err;
  }
  return (await resp.json()) as T;
}
