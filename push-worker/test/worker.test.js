import assert from "node:assert/strict";
import { test } from "node:test";

import { deliveryState, handleRequest } from "../src/index.js";

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

const subscriptionTwo = {
  endpoint: "https://push.example.test/subscription/two",
  keys: {
    p256dh: base64Url(new Uint8Array(65).fill(8)),
    auth: base64Url(new Uint8Array(16).fill(10)),
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

test("send requires authentication and suppresses same-source duplicates", async () => {
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
  assert.deepEqual(await first.json(), {
    ok: true,
    duplicate: false,
    request_state: "REQUEST_ACCEPTED",
    date: "2026-08-10",
    type: "READY",
    source: "other",
    delivery_state: "DELIVERED",
    subscription_count: 1,
    sent: 1,
    failed: 0,
    pruned: 0,
  });
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

test("manual READY and scheduled READY have separate idempotency identities", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  let calls = 0;
  const sendNotification = async () => { calls += 1; };
  const auth = { Authorization: `Bearer ${sendToken}` };
  const manual = await handleRequest(
    request("/send", { method: "POST", body: { date: "2026-08-18", run_id: "manual", type: "READY", source: "manual" }, headers: auth }),
    env,
    undefined,
    { sendNotification },
  );
  const scheduled = await handleRequest(
    request("/send", { method: "POST", body: { date: "2026-08-18", run_id: "scheduled", type: "READY", source: "schedule" }, headers: auth }),
    env,
    undefined,
    { sendNotification },
  );
  assert.equal(manual.status, 200);
  assert.equal(scheduled.status, 200);
  assert.equal((await scheduled.json()).duplicate, false);
  assert.equal(calls, 2);
});

test("distinct manual runs deliver independently while the same manual run dedupes", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  const auth = { Authorization: `Bearer ${sendToken}` };
  const tags = [];
  const sendNotification = async (_stored, message) => { tags.push(message.tag); };
  const send = (runId) => handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-21", run_id: runId, type: "READY", source: "manual" },
      headers: auth,
    }),
    env,
    undefined,
    { sendNotification },
  );

  const first = await send("manual-100-1");
  const retry = await send("manual-100-1");
  const secondRun = await send("manual-101-1");

  assert.equal(first.status, 200);
  assert.equal((await retry.json()).duplicate, true);
  assert.equal((await secondRun.json()).duplicate, false);
  assert.equal(tags.length, 2);
  assert.notEqual(tags[0], tags[1]);
  assert.match(tags[0], /manual-100-1$/);
  assert.match(tags[1], /manual-101-1$/);
});

test("same-isolate concurrent retries share one delivery operation", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  let calls = 0;
  let release;
  const blocked = new Promise((resolve) => { release = resolve; });
  const auth = { Authorization: `Bearer ${sendToken}` };
  const dependencies = {
    sendNotification: async () => {
      calls += 1;
      await blocked;
    },
  };
  const firstPromise = handleRequest(
    request("/send", { method: "POST", body: { date: "2026-08-19", run_id: "run-a", type: "READY", source: "schedule" }, headers: auth }),
    env,
    undefined,
    dependencies,
  );
  await new Promise((resolve) => setTimeout(resolve, 0));
  const secondPromise = handleRequest(
    request("/send", { method: "POST", body: { date: "2026-08-19", run_id: "run-b", type: "READY", source: "schedule" }, headers: auth }),
    env,
    undefined,
    dependencies,
  );
  release();
  const [first, second] = await Promise.all([firstPromise, secondPromise]);
  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal(calls, 1);
  assert.equal((await first.json()).duplicate, false);
  assert.equal((await second.json()).duplicate, true);
});

test("legacy delivery markers are normalized without an invalid response state", async () => {
  const env = environment();
  await env.PUSH_SUBSCRIPTIONS.put(
    "notify:2026-08-16:READY",
    JSON.stringify({ state: "sent", date: "2026-08-16", type: "READY", run_id: "legacy", sent: 0, failed: 0, pruned: 0 }),
  );
  const response = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-16", run_id: "retry", type: "READY", source: "other" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    env,
  );
  assert.equal(response.status, 202);
  assert.deepEqual(await response.json(), {
    ok: false,
    duplicate: true,
    request_state: "REQUEST_ACCEPTED",
    date: "2026-08-16",
    type: "READY",
    source: "other",
    delivery_state: "NO_SUBSCRIBERS",
    subscription_count: 0,
    sent: 0,
    failed: 0,
    pruned: 0,
  });
});

test("delivery states distinguish no subscribers, partial delivery, total failure, and stale pruning", async () => {
  assert.equal(deliveryState({ subscriptionCount: 0, sent: 0, failed: 0, pruned: 0 }), "NO_SUBSCRIBERS");
  assert.equal(deliveryState({ subscriptionCount: 2, sent: 1, failed: 1, pruned: 0 }), "PARTIAL_DELIVERY");
  assert.equal(deliveryState({ subscriptionCount: 1, sent: 0, failed: 1, pruned: 1 }), "ALL_DELIVERIES_FAILED");
  assert.equal(deliveryState({ subscriptionCount: 1, sent: 0, failed: 0, pruned: 1 }), "STALE_SUBSCRIPTIONS_PRUNED");

  const empty = environment();
  const noSubscribers = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-11", run_id: "no-subs", type: "READY", source: "schedule" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    empty,
    undefined,
    { sendNotification: async () => {} },
  );
  assert.equal(noSubscribers.status, 202);
  assert.equal((await noSubscribers.json()).delivery_state, "NO_SUBSCRIBERS");

  const partial = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), partial);
  await handleRequest(request("/subscribe", { method: "POST", body: subscriptionTwo }), partial);
  let attempt = 0;
  const partialResponse = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-12", run_id: "partial", type: "READY", source: "schedule" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    partial,
    undefined,
    {
      sendNotification: async () => {
        attempt += 1;
        if (attempt === 2) throw new Error("provider unavailable");
      },
    },
  );
  assert.equal(partialResponse.status, 502);
  assert.equal((await partialResponse.json()).delivery_state, "PARTIAL_DELIVERY");
  assert.equal(await partial.PUSH_SUBSCRIPTIONS.get("state:ready:2026-08-12"), null);

  const failed = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), failed);
  const failedResponse = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-13", run_id: "failed", type: "READY", source: "schedule" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    failed,
    undefined,
    { sendNotification: async () => { throw new Error("provider unavailable"); } },
  );
  assert.equal(failedResponse.status, 502);
  assert.equal((await failedResponse.json()).delivery_state, "ALL_DELIVERIES_FAILED");
  assert.equal(await failed.PUSH_SUBSCRIPTIONS.get("state:ready:2026-08-13"), null);

  const stale = environment();
  await stale.PUSH_SUBSCRIPTIONS.put("sub:stale", "not-json");
  const staleResponse = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-14", run_id: "stale", type: "READY", source: "schedule" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    stale,
    undefined,
    { sendNotification: async () => {} },
  );
  assert.equal(staleResponse.status, 502);
  assert.equal((await staleResponse.json()).delivery_state, "STALE_SUBSCRIPTIONS_PRUNED");
});

test("failure notifications are rejected without contacting subscribers", async () => {
  const env = environment();
  await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  let calls = 0;
  const response = await handleRequest(
    request("/send", {
      method: "POST",
      body: { date: "2026-08-10", run_id: "failed", type: "FAILURE", source: "schedule" },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    env,
    undefined,
    { sendNotification: async () => { calls += 1; } },
  );
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { ok: false, error: "INVALID_NOTIFICATION" });
  assert.equal(calls, 0);
});

test("subscription writes enforce the configured maximum", async () => {
  const env = environment();
  env.MAX_SUBSCRIPTIONS = 1;
  const first = await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  assert.equal(first.status, 201);
  const second = await handleRequest(request("/subscribe", { method: "POST", body: subscriptionTwo }), env);
  assert.equal(second.status, 429);
  assert.deepEqual(await second.json(), { ok: false, error: "SUBSCRIPTION_LIMIT" });
  const update = await handleRequest(request("/subscribe", { method: "POST", body: subscription }), env);
  assert.equal(update.status, 201);
});

test("concurrent subscription writes serialize the local capacity check", async () => {
  const env = environment();
  env.MAX_SUBSCRIPTIONS = 1;
  const [first, second] = await Promise.all([
    handleRequest(request("/subscribe", { method: "POST", body: subscription }), env),
    handleRequest(request("/subscribe", { method: "POST", body: subscriptionTwo }), env),
  ]);
  assert.deepEqual([first.status, second.status].sort(), [201, 429]);
});
