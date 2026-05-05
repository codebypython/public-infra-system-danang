import { expect, test } from "@playwright/test";

test("map page loads MapLibre and filter chips", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByText("Đà Nẵng Infra").first()).toBeVisible();
  // Wait for map canvas
  await page.waitForSelector(".maplibregl-canvas", { timeout: 15_000 });
});
