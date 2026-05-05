import { config } from "@/lib/config";
import { useAuthStore } from "@/lib/store/auth";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type ApiInit = Omit<RequestInit, "body"> & {
  body?: unknown;
  /** When set to a FormData, body will be sent as multipart. */
  form?: FormData;
  searchParams?: Record<string, string | number | boolean | null | undefined>;
  skipAuth?: boolean;
};

const refreshLock: { promise: Promise<string | null> | null } = { promise: null };

async function refreshAccessToken(): Promise<string | null> {
  const auth = useAuthStore.getState();
  if (!auth.refreshToken) return null;
  if (refreshLock.promise) return refreshLock.promise;
  refreshLock.promise = (async () => {
    try {
      const res = await fetch(`${config.apiUrl}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: auth.refreshToken }),
      });
      if (!res.ok) {
        auth.clear();
        return null;
      }
      const data = (await res.json()) as {
        access_token: string;
        refresh_token: string;
      };
      auth.setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    } finally {
      refreshLock.promise = null;
    }
  })();
  return refreshLock.promise;
}

export async function api<T = unknown>(
  path: string,
  init: ApiInit = {}
): Promise<T> {
  const url = new URL(
    path.startsWith("http") ? path : `${config.apiUrl}/api/v1${path}`
  );
  if (init.searchParams) {
    for (const [k, v] of Object.entries(init.searchParams)) {
      if (v !== null && v !== undefined && v !== "") {
        url.searchParams.set(k, String(v));
      }
    }
  }
  const headers = new Headers(init.headers);
  if (!init.skipAuth) {
    const token = useAuthStore.getState().accessToken;
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  let body: BodyInit | undefined;
  if (init.form) {
    body = init.form;
  } else if (init.body !== undefined) {
    body = JSON.stringify(init.body);
    headers.set("Content-Type", "application/json");
  }
  let res = await fetch(url, { ...init, headers, body });

  if (res.status === 401 && !init.skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(url, { ...init, headers, body });
    }
  }
  if (!res.ok) {
    let payload: any = null;
    try {
      payload = await res.json();
    } catch {
      /* ignore */
    }
    const err =
      payload?.error ??
      ({ code: `http_${res.status}`, message: res.statusText } as const);
    throw new ApiError(res.status, err.code, err.message, payload?.error?.details);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// Convenience namespaces (typed at call-sites)
export const apiClient = {
  get: <T>(path: string, init?: ApiInit) =>
    api<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: ApiInit) =>
    api<T>(path, { ...init, method: "POST", body }),
  patch: <T>(path: string, body?: unknown, init?: ApiInit) =>
    api<T>(path, { ...init, method: "PATCH", body }),
  delete: <T>(path: string, init?: ApiInit) =>
    api<T>(path, { ...init, method: "DELETE" }),
  postForm: <T>(path: string, form: FormData, init?: ApiInit) =>
    api<T>(path, { ...init, method: "POST", form }),
};
