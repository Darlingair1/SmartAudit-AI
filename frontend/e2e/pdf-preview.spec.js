import { test, expect } from "@playwright/test";
import { createTask, login, taskRow } from "./helpers";

test("task detail exposes PDF and risk anchors", async ({ page }) => {
  await login(page);
  const taskName = await createTask(page, `E2E PDF ${Date.now()}`);
  await taskRow(page, taskName).getByTestId("view-task").click();
  await expect(page.getByTestId("task-detail")).toBeVisible();
  await expect(page.getByTestId("pdf-preview")).toBeVisible();
  await expect(page.getByTestId("pdf-page-status")).toBeVisible();
});
