import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ReplayBar } from "./ReplayBar";

describe("ReplayBar", () => {
  it("renders replay bar with status indicator and speed controls", () => {
    render(<ReplayBar />);

    // Should display replay mode status
    expect(screen.getByText(/Simulating Live Feed|Replay Paused/i)).toBeInTheDocument();

    // Should render speed options
    expect(screen.getByText("1×")).toBeInTheDocument();
    expect(screen.getByText("5×")).toBeInTheDocument();
    expect(screen.getByText("10×")).toBeInTheDocument();
    expect(screen.getByText("50×")).toBeInTheDocument();

    // Should render reset button
    expect(screen.getByText("↺ Reset")).toBeInTheDocument();
  });
});
