import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("http://127.0.0.1:8000/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const headers = {
      "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
      "Access-Control-Allow-Credentials": "true",
      "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization, Idempotency-Key",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    };
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (path === "/api/v1/candidates/") {
      return route.fulfill({ headers, json: { count: 1, next: null, previous: null, results: [
        { slug: "alex", name: "Alex Example", professional_summary: "Backend engineer", image_url: "", linkedin: null, contact_email: null },
      ] } });
    }
    if (path === "/api/v1/candidates/alex/") return route.fulfill({ headers, json: {
      slug: "alex", name: "Alex Example", professional_summary: "Backend engineer", image_url: "", linkedin: null, contact_email: null,
      facts: [{ id: 3, fact_type: "skill", content: "Approved Python experience" }],
    } });
    if (path === "/api/v1/auth/csrf/") return route.fulfill({ headers, json: { csrf_token: "test" } });
    if (path === "/api/v1/auth/refresh/") return route.fulfill({ headers, status: 401, json: { detail: "Authentication required." } });
    return route.abort("failed");
  });
});

test("lists only API-provided profiles and displays public evidence", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Meet the candidates." })).toBeVisible();
  await page.getByRole("link", { name: "View profile" }).click();
  await expect(page.getByRole("heading", { name: "Alex Example." })).toBeVisible();
  await expect(page.getByText("Approved Python experience")).toBeVisible();
  await expect(page.getByText("private-documents-test-marker")).toHaveCount(0);
});

test("guest chat uses CSRF, Turnstile and the existing session without JWT", async ({ page }) => {
  const headers = {
    "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization, Idempotency-Key",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  };
  let verified = false;
  let remaining = 2;
  let submits = 0;
  await page.route("https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit", route =>
    route.fulfill({ contentType: "application/javascript", body:
      'window.turnstile = { render: (_node, options) => { options.callback("verified-token"); return "widget"; }, remove: () => {} };' }));
  await page.route("http://127.0.0.1:8000/api/v1/candidates/alex/guest-chat/", route => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (route.request().method() === "GET") return route.fulfill({ headers, json: {
      enabled: true, guest_verified: verified, turnstile_site_key: verified ? "" : "site-test",
      remaining: verified ? remaining : null, history: [],
    } });
    const request = route.request();
    const body = request.postDataJSON();
    expect(request.headers()["x-csrftoken"]).toBe("test");
    expect(request.headers()["idempotency-key"]).toBeTruthy();
    expect(request.headers().authorization).toBeUndefined();
    expect(body.turnstile_token).toBe(verified ? "" : "verified-token");
    expect(body.question).toBeTruthy();
    submits += 1;
    verified = true;
    remaining -= 1;
    return route.fulfill({ headers, json: {
      response: "Published skills only",
      evidence: [{ id: 3, fact_type: "skill", content: "Approved Python experience" }],
      guest_verified: true, remaining,
    } });
  });
  await page.goto("/#/agent/alex");
  await expect(page.getByText("Verify once to begin a limited guest session.")).toBeVisible();
  await page.getByLabel("Professional question").fill("What experience does Alex have?");
  expect(submits).toBe(0);
  await page.getByRole("button", { name: "Send guest question" }).click();
  await expect(page.getByText("Published skills only")).toBeVisible();
  await expect(page.getByText("1 guest questions remaining")).toBeVisible();
  await page.getByLabel("Professional question").fill("Which skills are verified?");
  await page.getByRole("button", { name: "Send guest question" }).click();
  await expect(page.getByText("0 guest questions remaining")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send guest question" })).toBeDisabled();
  expect(submits).toBe(2);
});

test("does not render a paid guest composer when backend disables guest chat", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/api/v1/candidates/alex/guest-chat/", route =>
    route.fulfill({ headers: {
      "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
      "Access-Control-Allow-Credentials": "true",
    }, json: {
      enabled: false, guest_verified: false, turnstile_site_key: "", remaining: null, history: [],
    } }));
  await page.goto("/#/agent/alex");
  await expect(page.getByText("Guest conversation is unavailable")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send guest question" })).toHaveCount(0);
  await expect(page.getByText("Sign in to use your account")).toBeVisible();
});

test("authenticates with JWT and displays evidence-backed API chat", async ({ page }) => {
  const headers = {
    "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization, Idempotency-Key",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  };
  await page.route("http://127.0.0.1:8000/api/v1/auth/token/", route =>
    route.request().method() === "OPTIONS"
      ? route.fulfill({ status: 204, headers })
      : route.fulfill({ headers, json: { access: "test-access", token_type: "Bearer", expires_in: 300 } }),
  );
  await page.route("http://127.0.0.1:8000/api/v1/candidates/alex/chat/", route => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (route.request().headers().authorization !== "Bearer test-access") return route.fulfill({ status: 401, headers });
    if (route.request().method() === "GET") return route.fulfill({ headers, json: [] });
    expect(route.request().headers()["idempotency-key"]).toBeTruthy();
    return route.fulfill({ headers, json: {
      response: "Verified backend experience.",
      evidence: [{ id: 3, fact_type: "skill", content: "Approved Python experience" }],
    } });
  });
  await page.goto("/#/agent/alex");
  await page.getByText("Sign in to use your account").click();
  await page.getByLabel("Username").fill("recruiter");
  await page.getByLabel("Password").fill("sample-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByLabel("Ask a professional question").fill("What is Alex's experience?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText("Verified backend experience.")).toBeVisible();
  await page.getByText("1 supporting fact(s)").click();
  await expect(page.getByText("Approved Python experience")).toBeVisible();
});


test("hides owner data from guests and does not request private APIs", async ({ page }) => {
  const privateRequests: string[] = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/v1/me/")) privateRequests.push(request.url());
  });
  await page.goto("/#/owner");
  await expect(page.getByRole("heading", { name: "Manage your professional profile" })).toBeVisible();
  expect(privateRequests).toEqual([]);
});

test("owner edits approved fields and publishes verified facts", async ({ page }) => {
  const headers = {
    "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization",
    "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
  };
  await page.route("http://127.0.0.1:8000/api/v1/auth/token/", route =>
    route.request().method() === "OPTIONS"
      ? route.fulfill({ status: 204, headers })
      : route.fulfill({ headers, json: { access: "owner-jwt", token_type: "Bearer", expires_in: 300 } }),
  );
  const profile = {
    slug: "alex", name: "Alex Example", professional_summary: "Backend engineer",
    image_url: "", linkedin: "", contact_email: "", show_linkedin: false,
    show_contact_email: false, status: "active", publication_status: "published",
  };
  let submittedProfile: Record<string, unknown> | undefined;
  await page.route("http://127.0.0.1:8000/api/v1/me/profile/", route => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    if (route.request().headers().authorization !== "Bearer owner-jwt") return route.fulfill({ status: 401, headers });
    if (route.request().method() === "PATCH") {
      submittedProfile = route.request().postDataJSON();
      return route.fulfill({ headers, json: { ...profile, ...submittedProfile } });
    }
    return route.fulfill({ headers, json: profile });
  });
  const fact = { id: 3, fact_type: "skill", content: "Approved Python experience",
    verification_status: "verified", is_public: false, updated_at: "2026-10-30T11:00:00Z" };
  let listed = fact;
  await page.route("http://127.0.0.1:8000/api/v1/me/facts/?*", route =>
    route.fulfill({ headers, json: { count: 1, next: null, previous: null, results: [listed] } }));
  await page.route("http://127.0.0.1:8000/api/v1/me/facts/3/review/", route => {
    if (route.request().method() === "OPTIONS") return route.fulfill({ status: 204, headers });
    expect(route.request().headers().authorization).toBe("Bearer owner-jwt");
    expect(route.request().postDataJSON()).toEqual({ action: "publish", version: fact.updated_at });
    listed = { ...fact, is_public: true, updated_at: "2026-10-31T11:00:00Z" };
    return route.fulfill({ headers, json: listed });
  });
  await page.goto("/#/owner");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Professional facts" })).toBeVisible();
  await page.getByLabel("professional summary").fill("Updated profile");
  await page.getByRole("button", { name: "Save profile" }).click();
  await expect(page.getByText("Profile changes saved. Publication status is unchanged.")).toBeVisible();
  expect(submittedProfile).toMatchObject({ professional_summary: "Updated profile" });
  expect(submittedProfile).not.toHaveProperty("status");
  expect(submittedProfile).not.toHaveProperty("publication_status");
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("verified · public")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Manage your professional profile" })).toBeVisible();
  await expect(page.getByText("Approved Python experience")).toHaveCount(0);
});

test("stale fact reviews reload the current version instead of silently overwriting", async ({ page }) => {
  const headers = {
    "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  };
  await page.route("http://127.0.0.1:8000/api/v1/auth/token/", route => route.fulfill({
    headers, json: { access: "owner-jwt", token_type: "Bearer", expires_in: 300 },
  }));
  await page.route("http://127.0.0.1:8000/api/v1/me/profile/", route => route.fulfill({ headers, json: {
    slug: "alex", name: "Alex Example", professional_summary: "Backend engineer",
    image_url: "", linkedin: "", contact_email: "", show_linkedin: false,
    show_contact_email: false, status: "active", publication_status: "published",
  } }));
  let reads = 0;
  await page.route("http://127.0.0.1:8000/api/v1/me/facts/?*", route => {
    reads += 1;
    return route.fulfill({ headers, json: { count: 1, next: null, previous: null, results: [{
      id: 3, fact_type: "skill", content: "Approved Python experience",
      verification_status: "verified", is_public: reads > 1,
      updated_at: reads > 1 ? "2026-10-31T13:00:00Z" : "2026-10-30T13:00:00Z",
    }] } });
  });
  await page.route("http://127.0.0.1:8000/api/v1/me/facts/3/review/", route =>
    route.fulfill({ headers, status: 409, json: { detail: "Fact changed. Reload before reviewing." } }));
  await page.goto("/#/owner");
  await page.getByLabel("Username").fill("owner");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Latest facts were reloaded.", { exact: false })).toBeVisible();
  await expect(page.getByText("verified · public")).toBeVisible();
  expect(reads).toBe(2);
});
