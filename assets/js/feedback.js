(function () {
  "use strict";

  var STORAGE_KEY = "insight-desk:v1";
  var MAX_SAVED = 300;
  var main = document.querySelector("main.shell");
  if (!main) return;

  /* 좋다/별로다 기록은 이 기기의 localStorage에만 남고 어디로도 보내지 않는다. */

  function load() {
    try {
      var raw = window.localStorage.getItem(STORAGE_KEY);
      var parsed = raw ? JSON.parse(raw) : null;
      if (parsed && typeof parsed === "object" && parsed.votes && parsed.saved) return parsed;
    } catch (error) {
      /* storage blocked or corrupt: start empty */
    }
    return { votes: {}, saved: {} };
  }

  var state = load();

  function persist() {
    try {
      var ids = Object.keys(state.saved);
      if (ids.length > MAX_SAVED) {
        ids.sort(function (a, b) { return (state.saved[a].at || 0) - (state.saved[b].at || 0); });
        ids.slice(0, ids.length - MAX_SAVED).forEach(function (id) { delete state.saved[id]; });
      }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (error) {
      /* the page keeps working without storage */
    }
  }

  function text(node) {
    return node ? node.textContent.replace(/\s+/g, " ").trim() : "";
  }

  function snapshot(article) {
    var source = article.querySelector("a.story-source");
    return {
      title: text(article.querySelector("h3")),
      reason: text(article.querySelector("p.story-reason")),
      lines: Array.prototype.map.call(article.querySelectorAll("ul.story-core > li"), text),
      summary: text(article.querySelector("p.story-summary")),
      topic: text(article.querySelector(".story-topic")),
      url: source ? source.getAttribute("href") : "",
      day: (main.getAttribute("data-briefing-id") || "").slice(6, 14),
      at: Date.now(),
    };
  }

  function paint(article) {
    var id = article.getAttribute("data-event-id");
    var vote = state.votes[id] || "";
    article.setAttribute("data-vote", vote);
    Array.prototype.forEach.call(article.querySelectorAll("button[data-action]"), function (button) {
      button.setAttribute("aria-pressed", button.getAttribute("data-action") === vote ? "true" : "false");
    });
  }

  function onVote(button) {
    var article = button.closest("article.story-row");
    if (!article) return;
    var id = article.getAttribute("data-event-id");
    var action = button.getAttribute("data-action");
    if (state.votes[id] === action) {
      delete state.votes[id];
      delete state.saved[id];
    } else {
      state.votes[id] = action;
      if (action === "good") {
        state.saved[id] = snapshot(article);
      } else {
        delete state.saved[id];
      }
    }
    persist();
    paint(article);
    renderCollection();
  }

  var collection = document.getElementById("collection-list");

  function renderCollection() {
    if (!collection) return;
    var ids = Object.keys(state.saved).sort(function (a, b) { return state.saved[b].at - state.saved[a].at; });
    collection.textContent = "";
    var empty = document.getElementById("collection-empty");
    if (empty) empty.hidden = ids.length > 0;
    ids.forEach(function (id) {
      var item = state.saved[id];
      var card = document.createElement("article");
      card.className = "saved-card";
      var meta = document.createElement("p");
      meta.className = "saved-meta";
      meta.textContent = [item.topic, item.day ? item.day.slice(0, 4) + "." + item.day.slice(4, 6) + "." + item.day.slice(6, 8) : ""].filter(Boolean).join(" · ");
      var title = document.createElement("h3");
      title.textContent = item.title;
      card.appendChild(meta);
      card.appendChild(title);
      if (item.reason) {
        var reason = document.createElement("p");
        reason.className = "story-reason";
        reason.textContent = item.reason;
        card.appendChild(reason);
      }
      var lines = item.lines && item.lines.length ? item.lines : item.summary ? [item.summary] : [];
      if (lines.length) {
        var list = document.createElement("ul");
        list.className = "story-core";
        lines.forEach(function (line) {
          var li = document.createElement("li");
          li.textContent = line;
          list.appendChild(li);
        });
        card.appendChild(list);
      }
      var actions = document.createElement("div");
      actions.className = "story-actions";
      if (/^https?:\/\//.test(item.url || "")) {
        var link = document.createElement("a");
        link.className = "story-source";
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "원문";
        actions.appendChild(link);
      }
      var remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "빼기";
      remove.addEventListener("click", function () {
        delete state.saved[id];
        if (state.votes[id] === "good") delete state.votes[id];
        persist();
        renderCollection();
        Array.prototype.forEach.call(document.querySelectorAll("article.story-row"), paint);
      });
      actions.appendChild(remove);
      card.appendChild(actions);
      collection.appendChild(card);
    });
  }

  function showView(name) {
    var views = ["today", "collection", "settings"];
    if (views.indexOf(name) < 0) name = "today";
    main.setAttribute("data-view", name);
    Array.prototype.forEach.call(document.querySelectorAll(".tabbar a"), function (link) {
      if (link.getAttribute("data-view") === name) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function fromHash() {
    var name = (window.location.hash || "").replace("#", "");
    showView(name === "collection" || name === "settings" ? name : "today");
  }

  main.addEventListener("click", function (event) {
    var button = event.target.closest && event.target.closest("button[data-action]");
    if (button) onVote(button);
  });
  var clear = document.getElementById("clear-saved");
  if (clear) {
    clear.addEventListener("click", function () {
      state = { votes: {}, saved: {} };
      persist();
      Array.prototype.forEach.call(document.querySelectorAll("article.story-row"), paint);
      renderCollection();
    });
  }
  window.addEventListener("hashchange", fromHash);
  Array.prototype.forEach.call(document.querySelectorAll("article.story-row"), paint);
  renderCollection();
  fromHash();
}());
