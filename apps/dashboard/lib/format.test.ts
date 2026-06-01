import { describe, expect, it } from "vitest";

import { formatCompactNumber, formatPercent } from "./format";

describe("format helpers", () => {
  it("formats compact numbers and percentages", () => {
    expect(formatCompactNumber(12500)).toBe("12.5K");
    expect(formatPercent(42.4)).toBe("42%");
  });
});
