import { expect, test } from "@playwright/test";
import { INCIDENT_ID, mockApi } from "./fixtures";

test("Ctrl+K opens a real investigation from the palette", async ({ page }) => {
  await mockApi(page);
  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("navigation").first()).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("fabricated");
  await expect(page.getByRole("option").first()).toContainText("Test case");
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(new RegExp(`/investigations/${INCIDENT_ID}`));
});

test("palette is not available on the landing page", async ({ page }) => {
  await mockApi(page, { signedIn: false });
  await page.goto("/");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog", { name: "Command palette" })).toHaveCount(0);
});

test("progress rail reflects stored data, not a guess", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/investigations/${INCIDENT_ID}`);
  const rail = page.getByRole("navigation", { name: "Case progress" });
  await expect(rail.getByRole("button", { name: /^Upload: Media stored and hashed/ })).toBeVisible();
  await expect(rail.getByRole("button", { name: /^Report: Not generated/ })).toBeVisible(); // fixture returns 404 for report
});

test("fingerprint page draws the real hash bits", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/investigations/${INCIDENT_ID}/fingerprint`);
  const grid = page.getByRole("img", { name: /^pHash: 64-bit hash d1a5c3e18f0b2d47/ });
  await expect(grid).toBeVisible();
  // d1a5c3e18f0b2d47 has 32 bits set — verify the label states the real popcount, not a decorative number.
  await expect(grid).toHaveAttribute("aria-label", /32 bits set/);
});

test("selecting a graph node dims unrelated nodes", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/investigations/${INCIDENT_ID}/lineage`);
  await page.getByRole("button", { name: /Source Graph/ }).click();
  await page.getByRole("button", { name: /^Telegram/ }).click();
  await expect.poll(async () => page.getByRole("button", { name: /^Facebook/ }).evaluate((el) => getComputedStyle(el).opacity)).toBe("0.25");
  await expect(page.getByRole("button", { name: /^X,/ })).toHaveCSS("opacity", "1"); // linked to Telegram by r1
  await page.keyboard.press("Escape");
});

test("reduced motion: content is visible immediately", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page);
  await page.goto("/dashboard");
  await expect(page.getByRole("heading").first()).toBeVisible();
});
