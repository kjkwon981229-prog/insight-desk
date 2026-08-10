import assert from "node:assert/strict";
import { test } from "node:test";

import { handleRequest, runWatchdog } from "../src/index.js";

class MemoryKV {
  constructor() {
    this.values = new Map();
  }

  async get(key) {
    return this.values.get(key) ?? null;
  }

  async put(key, value) {
    this.values.set(key, String(value));
  }

  async delete(key) {
    this.values.delete(key);
  }

  async list({ prefix = "" } = {}) {
    return {
      keys: [...this.values.keys()]
        .filter((key) => key.startsWith(prefix))
        .map((name) => ({ name })),
      list_complete: true,
    };
  }
}

const origin = "https://kjkwon981229-prog.github.io";
const publicKey = base64Url(new Uint8Array(65).fill(3));
const privateKey = base64Url(new Uint8Array(32).fill(5));
const sendToken = "test-send-token";

function base64Url(bytes) {
  return Buffer.from(bytes).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const subscription = {
  endpoint: "https://push.example.test/subscription/one",
  keys: {
    p256dh: base64Url(new Uint8Array(65).fill(7)),
    auth: base64Url(new Uint8Array(16).fill(9)),
  },
};

function environment() {
  return {
    ALLOWED_ORIGIN: origin,
    VAPID_PUBLIC_KEY: publicKey,
    VAPID_PRIVATE_KEY: privateKey,
    VAPID_SUBJECT: `${origin}/`,
    PUSH_SEND_TOKEN: sendToken,
    PUSH_SUBSCRIPTIONS: new MemoryKV(),
  };
}

function request(path, { method = "GET", body, headers = {}, withOrigin = true } = {}) {
  const requestHeaders = new Headers(headers);
  if (withOrigin) {
    requestHeaders.set("Origin", origin);
  }
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }
  return new Request(`https://insight-desk-push.example${path}`, {
    method,
    headers: requestHeaders,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

test("health and VAPID public key do not expose private configuration", async () => {
  const env = environment();
  const health = await handleRequest(request("/health", { withOrigin: false }), env);
  assert.equal(health.status, 200);
  assert.deepEqual(await health.json(), {
    ok: true,
    service: "insight-desk-push",
    kv_configured: true,
    vapid_configured: true,
  });
  const key = await handleRequest(request("/vapid-public-key"), env);
  assert.equal(key.status, 200);
  const body = await key.json();
  assert.equal(body.public_key, publicKey);
  assert.equal(JSON.stringify(body).includes(privateKey), false);
});

test("malformed VAPID material fails closed without returning key material", async () => {
  const env = environment();
  env.VAPID_PUBLIC_KEY = "not-a-vapid-key";
  const response = await handleRequest(request("/vapid-public-key"), env);
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { ok: false, error: "VAPID_NOT_CONFIGURED" });
});

test("CORS rejects non-Pages origins and preflight exposes only the contract", async () => {
  const env = environment();
  const bad = new Request("https://insight-desk-push.example/subscribe", {
    method: "POST",
    headers: { Origin: "https://evil.example", "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
  const rejected = await handleRequest(bad, env);
  assert.equal(rejected.status, 403);
  assert.equal(rejected.headers.get("Access-Control-Allow-Origin"), null);
  const preflight = await handleRequest(request("/subscribe", { method: "OPTIONS" }), env);
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get("Access-Control-Allow-Origin"), origin);
  assert.match(preflight.headers.get("Access-Control-Allow-Methods"), /DELETE/);
});

test("subscription validation stores only normalized browser keys and supports unsubscribe", async () => {
  const env = environment();
  const created = await handleRequest(request("/subscribe", { method: "POST", body: { ...subscription, expirationTime: 123 } }), env);
  assert.equal(created.status, 201);
  assert.deepEqual(await created.json(), { ok: true, subscribed: true });
  const stored = [...env.PUSH_SUBSCRIPTIONS.values.values()].find((value) => value.includes("push.example"));
  assert.deepEqual(JSON.parse(stored), subscription);
  const invalid = await handleRequest(request("/subscribe", { method: "POST", body: { endpoint: "http://not-secure" } }), env);
  assert.equal(invalid.status, 400);
  const deleted = await handleRequest(request("/subscribe", { method: "DELETE", body: subscription }), env);
  assert.equal(deleted.status, 200);
  assert.equal([...env.PUSH_SUBSCRIPTIONS.values.values()].some((value) => value.includes("push.example")), false);
});

test("send requires authentication and suppresses same-date same-state duplicates", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  const payload = { date: "2026-08-10", run_id: "run-1", type: "READY" };
  const unauthorized = await handleRequest(request("/send", { method: "POST", body: payload }), env);
  assert.equal(unauthorized.status, 401);
  let calls = 0;
  const sendNotification = async (stored, message) => {
    calls += 1;
    assert.deepEqual(stored, subscription);
    assert.equal(message.title, "오늘 브리핑 준비 완료");
  };
  const first = await handleRequest(
    request("/send", { method: "POST", body: payload, headers: { Authorization: `Bearer ${sendToken}` } }),
    env,
    undefined,
    { sendNotification },
  );
  assert.equal(first.status, 200);
  assert.deepEqual(await first.json(), { ok: true, duplicate: false, date: "2026-08-10", type: "READY", sent: 1, failed: 0, pruned: 0 });
  const second = await handleRequest(
    request("/send", { method: "POST", body: { ...payload, run_id: "run-2" }, headers: { Authorization: `Bearer ${sendToken}` } }),
    env,
    undefined,
    { sendNotification },
  );
  assert.equal(second.status, 200);
  assert.equal((await second.json()).duplicate, true);
  assert.equal(calls, 1);
});

test("watchdog emits one failure only when today's ready marker is absent", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  let calls = 0;
  const dependencies = {
    now: () => new Date("2026-08-10T00:00:00.000Z"),
    sendNotification: async (_subscription, message) => {
      calls += 1;
      assert.equal(message.title, "오늘 브리핑 업데이트 실패");
    },
  };
  const first = await runWatchdog(env, dependencies);
  assert.equal(first.type, "FAILURE");
  const second = await runWatchdog(env, dependencies);
  assert.equal(second.skipped, undefined);
  assert.equal(second.duplicate, true);
  assert.equal(calls, 1);
  await env.PUSH_SUBSCRIPTIONS.put("state:ready:2026-08-10", "ready");
  const ready = await runWatchdog(env, dependencies);
  assert.equal(ready.reason, "READY_ALREADY_RECORDED");
});
