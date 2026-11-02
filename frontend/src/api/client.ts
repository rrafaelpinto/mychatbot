import type { Account, DocumentList, OwnerDocument, CandidateDetail, ChatAnswer, ChatMessage, GuestReply, GuestStatus, OwnerFact, OwnerFactList, OwnerProfile, OwnerProfileUpdate, CandidateList, ReviewAction, TokenResponse } from "./types";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

type Fetcher = typeof fetch;

export class ApiClient {
  private access: string | null = null;
  private csrf: string | null = null;
  private refreshInFlight: Promise<boolean> | null = null;
  private generation = 0;

  constructor(
    private readonly base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
    private readonly fetcher: Fetcher = (...args) => fetch(...args),
  ) {}

  private async send<T>(
    path: string,
    options: { method?: string; body?: unknown; auth?: boolean; csrf?: boolean; key?: string } = {},
    retry = true,
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined && !(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
    if (options.auth && this.access) headers.Authorization = "Bearer " + this.access;
    if (options.csrf && this.csrf) headers["X-CSRFToken"] = this.csrf;
    if (options.key) headers["Idempotency-Key"] = options.key;

    const response = await this.fetcher(new URL(path, this.base), {
      method: options.method || "GET",
      headers,
      credentials: "include",
      cache: "no-store",
      body: options.body instanceof FormData ? options.body : options.body === undefined ? undefined : JSON.stringify(options.body),
    });

    if (response.status === 401 && options.auth && retry && (await this.refresh())) {
      return this.send<T>(path, options, false);
    }
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null);
      const detail = typeof payload === "object" && payload !== null && "detail" in payload
        ? (payload as { detail: unknown }).detail
        : undefined;
      throw new ApiError(response.status, typeof detail === "string" ? detail : "Request could not be completed.");
    }
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }

  private async csrfToken(): Promise<void> {
    const result = await this.send<{ csrf_token: string }>("/api/v1/auth/csrf/");
    this.csrf = result.csrf_token;
  }

  async requestCode(email: string, registration?: { name: string; role: "candidate" | "recruiter" }): Promise<void> {
    await this.csrfToken();
    await this.send("/api/v1/auth/code/request/", { method: "POST", csrf: true, body: { email, ...registration } });
  }

  async verifyCode(email: string, code: string): Promise<void> {
    if (!this.csrf) await this.csrfToken();
    const token = await this.send<TokenResponse>("/api/v1/auth/code/verify/", { method: "POST", csrf: true, body: { email, code } });
    this.generation++;
    this.access = token.access;
  }

  account(): Promise<Account> { return this.send("/api/v1/me/", { auth: true }); }

  createOwnerProfile(changes: OwnerProfileUpdate): Promise<OwnerProfile> {
    return this.send("/api/v1/me/profile/", { method: "POST", auth: true, body: changes });
  }

  documents(page = 1): Promise<DocumentList> {
    return this.send("/api/v1/me/documents/?page=" + page, { auth: true });
  }

  uploadDocument(document: File): Promise<OwnerDocument> {
    const body = new FormData(); body.append("document", document);
    return this.send("/api/v1/me/documents/", { method: "POST", auth: true, body });
  }

  extractDocument(id: number): Promise<{ proposed_count: number }> {
    return this.send("/api/v1/me/documents/" + id + "/extract/", { method: "POST", auth: true });
  }

  publishProfile(published: boolean): Promise<OwnerProfile> {
    return this.send("/api/v1/me/profile/publication/", { method: "POST", auth: true, body: { published } });
  }

  editFact(id: number, content: string, version: string): Promise<OwnerFact> {
    return this.send("/api/v1/me/facts/" + id + "/", { method: "PATCH", auth: true, body: { content, version } });
  }

  async restore(): Promise<boolean> {
    await this.csrfToken();
    return this.refresh();
  }

  private refresh(): Promise<boolean> {
    if (this.refreshInFlight) return this.refreshInFlight;
    const generation = this.generation;
    const pending = (async () => {
      if (!this.csrf) await this.csrfToken();
      try {
        const token = await this.send<TokenResponse>("/api/v1/auth/refresh/", {
          method: "POST", csrf: true,
        }, false);
        if (this.generation !== generation) return false;
        this.access = token.access;
        return true;
      } catch {
        if (this.generation === generation) this.access = null;
        return false;
      }
    })();
    this.refreshInFlight = pending;
    void pending.finally(() => { if (this.refreshInFlight === pending) this.refreshInFlight = null; });
    return pending;
  }

  async logout(): Promise<void> {
    this.generation++;
    this.access = null;
    try {
      if (!this.csrf) await this.csrfToken();
      await this.send<void>("/api/v1/auth/logout/", { method: "POST", csrf: true }, false);
    } finally {
      this.access = null;
    }
  }

  candidates(): Promise<CandidateList> {
    return this.send("/api/v1/candidates/");
  }

  candidate(slug: string): Promise<CandidateDetail> {
    return this.send("/api/v1/candidates/" + encodeURIComponent(slug) + "/");
  }

  chatHistory(slug: string): Promise<ChatMessage[]> {
    return this.send("/api/v1/candidates/" + encodeURIComponent(slug) + "/chat/", { auth: true });
  }

  ask(slug: string, question: string, key: string): Promise<ChatAnswer> {
    return this.send("/api/v1/candidates/" + encodeURIComponent(slug) + "/chat/", {
      method: "POST", auth: true, key, body: { question },
    });
  }

  guestStatus(slug: string): Promise<GuestStatus> {
    return this.send("/api/v1/candidates/" + encodeURIComponent(slug) + "/guest-chat/");
  }

  async guestAsk(slug: string, question: string, turnstileToken: string, key: string): Promise<GuestReply> {
    if (!this.csrf) await this.csrfToken();
    return this.send("/api/v1/candidates/" + encodeURIComponent(slug) + "/guest-chat/", {
      method: "POST", csrf: true, key, body: { question, turnstile_token: turnstileToken },
    }, false);
  }

  ownerProfile(): Promise<OwnerProfile> {
    return this.send("/api/v1/me/profile/", { auth: true });
  }

  updateOwnerProfile(changes: OwnerProfileUpdate): Promise<OwnerProfile> {
    return this.send("/api/v1/me/profile/", { auth: true, method: "PATCH", body: changes });
  }

  ownerFacts(page = 1): Promise<OwnerFactList> {
    return this.send("/api/v1/me/facts/?page=" + page, { auth: true });
  }

  reviewFact(id: number, action: ReviewAction, version: string): Promise<OwnerFact> {
    return this.send("/api/v1/me/facts/" + id + "/review/", {
      auth: true, method: "POST", body: { action, version },
    });
  }

  getBackendUrl(path: string): string {
    return new URL(path, this.base).toString();
  }
}

export const api = new ApiClient();
