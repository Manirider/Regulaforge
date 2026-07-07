import { test, expect } from "@playwright/test";
import { DashboardPage } from "./pages/DashboardPage";

test.describe("Navigation and layout", () => {
  test("redirect to login when unauthenticated", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("404 page for unknown routes when authenticated", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await page.goto("/nonexistent-route");

    await expect(page.getByText("404")).toBeVisible();
    await expect(page.getByText(/page not found/i)).toBeVisible();
  });

  test("logout flow", async ({ page }) => {
    const dashboardPage = new DashboardPage(page);
    await dashboardPage.mockAuthenticatedUser();
    await dashboardPage.goto();

    await page.getByLabel(/notifications/i).waitFor();

    const userMenu = page.getByRole("button", { name: /test user/i });
    if (await userMenu.isVisible()) {
      await userMenu.click();
    } else {
      const avatar = page.locator(".flex.h-8.w-8.items-center.justify-center").first();
      await avatar.click();
    }

    await page.getByText(/sign out/i).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
