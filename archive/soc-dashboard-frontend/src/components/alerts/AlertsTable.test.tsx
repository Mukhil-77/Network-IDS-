import { describe, it, expect, vi } from "vitest";
import { screen, fireEvent } from "@testing-library/react";
import { renderWithProviders } from "../../test/utils/renderWithProviders";
import { AlertsTable } from "./AlertsTable";
import type { AlertRow } from "../../types/alert";

const sampleAlerts: AlertRow[] = [
  {
    id: "a1", timestamp: "2026-07-24T10:00:00Z", attack_type: "DoS", confidence: 95.5,
    severity: "High", source_ip: "10.0.0.1", destination_ip: "10.0.0.9", protocol: "TCP",
    flow_id: "f1", status: "new", model_version: "v1",
  },
  {
    id: "a2", timestamp: "2026-07-24T09:00:00Z", attack_type: "PortScan", confidence: 60.0,
    severity: "Medium", source_ip: "10.0.0.2", destination_ip: "10.0.0.9", protocol: "TCP",
    flow_id: "f2", status: "resolved", model_version: "v1",
  },
];

describe("AlertsTable", () => {
  it("renders every alert row with its key fields", () => {
    renderWithProviders(
      <AlertsTable alerts={sampleAlerts} sortBy="timestamp" sortDesc onSortChange={vi.fn()} />
    );

    expect(screen.getByText("DoS")).toBeInTheDocument();
    expect(screen.getByText("PortScan")).toBeInTheDocument();
    expect(screen.getByText("95.5%")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
    expect(screen.getByText("High")).toBeInTheDocument();
    expect(screen.getByText("new")).toBeInTheDocument();
    expect(screen.getByText("resolved")).toBeInTheDocument();
  });

  it("shows an empty state when there are no alerts", () => {
    renderWithProviders(<AlertsTable alerts={[]} sortBy="timestamp" sortDesc onSortChange={vi.fn()} />);
    expect(screen.getByText(/no alerts match/i)).toBeInTheDocument();
  });

  it("calls onSortChange with the clicked column when a sortable header is clicked", () => {
    const onSortChange = vi.fn();
    renderWithProviders(
      <AlertsTable alerts={sampleAlerts} sortBy="timestamp" sortDesc onSortChange={onSortChange} />
    );

    fireEvent.click(screen.getByRole("button", { name: /confidence/i }));
    expect(onSortChange).toHaveBeenCalledWith("confidence");
  });

  it("shows the sort direction indicator on the active sort column", () => {
    renderWithProviders(
      <AlertsTable alerts={sampleAlerts} sortBy="severity" sortDesc={false} onSortChange={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: /severity ↑/i })).toBeInTheDocument();
  });
});
