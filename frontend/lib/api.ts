export type Project = {
  id: number;
  name: string;
};

export type Conversation = {
  id: number;
  project_id: number;
  title: string;
  updated_at: string;
};

export type ChatMessage = {
  id: number | string;
  role: "user" | "assistant";
  content: string;
  created_at?: string;
  source_document_ids?: number[];
};

export type ChatResponse = {
  reply: string;
  conversation_id: number;
  provider: string;
  model: string;
  sources: number[];
};

type Paginated<T> = {
  results: T[];
  next: string | null;
};

function csrfToken() {
  if (typeof document === "undefined") return "";
  return document.cookie
    .split(";")
    .map((entry) => entry.trim())
    .find((entry) => entry.startsWith("csrftoken="))
    ?.slice("csrftoken=".length) ?? "";
}

function localApiUrl(url: string) {
  if (url.startsWith("/")) return url;
  const parsed = new URL(url);
  return `${parsed.pathname}${parsed.search}`;
}

export async function api<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(localApiUrl(url), {
    credentials: "same-origin",
    ...init,
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.method && init.method !== "GET" ? { "X-CSRFToken": csrfToken() } : {}),
      ...init.headers,
    },
  });

  if (response.status === 401) {
    window.location.assign(new URL("/login/", window.location.origin).toString());
    throw new Error("Please sign in again.");
  }

  const contentType = response.headers.get("content-type") ?? "";
  const data = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : "The request could not be completed. Check project access and provider configuration.",
    );
  }

  return data as T;
}

export async function listAll<T>(initialUrl: string): Promise<T[]> {
  const results: T[] = [];
  let url: string | null = initialUrl;

  while (url) {
    const page: Paginated<T> = await api<Paginated<T>>(url);
    results.push(...page.results);
    url = page.next;
  }

  return results;
}

export async function signOut() {
  await api<never>("/logout/", { method: "POST" });
  window.location.assign(new URL("/login/", window.location.origin).toString());
}
