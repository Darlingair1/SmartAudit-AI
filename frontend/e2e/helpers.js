export async function login(page) {
  await page.goto("/login");
  await page.getByTestId("username").fill("e2e-admin");
  await page.getByTestId("password").fill("E2ePass123!");
  await Promise.all([page.waitForURL("**/"), page.getByTestId("login-submit").click()]);
}

export async function createTask(page, name = `E2E ${Date.now()}`) {
  await page.getByTestId("new-task").click();
  await page.getByTestId("task-name").fill(name);
  await page.getByTestId("pdf-upload").locator("input[type=file]").setInputFiles("../ai-python/test.pdf");
  await page.getByTestId("create-task").click();
  await page.getByTestId("task-table").getByText(name).waitFor({ state: "visible", timeout: 15000 });
  return name;
}

export function taskRow(page, name) {
  return page.getByTestId("task-table").locator(".el-table__row").filter({ hasText: name });
}
