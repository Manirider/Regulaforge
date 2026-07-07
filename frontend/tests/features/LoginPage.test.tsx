import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@/testing/test-utils";

// Mock react-router-dom Navigate to avoid actual navigation
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    Navigate: ({ to }: { to: string }) => <div data-testid="navigate" data-to={to} />,
  };
});

describe("LoginPage", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders login form", async () => {
    // Dynamic import so mocks are set
    const { LoginPage } = await import("@/features/auth/LoginPage");
    render(<LoginPage />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("shows link to register page", async () => {
    const { LoginPage } = await import("@/features/auth/LoginPage");
    render(<LoginPage />);

    expect(screen.getByText(/create one/i)).toBeInTheDocument();
    expect(screen.getByText(/create one/i).closest("a")).toHaveAttribute("href", "/register");
  });
});
