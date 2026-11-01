import { afterEach, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";

afterEach(() => vi.restoreAllMocks());
const json = (payload: unknown, status = 200) => new Response(JSON.stringify(payload), {
  status,
  headers: { "Content-Type": "application/json" },
});

it("sends a CSRF header and keeps tokens in memory", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(json({ csrf_token: "csrf-value" }))
    .mockResolvedValueOnce(json({ access: "access-value", token_type: "Bearer", expires_in: 300 }));
  const client = new ApiClient("https://api.example.test", fetcher);
  await client.login("owner", "password");
  expect(fetcher).toHaveBeenCalledTimes(2);
  const request = fetcher.mock.calls[1]![1] as RequestInit;
  expect((request.headers as Record<string, string>)["X-CSRFToken"]).toBe("csrf-value");
  expect(request.credentials).toBe("include");
  expect(request.cache).toBe("no-store");
  expect((request.headers as Record<string, string>).Authorization).toBeUndefined();
  expect(fetcher.mock.calls[0]![0].origin).toBe("https://api.example.test");
});

it("refreshes once after an expired bearer and retries only after successful rotation", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(json({ csrf_token: "csrf" }))
    .mockResolvedValueOnce(json({ access: "old", token_type: "Bearer", expires_in: 300 }))
    .mockResolvedValueOnce(json({ detail: "Invalid token" }, 401))
    .mockResolvedValueOnce(json({ access: "fresh", token_type: "Bearer", expires_in: 300 }))
    .mockResolvedValueOnce(json([]));
  const client = new ApiClient("https://api.example.test", fetcher);
  await client.login("owner", "password");
  expect(await client.chatHistory("alex")).toEqual([]);
  expect((fetcher.mock.calls[2]![1]!.headers as Record<string, string>).Authorization).toBe("Bearer old");
  expect((fetcher.mock.calls[4]![1]!.headers as Record<string, string>).Authorization).toBe("Bearer fresh");
});

it("does not retry denied or budget-exhausted paid requests", async () => {
  const fetcher = vi.fn()
    .mockResolvedValueOnce(json({ csrf_token: "csrf" }))
    .mockResolvedValueOnce(json({ access: "token", token_type: "Bearer", expires_in: 300 }))
    .mockResolvedValueOnce(json({ detail: "Quota reached" }, 429));
  const client = new ApiClient("https://api.example.test", fetcher);
  await client.login("owner", "password");
  await expect(client.ask("alex", "Question?", "fixed-key")).rejects.toMatchObject({ status: 429 });
  expect(fetcher).toHaveBeenCalledTimes(3);
  expect((fetcher.mock.calls[2]![1]!.headers as Record<string, string>)["Idempotency-Key"]).toBe("fixed-key");
});

it("reports backend errors without exposing internal objects", async () => {
  const client = new ApiClient("https://api.example.test", vi.fn().mockResolvedValue(json({ detail: "Not found." }, 404)));
  await expect(client.candidate("unknown")).rejects.toEqual(new ApiError(404, "Not found."));
});
