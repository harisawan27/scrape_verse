import {
  AlertEvent,
  AuthResponse,
  User,
  Watch,
  WatchOverview,
  WatchPlan,
  WatchPlanPreviewResponse,
  WatchRun,
  WatchSummary,
  WatchUpdateInput,
} from "../types";

const rawBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

const TOKEN_STORAGE_KEY = "web_radar_auth_token";

class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (token) {
      localStorage.setItem(TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  } catch (err) {
    console.error("Failed to set auth token in storage", err);
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${cleanEndpoint}`;
  const method = (options.method || "GET").toUpperCase();
  const isIdempotentGet = method === "GET";
  const maxRetries = isIdempotentGet ? 2 : 0;

  const token = getStoredToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let lastError: any = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      if (attempt > 0) {
        // Cold-start backoff: 500ms, 1200ms
        await sleep(attempt === 1 ? 500 : 1200);
      }

      const res = await fetch(url, {
        ...options,
        headers,
      });

      if (res.status === 204) {
        return {} as T;
      }

      // If backend is waking up (502/503/504) on a GET request, retry
      if (
        isIdempotentGet &&
        attempt < maxRetries &&
        (res.status === 502 || res.status === 503 || res.status === 504)
      ) {
        continue;
      }

      const data = await res.json().catch(() => null);

      if (!res.ok) {
        const message =
          data?.detail ||
          (typeof data?.message === "string" ? data.message : null) ||
          `HTTP ${res.status}: ${res.statusText}`;
        throw new ApiError(message, res.status, data);
      }

      return data as T;
    } catch (err: any) {
      lastError = err;
      if (err instanceof ApiError) {
        // Do not retry client errors (4xx)
        if (err.status >= 400 && err.status < 500) {
          throw err;
        }
      }
      // If write request or final attempt, throw
      if (!isIdempotentGet || attempt === maxRetries) {
        if (err instanceof ApiError) {
          throw err;
        }
        throw new ApiError(
          err?.message || "Failed to communicate with Web Radar backend",
          0,
          err
        );
      }
    }
  }

  throw (
    lastError ||
    new ApiError("Failed to communicate with Web Radar backend", 0)
  );
}

export const api = {
  getToken: getStoredToken,
  setToken: setStoredToken,

  /**
   * Fetch currently authenticated user session from backend.
   */
  async getMe(): Promise<User> {
    return request<User>("/v1/auth/me");
  },


  /**
   * Ensure a user exists (legacy fallback).
   */
  async ensureUser(email: string = "demo@webradar.io"): Promise<User> {
    return request<User>("/v1/users/ensure", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  /**
   * Translates a natural language instruction + URL into a structured plan preview.
   */
  async previewWatchPlan(
    message: string,
    url?: string,
    timezone: string = "Asia/Karachi"
  ): Promise<WatchPlanPreviewResponse> {
    return request<WatchPlanPreviewResponse>("/v1/watch-plans/preview", {
      method: "POST",
      body: JSON.stringify({
        message,
        url: url && url.trim().length > 0 ? url.trim() : null,
        timezone,
      }),
    });
  },

  /**
   * Persists a Watch directly from a validated plan preview.
   */
  async createWatchFromPlan(userId: string, plan: WatchPlan): Promise<Watch> {
    return request<Watch>("/v1/watches/from-plan", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        plan,
      }),
    });
  },

  /**
   * List all Watches for the current user (summary cards with latest values).
   */
  async getWatches(userId?: string): Promise<WatchSummary[]> {
    const query = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    const res = await request<WatchSummary[]>(`/v1/watches${query}`).catch(() => []);
    return Array.isArray(res) ? res : [];
  },

  /**
   * Retrieve aggregate overview for a specific Watch.
   */
  async getWatchOverview(watchId: string): Promise<WatchOverview> {
    const res = await request<WatchOverview>(
      `/v1/watches/${encodeURIComponent(watchId)}/overview`
    );
    if (!res) {
      throw new ApiError("Watch not found", 404);
    }
    return res;
  },

  /**
   * Retrieve global cross-watch activity feed.
   */
  async getActivity(
    userId?: string,
    limit: number = 50
  ): Promise<AlertEvent[]> {
    const query = userId
      ? `?user_id=${encodeURIComponent(userId)}&limit=${limit}`
      : `?limit=${limit}`;
    const res = await request<AlertEvent[]>(`/v1/activity${query}`).catch(() => []);
    return Array.isArray(res) ? res : [];
  },

  /**
   * Update Watch configuration (cadence, status, monitoring spec).
   */
  async updateWatch(
    watchId: string,
    data: WatchUpdateInput
  ): Promise<Watch> {
    return request<Watch>(`/v1/watches/${encodeURIComponent(watchId)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  /**
   * Trigger an immediate manual run for a Watch.
   */
  async triggerWatchRun(
    watchId: string,
    executeNow: boolean = true
  ): Promise<WatchRun> {
    return request<WatchRun>(
      `/v1/watches/${encodeURIComponent(watchId)}/runs?execute_now=${executeNow}`,
      {
        method: "POST",
      }
    );
  },

  /**
   * Delete a Watch.
   */
  async deleteWatch(watchId: string): Promise<void> {
    return request<void>(`/v1/watches/${encodeURIComponent(watchId)}`, {
      method: "DELETE",
    });
  },

  /**
   * Trigger scheduler tick to evaluate due watches.
   */
  async triggerSchedulerTick(): Promise<WatchRun[]> {
    return request<WatchRun[]>("/v1/scheduler/tick", {
      method: "POST",
    });
  },

  /**
   * Check backend health.
   */
  async checkHealth(): Promise<{ status: string }> {
    return request<{ status: string }>("/health");
  },
};

export { ApiError };
