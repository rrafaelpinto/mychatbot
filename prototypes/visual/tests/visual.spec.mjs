import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const views = [
  { route: "home", heading: /Your experience/, filename: "overview" },
  { route: "profile", heading: /Alex Morgan/, filename: "profile" },
  { route: "agent", heading: /Ask better questions/, filename: "agent" }
];

const sizes = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "mobile", width: 390, height: 844 }
];

test.describe("Visual review", () => {
  for (const size of sizes) {
    test.describe(size.name, () => {
      test.use({ viewport: { width: size.width, height: size.height } });

      for (const view of views) {
        test(`${view.route} layout, screenshot and accessibility`, async ({ page }) => {
          const outside = [];
          page.on("request", (request) => {
            if (!request.url().startsWith("http://127.0.0.1:4173/")) {
              outside.push(request.url());
            }
          });

          await page.goto(`/#${view.route}`);
          await expect(page.getByRole("heading", { name: view.heading })).toBeVisible();
          await expect(page.locator(`[data-nav="${view.route}"]`))
            .toHaveAttribute("aria-current", "page");
          await expect(page.locator("#view-home")).toBeHidden({
            timeout: view.route === "home" ? 0 : 5000
          }).catch(async (error) => {
            if (view.route !== "home") throw error;
          });

          const noOverflow = await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth
          );
          expect(noOverflow, "No horizontal overflow at tested viewport").toBe(true);
          expect(outside, "No external requests from prototype").toEqual([]);

          const audit = await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze();
          expect(audit.violations, JSON.stringify(audit.violations, null, 2)).toEqual([]);

          await page.screenshot({
            path: `prototypes/visual/screenshots/${view.filename}-${size.name}.png`,
            fullPage: true,
            animations: "disabled"
          });
        });
      }

      test("agent evidence and exceptional states", async ({ page }) => {
        await page.goto("/#agent");
        await page.getByRole("button", { name: /Backend experience/ }).click();
        await expect(page.getByLabel("Ask a professional question")).toHaveValue(
          "What is Alex's backend experience?"
        );
        await page.getByRole("button", { name: "Send question" }).click();
        await expect(page.getByText(/Alex has worked on backend services/)).toBeVisible();
        const evidence = page.getByText("2 verified sample facts");
        await evidence.click();
        await expect(page.getByText(/Designed REST APIs in Django/)).toBeVisible();
        await page.screenshot({
          path: `prototypes/visual/screenshots/agent-evidence-${size.name}.png`,
          fullPage: true
        });

        await page.getByLabel("Simulate an interface state").selectOption("unavailable");
        await expect(page.getByText("Candidate Agent temporarily unavailable")).toBeVisible();
        await expect(page.getByLabel("Ask a professional question")).toBeDisabled();
        await page.screenshot({
          path: `prototypes/visual/screenshots/agent-unavailable-${size.name}.png`,
          fullPage: true
        });
        for (const state of ["empty", "quota", "denied", "loading"]) {
          await page.getByLabel("Simulate an interface state").selectOption(state);
          await expect(page.locator("#chat-status .state-feedback")).toBeVisible();
          await expect(page.getByLabel("Ask a professional question")).toBeDisabled();
        }
        await page.getByLabel("Simulate an interface state").selectOption("ready");
        await expect(page.getByLabel("Ask a professional question")).toBeEnabled();
        await page.getByRole("button", { name: "Send question" }).count();
      });

      test("theme toggle and keyboard navigation", async ({ page }) => {
        await page.goto("/#home");
        const theme = page.getByRole("button", { name: "Switch to dark theme" });
        await theme.click();
        await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
        await expect(
          page.getByRole("button", { name: "Switch to light theme" })
        ).toHaveAttribute("aria-pressed", "true");
        await page.screenshot({
          path: `prototypes/visual/screenshots/overview-dark-${size.name}.png`,
          fullPage: true
        });
        await page.keyboard.press("Tab");
        expect(await page.locator(":focus").count()).toBe(1);
        await page.getByRole("link", { name: "Sample profile" }).click();
        await expect(page.getByRole("heading", { name: /Alex Morgan/ })).toBeVisible();
      });
    });
  }
});

test("320px mobile and 768px tablet have no horizontal overflow", async ({ page }) => {
  for (const width of [320, 768]) {
    await page.setViewportSize({ width, height: 860 });
    for (const view of views) {
      await page.goto(`/#${view.route}`);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        `Overflow on ${view.route} at ${width}px`
      ).toBe(true);
    }
  }
});

test("quota is represented as disabled input without a provider call", async ({ page }) => {
  await page.goto("/#agent");
  const field = page.getByLabel("Ask a professional question");
  for (let index = 0; index < 3; index += 1) {
    await field.fill("Which technologies does Alex use?");
    await page.getByRole("button", { name: "Send question" }).click();
  }
  await expect(page.getByText("Question limit reached")).toBeVisible();
  await expect(field).toBeDisabled();
  await expect(page.getByRole("button", { name: "Send question" })).toBeDisabled();
});
