import { describe, expect, it, beforeEach } from "vitest";
import { getToken, setToken, removeToken } from "./auth";

describe("auth storage", () => {
  beforeEach(() => localStorage.clear());
  it("stores and clears the access token", () => {
    setToken("test-token");
    expect(getToken()).toBe("test-token");
    removeToken();
    expect(getToken()).toBe("");
  });
});
