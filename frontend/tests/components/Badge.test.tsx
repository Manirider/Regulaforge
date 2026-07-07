import { describe, it, expect } from "vitest";
import { render, screen } from "@/testing/test-utils";
import { Badge, StatusBadge } from "@/components/ui/Badge";

describe("Badge", () => {
  it("renders with text", () => {
    render(<Badge>Active</Badge>);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("applies variant classes", () => {
    render(<Badge variant="success">Good</Badge>);
    expect(screen.getByText("Good").className).toContain("bg-green");
  });
});

describe("StatusBadge", () => {
  it("renders active status with success variant", () => {
    render(<StatusBadge status="active" />);
    const badge = screen.getByText("active");
    expect(badge.className).toContain("bg-green");
  });

  it("renders failed status with danger variant", () => {
    render(<StatusBadge status="failed" />);
    const badge = screen.getByText("failed");
    expect(badge.className).toContain("bg-red");
  });

  it("formats status text", () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText("in progress")).toBeInTheDocument();
  });
});
