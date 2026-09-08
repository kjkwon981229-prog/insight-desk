/* Notification-only service worker. It intentionally has no fetch handler. */
self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (_error) {
    data = { title: "Insight Desk", body: "새 브리핑 상태를 확인하세요." };
  }
  const title = typeof data.title === "string" && data.title ? data.title : "Insight Desk";
  const body = typeof data.body === "string" ? data.body : "새 브리핑 상태를 확인하세요.";
  const url = typeof data.url === "string" && data.url ? data.url : self.registration.scope;
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: typeof data.tag === "string" ? data.tag : "insight-desk",
      data: { url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = event.notification?.data?.url || self.registration.scope;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          if ("navigate" in client && client.url !== target) {
            client.navigate(target);
          }
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
