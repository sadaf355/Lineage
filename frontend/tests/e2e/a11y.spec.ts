import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { INCIDENT_ID, mockApi } from "./fixtures";

/**
 * Automated accessibility pass (axe-core, WCAG 2.0/2.1 A + AA rules).
 * Automated checks find roughly a third of real-world accessibility problems; passing here is necessary, NOT sufficient.
 * Still required by hand: screen-reader walkthrough, keyboard-only walkthrough, 200% zoom, reduced-motion.
 *
 * Violations fail the build. The only exclusions are listed below with a reason, so they stay visible in review.
 */
const EXCLUDE: string[] = [
  // The WebGL globe is a decorative/exploratory canvas; its data is also available in the Source Graph and Timeline.
  "canvas",
];

async function audit(page: import("@playwright/test").Page, label: string) {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(900); // let entrance animations finish so contrast is measured on settled opacity
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]);
  for (const sel of EXCLUDE) builder = builder.exclude(sel);
  const { violations } = await builder.analyze();
  const summary = violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}: ${v.help}\n    ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join("\n    ")}`).join("\n");
  expect(violations, `${label}\n${summary}`).toEqual([]);
}

const PUBLIC = [["landing", "/"], ["login", "/login"]] as const;
const SIGNED_IN = [
  ["dashboard", "/dashboard"], ["investigations list", "/investigations"], ["new investigation", "/investigations/new"],
  ["roadmap", "/roadmap"], ["settings", "/settings"],
  ["case overview", `/investigations/${INCIDENT_ID}`], ["detection", `/investigations/${INCIDENT_ID}/detection`],
  ["fingerprint", `/investigations/${INCIDENT_ID}/fingerprint`], ["evidence locker", `/investigations/${INCIDENT_ID}/evidence`],
  ["lineage", `/investigations/${INCIDENT_ID}/lineage`], ["attribution gap", `/investigations/${INCIDENT_ID}/attribution`],
  ["report", `/investigations/${INCIDENT_ID}/report`], ["automation", `/investigations/${INCIDENT_ID}/automation`],
] as const;

for (const [name, path] of PUBLIC) {
  test(`axe: ${name}`, async ({ page }) => {
    await mockApi(page, { signedIn: false });
    await page.goto(path);
    await audit(page, name);
  });
}
for (const [name, path] of SIGNED_IN) {
  test(`axe: ${name}`, async ({ page }) => {
    await mockApi(page);
    await page.goto(path);
    await audit(page, name);
  });
}

test("axe: source graph with a focused node (dimming + detail panel)", async ({ page }) => {
  await mockApi(page);
  await page.goto(`/investigations/${INCIDENT_ID}/lineage`);
  await page.getByRole("button", { name: /Source Graph/ }).click();
  const node = page.getByRole("button", { name: /^Telegram/ });
  await node.focus();
  await page.keyboard.press("Enter");
  await expect(node).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByText("Linked sources")).toBeVisible();
  await audit(page, "source graph focused");
});

test("axe: command palette open", async ({ page }) => {
  await mockApi(page);
  await page.goto("/dashboard");
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("navigation").first()).toBeVisible();
  await page.keyboard.press("Control+k");
  const dialog = page.getByRole("dialog", { name: "Command palette" });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole("combobox")).toBeFocused();
  await audit(page, "command palette");
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
});
