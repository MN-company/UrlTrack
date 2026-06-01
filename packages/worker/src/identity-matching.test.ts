import { describe, expect, it } from "vitest";

import { extractSignals, matchIdentity, scoreCandidate } from "./identity-matching";

describe("identity matching", () => {
  it("confirms a strong multi-signal visitor match", () => {
    const scored = scoreCandidate(
      {
        email: "lead@example.com",
        canvasHash: "canvas-a",
        webglHash: "webgl-a",
        thumbmarkHash: "tm-a"
      },
      {
        visitorId: "visitor-1",
        email: "lead@example.com",
        canvasHash: "canvas-a",
        webglHash: "webgl-a",
        thumbmarkHash: "tm-a"
      }
    );

    expect(scored.confidenceScore).toBeGreaterThanOrEqual(60);
    expect(scored.matchReasons).toContain("same_email");
  });

  it("suggests review for medium confidence matches", () => {
    const result = matchIdentity(
      {
        workspaceId: "workspace-1",
        visitId: "visit-1",
        canvasHash: "canvas-a",
        webglHash: "webgl-a"
      },
      [{ visitorId: "visitor-1", canvasHash: "canvas-a", webglHash: "webgl-a" }]
    );

    expect(result.action).toBe("review_suggested");
    expect(result.reviewSuggested).toBe(true);
  });

  it("extracts ThumbmarkJS hash fields from raw payloads", () => {
    const signals = extractSignals({
      thumbmark: {
        hash: "abc",
        components: {
          canvas: { hash: "canvas" },
          webgl: { hash: "webgl" },
          audio: { hash: "audio" },
          screen: { resolution: "1440x900" }
        }
      }
    });

    expect(signals.thumbmarkHash).toBe("abc");
    expect(signals.canvasHash).toBe("canvas");
    expect(signals.webglHash).toBe("webgl");
    expect(signals.audioFingerprint).toBe("audio");
  });
});
