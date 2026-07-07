import { test, expect } from "@playwright/test";
import { DashboardPage } from "./pages/DashboardPage";

test.describe("Dashboard", () => {
  test("dashboard loads after mocking auth", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await dashboardPage.goto();

    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test("sidebar navigation links are present", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await dashboardPage.goto();

    await expect(page.getByRole("link", { name: /^dashboard$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^regulations$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^assessments$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^entities$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^documents$/i })).toBeVisible();
  });

  test("navigation to regulations page", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await dashboardPage.goto();

    await page.getByRole("link", { name: /^regulations$/i }).click();
    await expect(page).toHaveURL(/\/regulations/);
  });

  test("navigation to assessments page", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await dashboardPage.goto();

    await page.getByRole("link", { name: /^assessments$/i }).click();
    await expect(page).toHaveURL(/\/assessments/);
  });
});
