import { mkdirSync } from "node:fs";
import { expect, test } from "@playwright/test";

const headers = {
  "Access-Control-Allow-Origin": "http://127.0.0.1:4173",
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization",
  "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS",
};

for (const width of [320, 390, 768, 1440]) {
  test(`candidate onboarding and pending gate at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    let approved = false;
    let privateCalls = 0;
    let sentRole = "";
    const document = { id: 1, original_filename: "example.docx", size_bytes: 20, processing_status: "processed", uploaded_at: "2026-11-02T12:00:00Z", extraction_status: "not_started" };
    let uploaded = false;
    let fact: { id: number; fact_type: string; content: string; verification_status: string; is_public: boolean; updated_at: string } | null = null;
    await page.route("http://127.0.0.1:8000/api/v1/**", async route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      if (request.method() === "OPTIONS") return route.fulfill({ headers, status: 204 });
      if (path === "/api/v1/auth/csrf/") return route.fulfill({ headers, json: { csrf_token: "csrf" } });
      if (path === "/api/v1/auth/refresh/") return route.fulfill({ headers, status: 401, json: {} });
      if (path === "/api/v1/candidates/") return route.fulfill({ headers, json: { count: 0, next: null, results: [] } });
      if (path === "/api/v1/auth/code/request/") {
        expect(request.headers()["x-csrftoken"]).toBe("csrf");
        sentRole = request.postDataJSON().role;
        return route.fulfill({ headers, json: { detail: "Code requested." } });
      }
      if (path === "/api/v1/auth/code/verify/") return route.fulfill({ headers, json: { access: "candidate-token", expires_in: 300, token_type: "Bearer" } });
      if (path === "/api/v1/me/") return route.fulfill({ headers, json: { id: 1, username: "candidate", email: "example@example.test", role: "candidate", account_status: approved ? "active" : "pending_approval", can_manage_candidate: approved, is_superuser: false, uploads_enabled: true } });
      if (path.startsWith("/api/v1/me/")) {
        privateCalls++;
        if (path === "/api/v1/me/documents/" && request.method() === "POST") { uploaded = true; return route.fulfill({ headers, status: 201, json: document }); }
        if (path === "/api/v1/me/documents/") return route.fulfill({ headers, json: { count: uploaded ? 1 : 0, next: null, results: uploaded ? [document] : [] } });
        if (path === "/api/v1/me/documents/1/extract/") { document.extraction_status = "succeeded"; fact = { id: 1, fact_type: "skill", content: "I build Django APIs.", verification_status: "pending", is_public: false, updated_at: "2026-11-02T12:00:00Z" }; return route.fulfill({ headers, json: { proposed_count: 1, already_completed: false } }); }
        if (path === "/api/v1/me/facts/") return route.fulfill({ headers, json: { count: fact ? 1 : 0, next: null, results: fact ? [fact] : [] } });
        if (path === "/api/v1/me/facts/1/review/" && fact) { fact = { ...fact, verification_status: "verified", is_public: request.postDataJSON().action === "publish" }; return route.fulfill({ headers, json: fact }); }
        if (path === "/api/v1/me/profile/") return route.fulfill({ headers, json: { name: "Example Person", slug: "example", professional_summary: "", linkedin: "", contact_email: "", phone: "", show_linkedin: false, show_contact_email: false, status: "active", publication_status: "draft", image_url: "" } });
        return route.fulfill({ headers, json: { count: 0, next: null, results: [] } });
      }
      return route.abort();
    });
    await page.goto("/#/register");
    await page.getByLabel("Full name").fill("Example Person");
    await page.getByLabel("Email", { exact: true }).fill("example@example.test");
    await expect(page.getByLabel("I am joining as a")).toHaveValue("candidate");
    await expect(page.locator('input[type="password"]')).toHaveCount(0);
    mkdirSync(".local/onboarding", { recursive: true });
    if ([390, 1440].includes(width)) await page.screenshot({ path: `.local/onboarding/register-${width}.png`, fullPage: true });
    await page.getByRole("button", { name: "Send sign-in code", exact: true }).click();
    await page.getByLabel("Verification code").fill("123456");
    expect(sentRole).toBe("candidate");
    await page.getByRole("button", { name: "Verify and continue" }).click();
    await expect(page.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
    expect(privateCalls).toBe(0);
    await page.evaluate(() => { window.location.hash = "/recruiter"; });
    await expect(page.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
    expect(privateCalls).toBe(0);
    if ([390, 1440].includes(width)) await page.screenshot({ path: `.local/onboarding/pending-${width}.png`, fullPage: true });
    approved = true;
    await page.getByRole("button", { name: "Check status" }).click();
    await expect(page.getByRole("link", { name: "My workspace" })).toBeVisible();
    await page.getByRole("link", { name: "My workspace" }).click();
    await expect(page.getByRole("heading", { name: "Your resume" })).toBeVisible();
    await expect(page.getByLabel("PDF or DOCX, up to 5 MB")).toBeEnabled();
    if ([390, 1440].includes(width)) await page.screenshot({ path: `.local/onboarding/workspace-${width}.png`, fullPage: true });
    expect(await page.evaluate(() => [...document.querySelectorAll("body *")].filter(el => el.getBoundingClientRect().right > innerWidth + 1).map(el => el.className))).toEqual([]);
    if (width === 1440) {
      await page.getByLabel("PDF or DOCX, up to 5 MB").setInputFiles({ name: "example.docx", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", buffer: Buffer.from("Synthetic browser fixture") });
      await page.getByRole("button", { name: "Upload resume", exact: true }).click();
      await page.getByRole("button", { name: "Generate suggested facts", exact: true }).click();
      await expect(page.locator(".owner-fact > p").filter({ hasText: "I build Django APIs." })).toBeVisible();
      await page.getByRole("button", { name: "Approve", exact: true }).click();
      await expect(page.getByText("verified · private")).toBeVisible();
      await page.getByRole("button", { name: "Publish", exact: true }).click();
      await expect(page.getByText("verified · public")).toBeVisible();
    }
    await page.keyboard.press("Tab");
    expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe("BODY");
  });
}

test("superuser sees public navigation, workspace and administration", async ({ page }) => {
  await page.route("http://127.0.0.1:8000/api/v1/**", route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "OPTIONS") return route.fulfill({ headers, status: 204 });
    if (path === "/api/v1/auth/csrf/") return route.fulfill({ headers, json: { csrf_token: "csrf" } });
    if (path === "/api/v1/auth/refresh/") return route.fulfill({ headers, json: { access: "root", expires_in: 300, token_type: "Bearer" } });
    if (path === "/api/v1/me/") return route.fulfill({ headers, json: { role: "superuser", account_status: "active", can_manage_candidate: true, is_superuser: true, uploads_enabled: false } });
    return route.fulfill({ headers, json: { count: 0, next: null, results: [] } });
  });
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Administration" })).toHaveAttribute("href", "http://127.0.0.1:8000/admin/");
  await expect(page.getByRole("link", { name: "My workspace" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Recruiter area" })).toBeVisible();
});
