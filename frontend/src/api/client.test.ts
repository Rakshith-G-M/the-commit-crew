import { afterEach, describe, expect, it } from "vitest";
import { ApiError, qs, request } from "./client";
import { mockFetch, unmockFetch } from "../test/setup";

describe("qs", () => {
  it("skips undefined/null and encodes values", () => {
    expect(qs({ a: 1, b: null, c: undefined, d: "x y" })).toBe("?a=1&d=x%20y");
  });
  it("returns empty when nothing to encode", () => {
    expect(qs({})).toBe("");
  });
});

describe("request", () => {
  afterEach(() => unmockFetch());

  it("GETs a JSON envelope from the /api path", async () => {
    const seen: Array<[string, string]> = [];
    mockFetch((method, url) => {
      seen.push([method, url]);
      return { items: [], total: 0 };
    });
    const out = await request<{ items: unknown[]; total: number }>("/api/spaces", {
      method: "GET",
    });
    expect(out.total).toBe(0);
    expect(seen[0][0]).toBe("GET");
    expect(seen[0][1]).toContain("/api/spaces");
  });

  it("derives POST method from RequestInit", async () => {
    const seen: Array<[string, string]> = [];
    mockFetch((method, url) => {
      seen.push([method, url]);
      return { availability: { present: false } };
    });
    await request("/api/allocation/evaluate", {
      method: "POST",
      body: JSON.stringify({ capacity_people: 20 }),
    });
    expect(seen[0][0]).toBe("POST");
  });

  it("throws ApiError(0) when the network is unreachable", async () => {
    mockFetch(() => {
      throw new TypeError("fetch failed");
    });
    await expect(request("/api/x")).rejects.toMatchObject({ status: 0 });
  });

  it("throws ApiError with the detail message on HTTP errors", async () => {
    mockFetch(() => ({ body: { detail: "space_id not found" }, status: 404 }));
    await expect(request("/api/spaces/nope/bim-design")).rejects.toBeInstanceOf(
      ApiError,
    );
    await request("/api/spaces/nope/bim-design").catch((e: ApiError) => {
      expect(e.status).toBe(404);
      expect(e.message).toContain("space_id not found");
    });
  });
});