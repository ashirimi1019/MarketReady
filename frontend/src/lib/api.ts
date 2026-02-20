import { ApiError } from "./errors";

export { ApiError } from "./errors";

export const API_BASE =
  (process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

function getCandidateApiBases(): string[] {
  const bases = [API_BASE];
  if (API_BASE.endsWith("/api")) {
    bases.push(API_BASE.slice(0, -4));
  }
  return [...new Set(bases.filter(Boolean))];
}

type RefreshResponse = {
  user_id: string;
  auth_token?: string | null;
  refresh_token?: string | null;
};

function withAuthHeaders(headers?: HeadersInit): Headers {
  const merged = new Headers(headers ?? {});
  if (typeof window !== "undefined") {
    const token = window.localStorage.getItem("mp_auth_token");
    const username = window.localStorage.getItem("mp_username");
    if (token && !merged.has("X-Auth-Token")) {
      merged.set("X-Auth-Token", token);
    }
    if (username && !merged.has("X-User-Id")) {
      merged.set("X-User-Id", username);
    }
  }
  return merged;
}

export function getAuthHeaders(headers?: HeadersInit): Headers {
  return withAuthHeaders(headers);
}

async function tryRefreshSession(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const refreshToken = window.localStorage.getItem("mp_refresh_token");
  const username = window.localStorage.getItem("mp_username");
  if (!refreshToken || !username) return false;

  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = (await res.json()) as RefreshResponse;
    if (!data.auth_token) return false;
    window.localStorage.setItem("mp_auth_token", data.auth_token);
    if (data.refresh_token) {
      window.localStorage.setItem("mp_refresh_token", data.refresh_token);
    }
    return true;
  } catch {
    return false;
  }
}

export async function apiGet<T>(path: string, headers?: HeadersInit): Promise<T> {
  const bases = getCandidateApiBases();
  let res: Response | null = null;
  for (const base of bases) {
    res = await fetch(`${base}${path}`, {
      cache: "no-store",
      headers: withAuthHeaders(headers),
    });
    if (res.status === 404 && base.endsWith("/api") && bases.length > 1) {
      continue;
    }
    if (res.status === 401) {
      const refreshed = await tryRefreshSession();
      if (refreshed) {
        res = await fetch(`${base}${path}`, {
          cache: "no-store",
          headers: withAuthHeaders(headers),
        });
      }
    }
    break;
  }
  if (!res) {
    throw new ApiError(500, "API request failed: no base URL available");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}

export async function apiSend<T>(
  path: string,
  options: RequestInit
): Promise<T> {
  const bases = getCandidateApiBases();
  let res: Response | null = null;
  for (const base of bases) {
    res = await fetch(`${base}${path}`, {
      ...options,
      headers: withAuthHeaders(options.headers),
    });
    if (res.status === 404 && base.endsWith("/api") && bases.length > 1) {
      continue;
    }
    if (res.status === 401) {
      const refreshed = await tryRefreshSession();
      if (refreshed) {
        res = await fetch(`${base}${path}`, {
          ...options,
          headers: withAuthHeaders(options.headers),
        });
      }
    }
    break;
  }
  if (!res) {
    throw new ApiError(500, "API request failed: no base URL available");
  }
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body);
  }
  return res.json() as Promise<T>;
}
