import { describe, expect, it } from "vitest";
import { buildPage, rectsForSpan, sha1 } from "../src/index.ts";
import { DOC_SHA } from "./helpers.ts";

describe("page rebuild (the reference reader's row grouping)", () => {
  it("groups words into rows by bottom edge, orders rows top-down and words left-right, records spans", () => {
    const w = (s: string, x0: number, y1: number) => ({ s, x0, x1: x0 + s.length * 5, y0: y1 - 10, y1 });
    const p = buildPage(1, [w("B", 60, 101.5), w("A", 10, 100), w("C", 10, 130)], 612, 792, DOC_SHA);
    expect(p.text).toBe("A B\nC");
    expect(p.words.map((x) => x.slice(4))).toEqual([[0, 1], [2, 3], [4, 5]]);
    expect(p.scanned).toBe(true);
    // one box per word unless the next word continues the line within 12 pt
    expect(rectsForSpan(p, 0, 3)).toEqual([[10, 90, 15, 100], [60, 91.5, 65, 101.5]]);
    expect(rectsForSpan(p, 4, 5)).toEqual([[10, 120, 15, 130]]);
  });
});

describe("hash", () => {
  it("is SHA-1", () => {
    expect(sha1(new TextEncoder().encode("abc"))).toBe("a9993e364706816aba3e25717850c26c9cd0d89d");
  });
});
