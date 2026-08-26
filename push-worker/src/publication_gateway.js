import baseWorker, {
  MAX_BODY_BYTES,
  handleRequest as handleCoreRequest,
  runWatchdog,
} from "./index.js";

export const PUBLICATION_BINDING_VERSION = 2;

const READY_STATE_PREFIX = "state:ready:";
const MARKER_TTL_SECONDS = 3 * 24 * 60 * 60;
const PUBLICATION_DIGEST_RE = /^[0-9a-f]{64}$/;
const BRIEFING_ID_RE = /^[A-Za-z0-9._:+-]{1,192}$/;
const RUN_ID_RE = /^[A-Za-z0-9._:-]{1,128}$/;
const VALID_SOURCES = new Set(["schedule", "manual", "other"]);
const READY_STATE_VALUES = new Set([
  "DELIVERED",
  "NO_SUBSCRIBERS",
  "STALE_SUBSCRIPTIONS_PRUNED",
]);

function responseWithJson(response, payload) {
  const headers = new Headers(response.headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  return new Response(JSON.stringify(payload), {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function readJsonClone(request) {
  const contentLength = Number(request.headers.get("Content-Length") || 0);
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return null;
  }
  const bytes = new Uint8Array(await request.clone().arrayBuffer());
  if (bytes.byteLength > MAX_BODY_BYTES) {
    return null;
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

function requestWithPayload(request, payload) {
  const headers = new Headers(request.headers);
  headers.set("Content-Type", "application/json");
  headers.delete("Content-Length");
  return new Request(request.url, {
    method: request.method,
    headers,
    body: JSON.stringify(payload),
  });
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(value, key);
}

function bindingFields(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { mode: "legacy" };
  }
  const hasBriefingId = hasOwn(value, "briefing_id");
  const hasDigest = hasOwn(value, "publication_digest");
  if (!hasBriefingId && !hasDigest) {
    return { mode: "legacy" };
  }
  if (hasBriefingId !== hasDigest) {
    return { mode: "invalid" };
  }
  const briefingId = value.briefing_id;
  const publicationDigest = value.publication_digest;
  const source = value.source === undefined ? "other" : value.source;
  if (
    value.type !== "READY"
    || typeof briefingId !== "string"
    || !BRIEFING_ID_RE.test(briefingId)
    || typeof publicationDigest !== "string"
    || !PUBLICATION_DIGEST_RE.test(publicationDigest)
    || !VALID_SOURCES.has(source)
    || typeof value.run_id !== "string"
    || !RUN_ID_RE.test(value.run_id)
  ) {
    return { mode: "invalid" };
  }
  return {
    mode: "bound",
    briefingId,
    publicationDigest,
    source,
    runId: value.run_id,
  };
}

function invalidPayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return value;
  }
  // Preserve core authentication/CORS behavior but force its existing payload validator to reject.
  return { ...value, run_id: "" };
}

async function persistPublicationReadyState(env, value, result) {
  if (
    !env?.PUSH_SUBSCRIPTIONS
    || typeof env.PUSH_SUBSCRIPTIONS.put !== "function"
    || !READY_STATE_VALUES.has(result?.delivery_state)
  ) {
    return;
  }
  await env.PUSH_SUBSCRIPTIONS.put(
    `${READY_STATE_PREFIX}${value.date}`,
    JSON.stringify({
      run_id: value.run_id,
      source: value.source,
      briefing_id: value.briefing_id,
      publication_digest: value.publication_digest,
      delivery_state: result.delivery_state,
      subscription_count: Number(result.subscription_count || 0),
      sent: Number(result.sent || 0),
      failed: Number(result.failed || 0),
      pruned: Number(result.pruned || 0),
      at: new Date().toISOString(),
    }),
    { expirationTtl: MARKER_TTL_SECONDS },
  );
}

async function handleHealth(request, env, context, dependencies) {
  const response = await handleCoreRequest(request, env, context, dependencies);
  if (response.status !== 200) {
    return response;
  }
  let payload;
  try {
    payload = await response.clone().json();
  } catch {
    return response;
  }
  return responseWithJson(response, {
    ...payload,
    publication_binding_version: PUBLICATION_BINDING_VERSION,
    publication_ready_identity: "briefing_id+sha256",
  });
}

export async function handlePublicationRequest(request, env, context, dependencies = {}) {
  const url = new URL(request.url);
  if (request.method.toUpperCase() === "GET" && url.pathname.replace(/\/+$/, "") === "/health") {
    return handleHealth(request, env, context, dependencies);
  }
  if (request.method.toUpperCase() !== "POST" || url.pathname.replace(/\/+$/, "") !== "/send") {
    return handleCoreRequest(request, env, context, dependencies);
  }

  const value = await readJsonClone(request);
  const binding = bindingFields(value);
  if (binding.mode === "legacy") {
    return handleCoreRequest(request, env, context, dependencies);
  }
  if (binding.mode === "invalid") {
    return handleCoreRequest(
      requestWithPayload(request, invalidPayload(value)),
      env,
      context,
      dependencies,
    );
  }

  // The delivery core already provides concurrency control and durable marker semantics for
  // manual run ids. Project the immutable publication digest into that idempotency slot so one
  // publication set is delivered once regardless of workflow run, while a genuinely changed
  // publication set on the same date receives a distinct delivery.
  const corePayload = {
    ...value,
    source: "manual",
    run_id: `publication-${binding.publicationDigest}`,
  };
  const coreResponse = await handleCoreRequest(
    requestWithPayload(request, corePayload),
    env,
    context,
    dependencies,
  );
  let result;
  try {
    result = await coreResponse.clone().json();
  } catch {
    return coreResponse;
  }
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    return coreResponse;
  }

  const publicationResult = {
    ...result,
    source: binding.source,
    briefing_id: binding.briefingId,
    publication_digest: binding.publicationDigest,
  };
  if (result.request_state === "REQUEST_ACCEPTED") {
    await persistPublicationReadyState(
      env,
      {
        date: value.date,
        run_id: binding.runId,
        source: binding.source,
        briefing_id: binding.briefingId,
        publication_digest: binding.publicationDigest,
      },
      publicationResult,
    );
  }
  return responseWithJson(coreResponse, publicationResult);
}

const worker = {
  async fetch(request, env, context) {
    return handlePublicationRequest(request, env, context);
  },
  async scheduled(_controller, env) {
    await runWatchdog(env);
  },
};

export default worker;
