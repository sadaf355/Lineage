import { describe, expect, it } from "vitest";
import { ApiError } from "../lib/api";

describe("frontend API primitives", () => {
  it("represents an API failure with a status", () => {
    const error = new ApiError("Unauthorized", 401);
    expect(error.status).toBe(401);
    expect(error.message).toBe("Unauthorized");
  });
});
