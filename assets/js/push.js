(function () {
  "use strict";

  var root = document.querySelector("[data-push-settings]");
  if (!root) return;

  var enableButton = root.querySelector("[data-push-enable]");
  var disableButton = root.querySelector("[data-push-disable]");
  var status = root.querySelector("[data-push-status]");
  var workerUrl = (document.querySelector('meta[name="insight-desk-push-worker-url"]')?.content || "").replace(/\/$/, "");
  var serviceWorkerUrl = root.getAttribute("data-push-service-worker-url") || "push-sw.js";
  var standalone = Boolean(window.navigator.standalone) || window.matchMedia("(display-mode: standalone)").matches;
  var supported = Boolean(
    workerUrl &&
      standalone &&
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window,
  );

  function setStatus(message, tone) {
    if (!status) return;
    status.textContent = message;
    status.dataset.tone = tone || "";
  }

  function setBusy(busy) {
    enableButton.disabled = busy || !supported;
    disableButton.disabled = busy || !supported;
    root.setAttribute("aria-busy", busy ? "true" : "false");
  }

  function toUint8Array(value) {
    var padding = "=".repeat((4 - (value.length % 4)) % 4);
    var base64 = (value + padding).replace(/-/g, "+").replace(/_/g, "/");
    var binary = window.atob(base64);
    var output = new Uint8Array(binary.length);
    for (var index = 0; index < binary.length; index += 1) output[index] = binary.charCodeAt(index);
    return output;
  }

  async function getRegistration() {
    return navigator.serviceWorker.getRegistration(new URL("./", document.baseURI).href);
  }

  async function enable() {
    if (!supported) return;
    setBusy(true);
    try {
      var permission = Notification.permission;
      if (permission === "default") permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setStatus(permission === "denied" ? "알림 권한이 거부되었습니다." : "알림 권한을 확인하지 못했습니다.", "warning");
        return;
      }
      var registration = await navigator.serviceWorker.register(serviceWorkerUrl, { scope: "./" });
      var keyResponse = await fetch(workerUrl + "/vapid-public-key", { headers: { Accept: "application/json" } });
      if (!keyResponse.ok) throw new Error("public key unavailable");
      var keyBody = await keyResponse.json();
      if (!keyBody.public_key) throw new Error("public key missing");
      var subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: toUint8Array(keyBody.public_key),
        });
      }
      var response = await fetch(workerUrl + "/subscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(subscription.toJSON()),
      });
      if (!response.ok) throw new Error("subscription rejected");
      setStatus("알림 사용 중", "success");
    } catch (error) {
      console.warn("Insight Desk push setup failed", error);
      setStatus("알림을 켜지 못했습니다. 잠시 후 다시 시도하세요.", "warning");
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    if (!supported) return;
    setBusy(true);
    try {
      var registration = await getRegistration();
      var subscription = registration && (await registration.pushManager.getSubscription());
      if (subscription) {
        var response = await fetch(workerUrl + "/subscribe", {
          method: "DELETE",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(subscription.toJSON()),
        });
        if (!response.ok) throw new Error("unsubscribe rejected");
        await subscription.unsubscribe();
      }
      setStatus("알림 꺼짐", "");
    } catch (error) {
      console.warn("Insight Desk push disable failed", error);
      setStatus("알림을 끄지 못했습니다. 잠시 후 다시 시도하세요.", "warning");
    } finally {
      setBusy(false);
    }
  }

  if (!workerUrl) {
    setStatus("알림 연결을 준비 중입니다.", "");
  } else if (!standalone) {
    setStatus("홈 화면에 추가한 앱에서 알림을 켤 수 있습니다.", "");
  } else if (!supported) {
    setStatus("이 기기 또는 브라우저에서는 웹 알림을 지원하지 않습니다.", "warning");
  } else {
    setStatus(Notification.permission === "granted" ? "알림을 켜거나 끌 수 있습니다." : "사용자 탭 후 알림 권한을 요청합니다.", "");
  }
  setBusy(false);
  enableButton.addEventListener("click", enable);
  disableButton.addEventListener("click", disable);
}());
