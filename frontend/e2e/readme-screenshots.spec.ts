import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test } from "@playwright/test";

const apiOrigin = "http://127.0.0.1:8000";
const frontendOrigin = "http://127.0.0.1:4173";
const slug = "rafael-pinto";

const facts = [
  { id: 101, fact_type: "backend_engineering", content: "At ZivianHealth, I build backend services with Python, Django, and Django REST Framework, including domain models, serializers, validation, permissions, filtering, and pagination." },
  { id: 102, fact_type: "data_access", content: "I work with Django ORM and PostgreSQL access patterns, improve data retrieval, and troubleshoot production behavior." },
  { id: 103, fact_type: "background_processing", content: "I design asynchronous workflows using Celery and Redis for background execution, synchronization, and notifications." },
  { id: 104, fact_type: "engineering_workflow", content: "I use AI-assisted development for repository analysis, planning, prototyping, debugging, automated tests, code review, and documentation, with human validation." },
  { id: 105, fact_type: "applied_ai", content: "My technical background includes LLM integrations, LangChain, and practical AI-enabled software development." },
];

const questions = [
  {
    question: "How do you use Django and Django REST Framework in your work?",
    answer: "I build backend services with Django and DRF, from domain models and serializers to REST API permissions, validation, filtering, and pagination. I focus on maintainable APIs and clear contracts for frontend consumers.",
    facts: [facts[0]],
  },
  {
    question: "What is your experience with PostgreSQL and the Django ORM?",
    answer: "I work with PostgreSQL and Django ORM access patterns as part of backend development. I pay attention to data modeling, retrieval behavior, and production debugging, supported by automated tests.",
    facts: [facts[1]],
  },
  {
    question: "How do you apply AI in your engineering workflow?",
    answer: "I use AI-assisted development for analysis, implementation planning, debugging, testing, reviews, and documentation. I keep architectural decisions and final validation under human control, and I also work with LLM integrations.",
    facts: [facts[3], facts[4]],
  },
];

const profile = {
  slug, name: "Rafael Pinto",
  professional_summary: "I'm a Senior Software Engineer with 15+ years of experience, focused on Python, Django, Django REST Framework, REST APIs, PostgreSQL, and practical AI integration. I work on domain modeling, backend architecture, and reliable software delivery.",
  image_url: "", linkedin: null, contact_email: null,
};

const headers = {
  "Access-Control-Allow-Origin": frontendOrigin,
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Allow-Headers": "Content-Type, X-CSRFToken, Authorization, Idempotency-Key",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

test("capture the public profile and evidence-backed Candidate Agent for documentation", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "light" });
  await page.route(apiOrigin + "/api/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "OPTIONS") {
      return route.fulfill({ status: 204, headers });
    }
    if (path === "/api/v1/candidates/") {
      return route.fulfill({ headers, json: {
        count: 1, results: [profile], next: null, previous: null,
      } });
    }
    if (path === `/api/v1/candidates/${slug}/`) {
      return route.fulfill({ headers, json: { ...profile, facts } });
    }
    if (path === "/api/v1/auth/csrf/") {
      return route.fulfill({ headers, json: { csrf_token: "sample-csrf" } });
    }
    if (path === "/api/v1/auth/refresh/") {
      return route.fulfill({ status: 401, headers, json: { detail: "No session." } });
    }
    if (path === `/api/v1/candidates/${slug}/guest-chat/`) {
      const history = questions.flatMap(entry => [
        { role: "user", content: entry.question, evidence: [] },
        { role: "assistant", content: entry.answer, evidence: entry.facts },
      ]);
      return route.fulfill({ headers, json: {
        enabled: true, guest_verified: true, turnstile_site_key: "",
        remaining: 7, history,
      } });
    }
    return route.abort("failed");
  });

  const outputDir = join(process.cwd(), "..", "docs", "assets");
  mkdirSync(outputDir, { recursive: true });

  await page.goto(`/#/profile/${slug}`);
  await expect(page.getByRole("heading", { name: "Rafael Pinto." })).toBeVisible();
  await expect(page.getByText("I work with Django ORM and PostgreSQL access patterns")).toBeVisible();
  await page.screenshot({
    path: join(outputDir, "resumebot-public-profile.jpg"),
    type: "jpeg", quality: 85, fullPage: true, animations: "disabled",
  });

  await page.goto(`/#/agent/${slug}`);
  await expect(page.getByText(questions[2].answer)).toBeVisible();
  await expect(page.getByText(questions[1].question)).toBeVisible();
  await expect(page.getByText("7 guest questions remaining")).toBeVisible();
  // Expand the transcript for the documentation capture without changing app styles.
  await page.addStyleTag({ content: ".conversation-scroll { max-height: none !important; overflow: visible !important; }" });
  await page.screenshot({
    path: join(outputDir, "resumebot-candidate-agent.jpg"),
    type: "jpeg", quality: 85, fullPage: true, animations: "disabled",
  });
});
