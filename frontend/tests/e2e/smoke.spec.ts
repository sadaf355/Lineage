import { test, expect } from "@playwright/test";

test("landing page is reachable", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/LINEAGE/i);
});
