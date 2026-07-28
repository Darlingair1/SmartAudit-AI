import { test, expect } from "@playwright/test";
import { createTask, login, taskRow } from "./helpers";

test("user can create an audit task and trigger review", async ({ page }) => {
  test.setTimeout(120_000);

  await login(page);

  const taskName = await createTask(page);
  await taskRow(page, taskName).getByTestId("view-task").click();
  await expect(page.getByTestId("task-detail")).toBeVisible();
  await page.getByTestId("trigger-audit").click();
  await expect(page.getByTestId("sse-status")).toContainText("实时通道已连接", { timeout: 10000 });
  await expect(page.getByTestId("task-status")).toContainText("已完成", { timeout: 90_000 });
  await expect(page.getByTestId("sse-status")).toContainText("实时通道已完成");
  await expect(page.getByTestId("risk-item")).toHaveCount(1);
  await expect(page.getByTestId("risk-highlight")).toContainText("逾期付款");
  await page.getByTestId("risk-item").click();
  await expect(page.getByTestId("pdf-page-status")).toContainText("1 / 1");
});
