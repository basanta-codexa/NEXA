/* JWT-aware API client for the NEXA backend. */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";

const TOKEN_KEY = "nexa.token";
const USER_KEY = "nexa.user";

export type NexaUser = {
  id: number;
  email: string;
  tenant_id: number;
  role: string;
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): NexaUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as NexaUser) : null;
  } catch {
    return null;
  }
}

export function storeAuth(token: string, user: NexaUser) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  authRequired = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (authRequired) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  if (options.body && !headers.has("Content-Type") && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!res.ok) {
    const detail =
      (body && typeof body === "object" && "detail" in body && typeof (body as { detail: unknown }).detail === "string"
        ? (body as { detail: string }).detail
        : null) ?? `Request failed (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

/* ---------- Meta ---------- */
export const health = () => apiFetch<Record<string, unknown>>("/health", {}, false);

/* ---------- Auth ---------- */
export async function login(email: string, password: string) {
  const data = await apiFetch<{ access_token: string; user: NexaUser }>(
    "/users/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
    false,
  );
  storeAuth(data.access_token, data.user);
  return data.user;
}

export async function fetchMe() {
  return apiFetch<NexaUser>("/users/me");
}

/* ---------- Tenant signup (invite-only) ---------- */
export async function registerTenant(input: {
  name: string;
  description: string;
  adminEmail: string;
  adminPassword: string;
  inviteCode: string;
}) {
  return apiFetch<{
    message: string;
    tenant: { id: number; name: string; description: string };
    admin_user?: { id: number; email: string; role: string };
  }>(
    "/tenants",
    {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        description: input.description,
        admin_email: input.adminEmail,
        admin_password: input.adminPassword,
        invite_code: input.inviteCode,
      }),
    },
    false,
  );
}

/* ---------- Agents ---------- */
export type Agent = {
  id: number;
  name: string;
  role: string;
  language: string;
  description?: string | null;
  model_name?: string | null;
  system_prompt?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  top_p?: number | null;
  status: "draft" | "active" | "paused" | "archived";
  tools?: string[] | null;
  tenant_id: number;
};

export const listAgents = () => apiFetch<{ agents: Agent[] }>("/agents");
export const getAgent = (id: number) => apiFetch<Agent>(`/agents/${id}`);
export const createAgent = (agent: Record<string, unknown>) =>
  apiFetch<Agent>("/agents", { method: "POST", body: JSON.stringify(agent) });
export const updateAgent = (id: number, agent: Record<string, unknown>) =>
  apiFetch<Agent>(`/agents/${id}`, { method: "PUT", body: JSON.stringify(agent) });
export const deleteAgent = (id: number) =>
  apiFetch<{ message: string }>(`/agents/${id}`, { method: "DELETE" });
export const setAgentStatus = (id: number, status: Agent["status"]) =>
  apiFetch<Agent>(`/agents/${id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
export const runAgent = (id: number, message: string, sessionId?: string) =>
  apiFetch<Record<string, unknown>>(`/agents/${id}/run`, {
    method: "POST",
    body: JSON.stringify({ message, ...(sessionId ? { session_id: sessionId } : {}) }),
  });

/* ---------- Documents & knowledge ---------- */
export type DocumentItem = {
  id: number;
  title: string;
  tenant_id: number;
  created_at: string;
};

export type SearchResult = {
  chunk_id: number;
  document_id: number;
  title: string;
  chunk_index: number;
  content: string;
  similarity: number;
};

export const listDocuments = (limit = 50, offset = 0) =>
  apiFetch<{ documents: DocumentItem[] }>(`/documents?limit=${limit}&offset=${offset}`);

export const createDocument = (title: string, content: string) =>
  apiFetch<DocumentItem>("/documents", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<DocumentItem>("/documents/upload", { method: "POST", body: form });
}

export const deleteDocument = (id: number) =>
  apiFetch<{ message: string }>(`/documents/${id}`, { method: "DELETE" });

export const searchKnowledge = (query: string, topK = 5) =>
  apiFetch<SearchResult[]>(
    `/documents/search?query=${encodeURIComponent(query)}&top_k=${topK}`,
    { method: "POST" },
  );

/* ---------- Users ---------- */
export type TenantUser = {
  id: number;
  email: string;
  role: string;
  tenant_id: number;
};

export const listUsers = () => apiFetch<{ users: TenantUser[] }>("/users");

export const createUser = (email: string, password: string, role: string) =>
  apiFetch<{ message: string; user: TenantUser }>("/users", {
    method: "POST",
    body: JSON.stringify({ email, password, role }),
  });
