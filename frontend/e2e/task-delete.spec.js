import { test, expect } from "@playwright/test";
import { createTask, login, taskRow } from "./helpers";

test("user can delete an existing task", async ({ page }) => {
  await login(page);
  const taskName = await createTask(page, `E2E Delete ${Date.now()}`);
  const deleteButton = taskRow(page, taskName).getByTestId("delete-task");
  await expect(deleteButton).toBeVisible({ timeout: 15000 });
  await deleteButton.click();
  const confirm = page.locator(".el-message-box__btns button").last();
  await expect(confirm).toBeVisible();
  await confirm.click();
  await expect(page.getByTestId("task-table")).toBeVisible();
  await expect(page.getByTestId("task-table")).not.toContainText(taskName);
});
