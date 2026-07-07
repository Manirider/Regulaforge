import { test, expect } from "@playwright/test";
import { LoginPage } from "./pages/LoginPage";

test.describe("Auth flow", () => {
  test("login page renders correctly", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await expect(loginPage.emailInput).toBeVisible();
    await expect(loginPage.passwordInput).toBeVisible();
    await expect(loginPage.signInButton).toBeVisible();
  });

  test("login form validation shows errors on empty submit", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.signInButton.click();
    await expect(page.getByText(/valid email/i).or(page.getByText(/required/i))).toBeVisible();
    await expect(page.getByText(/password is required/i).or(page.getByText(/required/i))).toBeVisible();
  });

  test("navigation to register page", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();

    await loginPage.registerLink.click();
    await expect(page).toHaveURL(/\/register/);
  });

  test("login with invalid credentials shows error message", async ({ page }) => {
    const loginPage = new LoginPage(page);

    await page.route("**/auth/login", async (route) => {
      await route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Invalid email or password" }),
      });
    });

    await loginPage.goto();
    await loginPage.login("wrong@email.com", "wrongpass");

    await expect(loginPage.errorAlert).toBeVisible();
    await expect(loginPage.errorAlert).toContainText(/invalid/i);
  });
});
