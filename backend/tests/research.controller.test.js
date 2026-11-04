const test = require("node:test");
const assert = require("node:assert/strict");

const {
  validSymbol,
  structuredError,
} = require("../src/controllers/research.controller");

test("research proxy accepts normal stock symbols and rejects traversal input", () => {
  assert.equal(validSymbol("TATASTEEL.NS"), true);
  assert.equal(validSymbol("^NSEI"), true);
  assert.equal(validSymbol("BAD SYMBOL"), false);
  assert.equal(validSymbol("../../secret"), false);
  assert.equal(validSymbol(""), false);
  assert.equal(validSymbol(null), false);
});

test("structuredError preserves AI-service error payloads", () => {
  const parsed = structuredError({
    response: {
      status: 409,
      data: {
        detail: {
          error: {
            code: "registry_unavailable",
            message: "No active model",
          },
        },
      },
    },
  });
  assert.equal(parsed.status, 409);
  assert.equal(parsed.error.code, "registry_unavailable");
});

test("structuredError falls back to a 502 for transport failures", () => {
  const parsed = structuredError(new Error("connection refused"));
  assert.equal(parsed.status, 502);
  assert.equal(parsed.error.code, "ai_service_unavailable");
  assert.match(parsed.error.message, /connection refused/);
});
