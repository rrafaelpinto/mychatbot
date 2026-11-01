import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("http://127.0.0.1:8000/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/candidates/") {
      return route.fulfill({ json: { count: 1, next: null, previous: null, results: [
        { slug: "alex", name: "Alex Example", professional_summary: "Backend engineer", image_url: "", linkedin: null, contact_email: null },
      ] } });
    }
    if (path === "/api/v1/candidates/alex/") return route.fulfill({ json: {
      slug: "alex", name: "Alex Example", professional_summary: "Backend engineer", image_url: "", linkedin: null, contact_email: null,
      facts: [{ id: 3, fact_type: "skill", content: "Approved Python experience" }],
    } });
    if (path === "/api/v1/auth/csrf/") return route.fulfill({ json: { csrf_token: "test" } });
    if (path === "/api/v1/auth/refresh/") return route.fulfill({ status: 401, json: { detail: "Authentication required." } });
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

test("keeps guest chat separate from authenticated REST chat", async ({ page }) => {
  const paidRequests: string[] = [];
  page.on("request", request => {
    if (request.url().includes("/chat/") && request.method() === "POST") paidRequests.push(request.url());
  });
  await page.goto("/#/agent/alex");
  await expect(page.getByText("Sign in to ask a question")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open limited guest demo" })).toHaveAttribute("href", "http://127.0.0.1:8000/chat/alex/");
  expect(paidRequests).toEqual([]);
});
