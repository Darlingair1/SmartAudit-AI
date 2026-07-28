import { test, expect } from "@playwright/test";

test("user can log in with the E2E account", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByTestId("login-form")).toBeVisible();
  await page.getByTestId("username").fill("e2e-admin");
  await page.getByTestId("password").fill("E2ePass1234!");
  await Promise.all([
    page.waitForURL("**/"),
    page.getByTestId("login-submit").click(),
  ]);
  await expect(page.getByTestId("task-table")).toBeVisible();
});
