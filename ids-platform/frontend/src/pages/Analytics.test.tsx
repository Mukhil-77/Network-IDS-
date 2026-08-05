import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/utils/renderWithProviders";

vi.mock("../services/analyticsService", () => ({
  analyticsService: {
    getOverview: vi.fn().mockResolvedValue({
      top_attack_types: { DoS: 5 },
      attack_timeline: [{ date: "2026-07-20", count: 3 }],
      top_source_ips: [{ source_ip: "10.0.0.1", count: 5 }],
      top_destination_ips: [{ destination_ip: "10.0.0.9", count: 5 }],
      attack_heatmap: [],
      severity_distribution: { High: 5 },
      detection_accuracy: 0.92,
      false_positive_rate: null,
      average_detection_time_ms: 4.5,
      average_response_time_seconds: 12.3,
    }),
    getTrends: vi.fn().mockResolvedValue({ attack_timeline: [], forecast: [] }),
  },
}));

import Analytics from "./Analytics";

describe("Analytics page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders detection accuracy once loaded", async () => {
    renderWithProviders(<Analytics />);
    expect(await screen.findByText("92.0%")).toBeInTheDocument();
  });

  it("honestly labels false positive rate as unavailable rather than fabricating a number", async () => {
    renderWithProviders(<Analytics />);
    expect(await screen.findByText("False Positive Rate")).toBeInTheDocument();
    expect(screen.getByText(/requires labeled ground truth/i)).toBeInTheDocument();
  });

  it("renders average detection and response time", async () => {
    renderWithProviders(<Analytics />);
    expect(await screen.findByText("4.5")).toBeInTheDocument();
    expect(screen.getByText("12.3")).toBeInTheDocument();
  });
});
