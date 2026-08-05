import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement ResizeObserver, which Recharts' ResponsiveContainer
// uses to size charts - stub it so chart-containing components can render in tests.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverStub;
