import { expect, test } from "@playwright/test";

// Single main-flow smoke test: the prefilled form is submitted and the
// exposure conclusion (verdict, total LAeq, dominant source, per-period
// LAeq) appears — all rendered from the one backend energy calculation.
test("main flow: submit default periods and see the exposure conclusion", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByTestId("period-1")).toBeVisible();
  await expect(page.getByTestId("period-2")).toBeVisible();

  await page.getByRole("button", { name: "计算暴露" }).click();

  await expect(page.getByTestId("verdict")).toHaveText("超标");
  await expect(page.getByTestId("total-laeq")).toContainText("dB(A)");
  await expect(page.getByTestId("dominant-source")).toContainText("时段 2");
  await expect(page.getByTestId("dominant-source")).toContainText("2000 Hz");
  await expect(page.getByTestId("period-laeq-1")).toBeVisible();
  await expect(page.getByTestId("period-laeq-2")).toBeVisible();
});
