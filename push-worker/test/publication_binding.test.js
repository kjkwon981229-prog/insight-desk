import assert from "node:assert/strict";
import { test } from "node:test";

import worker, {
  PUBLICATION_BINDING_VERSION,
  handlePublicationRequest,
} from "../src/publication_gateway.js";

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
const sendToken = "test-send-token";

function base64Url(bytes) {
  return Buffer.from(bytes).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const subscription = {
  endpoint: "https://push.example.test/subscription/publication",
  keys: {
    p256dh: base64Url(new Uint8Array(65).fill(7)),
    auth: base64Url(new Uint8Array(16).fill(9)),
  },
};

function environment() {
  return {
    ALLOWED_ORIGIN: origin,
    VAPID_PUBLIC_KEY: base64Url(new Uint8Array(65).fill(3)),
    VAPID_PRIVATE_KEY: base64Url(new Uint8Array(32).fill(5)),
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

async function subscribe(env) {
  const response = await handlePublicationRequest(
    request("/subscribe", { method: "POST", body: subscription }),
    env,
  );
  assert.equal(response.status, 201);
}

function readyPayload({
  digest,
  briefingId = "daily-20260827T120000+0900",
  runId = "run-1",
  source = "schedule",
} = {}) {
  return {
    date: "2026-08-27",
    run_id: runId,
    type: "READY",
    source,
    briefing_id: briefingId,
    publication_digest: digest ?? "a".repeat(64),
  };
}

function send(env, payload, dependencies = {}) {
  return handlePublicationRequest(
    request("/send", {
      method: "POST",
      body: payload,
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    env,
    undefined,
    dependencies,
  );
}

test("health advertises the publication binding contract without exposing secrets", async () => {
  const env = environment();
  const response = await handlePublicationRequest(request("/health", { withOrigin: false }), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body.publication_binding_version, PUBLICATION_BINDING_VERSION);
  assert.equal(body.publication_binding_version, 2);
  assert.equal(body.publication_ready_identity, "briefing_id+sha256");
  assert.equal(body.notification_policy, "publication_ready_only");
  assert.equal(JSON.stringify(body).includes(env.VAPID_PRIVATE_KEY), false);
  assert.equal(JSON.stringify(body).includes(env.PUSH_SEND_TOKEN), false);
});

test("the deployed worker exposes no scheduled failure entrypoint", () => {
  assert.equal(worker.scheduled, undefined);
});

test("same publication digest deduplicates across workflow runs and records scheduled ready identity", async () => {
  const env = environment();
  await subscribe(env);
  let calls = 0;
  const dependencies = { sendNotification: async () => { calls += 1; } };
  const digest = "b".repeat(64);

  const first = await send(env, readyPayload({ digest, runId: "run-1" }), dependencies);
  const retry = await send(env, readyPayload({ digest, runId: "run-2" }), dependencies);

  assert.equal(first.status, 200);
  assert.equal(retry.status, 200);
  const firstBody = await first.json();
  const retryBody = await retry.json();
  assert.equal(firstBody.duplicate, false);
  assert.equal(retryBody.duplicate, true);
  assert.equal(firstBody.publication_digest, digest);
  assert.equal(retryBody.publication_digest, digest);
  assert.equal(firstBody.briefing_id, "daily-20260827T120000+0900");
  assert.equal(firstBody.source, "schedule");
  assert.equal(calls, 1);

  const ready = JSON.parse(await env.PUSH_SUBSCRIPTIONS.get("state:ready:2026-08-27"));
  assert.equal(ready.source, "schedule");
  assert.equal(ready.publication_digest, digest);
  assert.equal(ready.briefing_id, "daily-20260827T120000+0900");
  assert.equal(ready.delivery_state, "DELIVERED");
});

test("different publication digests on the same date are independent updates", async () => {
  const env = environment();
  await subscribe(env);
  const tags = [];
  const dependencies = {
    sendNotification: async (_subscription, message) => { tags.push(message.tag); },
  };

  const first = await send(
    env,
    readyPayload({ digest: "c".repeat(64), runId: "run-1" }),
    dependencies,
  );
  const second = await send(
    env,
    readyPayload({ digest: "d".repeat(64), runId: "run-2" }),
    dependencies,
  );

  assert.equal(first.status, 200);
  assert.equal(second.status, 200);
  assert.equal((await first.json()).duplicate, false);
  assert.equal((await second.json()).duplicate, false);
  assert.equal(tags.length, 2);
  assert.notEqual(tags[0], tags[1]);
  assert.match(tags[0], /publication-c{12}/);
  assert.match(tags[1], /publication-d{12}/);
});

test("publication identity deduplicates independently of notification source", async () => {
  const env = environment();
  await subscribe(env);
  let calls = 0;
  const dependencies = { sendNotification: async () => { calls += 1; } };
  const digest = "e".repeat(64);

  const manual = await send(
    env,
    readyPayload({ digest, runId: "manual-1", source: "manual" }),
    dependencies,
  );
  const scheduled = await send(
    env,
    readyPayload({ digest, runId: "scheduled-1", source: "schedule" }),
    dependencies,
  );

  assert.equal((await manual.json()).duplicate, false);
  assert.equal((await scheduled.json()).duplicate, true);
  assert.equal(calls, 1);
  const ready = JSON.parse(await env.PUSH_SUBSCRIPTIONS.get("state:ready:2026-08-27"));
  assert.equal(ready.source, "schedule");
  assert.equal(ready.publication_digest, digest);
});

test("partial or malformed publication identity fails the authenticated send contract", async () => {
  const env = environment();
  const auth = { Authorization: `Bearer ${sendToken}` };
  const partial = await handlePublicationRequest(
    request("/send", {
      method: "POST",
      body: {
        date: "2026-08-27",
        run_id: "run-1",
        type: "READY",
        briefing_id: "daily-20260827T120000+0900",
      },
      headers: auth,
    }),
    env,
  );
  assert.equal(partial.status, 400);
  assert.deepEqual(await partial.json(), { ok: false, error: "INVALID_NOTIFICATION" });

  const badDigest = await send(
    env,
    readyPayload({ digest: "not-a-sha256", runId: "run-2" }),
  );
  assert.equal(badDigest.status, 400);
  assert.deepEqual(await badDigest.json(), { ok: false, error: "INVALID_NOTIFICATION" });
});

test("an authenticated READY request cannot bypass publication identity", async () => {
  const env = environment();
  const response = await handlePublicationRequest(
    request("/send", {
      method: "POST",
      body: {
        date: "2026-08-27",
        run_id: "legacy-ready",
        type: "READY",
        source: "schedule",
      },
      headers: { Authorization: `Bearer ${sendToken}` },
    }),
    env,
  );
  assert.equal(response.status, 400);
  assert.deepEqual(await response.json(), { ok: false, error: "INVALID_NOTIFICATION" });
});

test("legacy READY without publication identity remains backward compatible", async () => {
  const env = environment();
  await subscribe(env);
  let calls = 0;
  const dependencies = { sendNotification: async () => { calls += 1; } };
  const payload = {
    date: "2026-08-27",
    run_id: "legacy-run",
    type: "READY",
    source: "schedule",
  };
  const first = await send(env, payload, dependencies);
  const second = await send(env, { ...payload, run_id: "legacy-retry" }, dependencies);
  assert.equal(first.status, 200);
  assert.equal((await first.json()).duplicate, false);
  assert.equal((await second.json()).duplicate, true);
  assert.equal(calls, 1);
});
