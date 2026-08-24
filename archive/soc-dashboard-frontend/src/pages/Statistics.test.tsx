import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "../test/utils/renderWithProviders";

vi.mock("../services/statisticsService", () => ({
  statisticsService: {
    get: vi.fn().mockResolvedValue({
      threat_count: 10,
      threats_per_minute: [{ minute: "2026-07-24T10:00", count: 2 }],
      threats_by_type: { DoS: 6, PortScan: 4 },
      threats_by_severity: { High: 6, Low: 4 },
      top_source_ips: [{ source_ip: "10.0.0.5", count: 6 }],
      detection_accuracy: 0.87,
      average_prediction_latency_ms: 5.1,
    }),
    topAttacks: vi.fn().mockResolvedValue([
      { attack_type: "DoS", total_count: 6, last_seen: "2026-07-24T10:00:00Z", avg_confidence: 92.3 },
    ]),
  },
}));

import Statistics from "./Statistics";

describe("Statistics page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders latency and accuracy figures", async () => {
    renderWithProviders(<Statistics />);
    expect(await screen.findByText("5.1")).toBeInTheDocument();
    expect(screen.getByText("87.0%")).toBeInTheDocument();
  });

  it("renders the top attacks list", async () => {
    renderWithProviders(<Statistics />);
    expect(await screen.findByText("DoS")).toBeInTheDocument();
    expect(screen.getByText(/6 · avg 92.3%/)).toBeInTheDocument();
  });

  it("honestly labels system load as unavailable rather than fabricating a number", async () => {
    renderWithProviders(<Statistics />);
    await screen.findByText("DoS");
    expect(screen.getByText("System Load")).toBeInTheDocument();
    expect(screen.getByText(/requires backend telemetry/i)).toBeInTheDocument();
  });
});
