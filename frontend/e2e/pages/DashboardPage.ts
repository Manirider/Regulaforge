import { type Locator, type Page } from "@playwright/test";

export class DashboardPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async mockAuthenticatedUser() {
    await this.page.evaluate(() => {
      localStorage.setItem("access_token", "mock-token");
    });
    await this.page.route("**/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          email: "test@example.com",
          full_name: "Test User",
          username: "testuser",
          is_superuser: false,
        }),
      });
    });
  }

  async mockAuthenticatedAdmin() {
    await this.page.evaluate(() => {
      localStorage.setItem("access_token", "mock-token");
    });
    await this.page.route("**/auth/me", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: 1,
          email: "admin@example.com",
          full_name: "Admin User",
          username: "admin",
          is_superuser: true,
        }),
      });
    });
  }

  async goto() {
    await this.page.goto("/dashboard");
  }
}
