export async function login(page) {
  await page.goto("/login");
  await page.getByTestId("username").fill("e2e-admin");
  await page.getByTestId("password").fill("E2ePass123!");
  await Promise.all([page.waitForURL("**/"), page.getByTestId("login-submit").click()]);
}

function createSyntheticPdf() {
  const content = "BT /F1 12 Tf 72 720 Td (Synthetic contract fixture for automated testing.) Tj ET";
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    `<< /Length ${Buffer.byteLength(content, "ascii")} >>\nstream\n${content}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];

  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => {
    offsets.push(Buffer.byteLength(pdf, "ascii"));
    pdf += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });

  const xrefOffset = Buffer.byteLength(pdf, "ascii");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  pdf += offsets.slice(1).map((offset) => `${String(offset).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(pdf, "ascii");
}

export async function createTask(page, name = `E2E ${Date.now()}`) {
  await page.getByTestId("new-task").click();
  await page.getByTestId("task-name").fill(name);
  await page
    .getByTestId("pdf-upload")
    .locator("input[type=file]")
    .setInputFiles({
      name: "synthetic-contract.pdf",
      mimeType: "application/pdf",
      buffer: createSyntheticPdf(),
    });
  await page.getByTestId("create-task").click();
  await page.getByTestId("task-table").getByText(name).waitFor({ state: "visible", timeout: 15000 });
  return name;
}

export function taskRow(page, name) {
  return page.getByTestId("task-table").locator(".el-table__row").filter({ hasText: name });
}
