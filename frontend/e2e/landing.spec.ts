import { expect, test } from "@playwright/test";

test("landing page renders hero + nav links", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Quản lý hạ tầng công cộng")).toBeVisible();
  await expect(page.getByRole("link", { name: /Đăng nhập/ }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Khám phá bản đồ/ })).toBeVisible();
});

test("login page renders and demo accounts populate fields", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("button", { name: /Dùng Citizen/ }).click();
  const email = page.getByLabel("Email");
  await expect(email).toHaveValue("citizen@danang.gov.vn");
});
