import assert from "node:assert/strict";
import { test } from "node:test";
import { validateBuildEnvironment } from "./check-build-env.mjs";

test("development build permits its local API", () => {
  assert.doesNotThrow(() => validateBuildEnvironment({
    VITE_API_BASE_URL: "http://localhost:8000",
  }));
});

test("production build requires an explicit HTTPS API origin", () => {
  for (const value of [
    undefined,
    "",
    "http://api.example.test",
    "http://localhost:8000",
    "https://localhost",
    "https://127.0.0.1",
    "https://api.example.test/path",
    "https://api.example.test/?secret=x",
    "https://user:password@api.example.test",
    "https://api.example.test:443",
    "not-a-url",
  ]) {
    assert.throws(
      () => validateBuildEnvironment({
        RESUMEBOT_BUILD_TARGET: "production",
        VITE_API_BASE_URL: value,
      }),
      /Production|HTTPS/,
      String(value),
    );
  }
});

test("production build accepts a dedicated HTTPS API origin", () => {
  assert.doesNotThrow(() => validateBuildEnvironment({
    RESUMEBOT_BUILD_TARGET: "production",
    VITE_API_BASE_URL: "https://api.example.test",
  }));
});
