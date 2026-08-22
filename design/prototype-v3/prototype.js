(() => {
  const root = document.querySelector('[data-ui-v3-prototype]');
  if (!root) return;

  const buttons = [...root.querySelectorAll('[data-view-button]')];
  const views = [...root.querySelectorAll('[data-view]')];
  const validViews = new Set(views.map((view) => view.dataset.view));

  function activate(name, { updateHash = true } = {}) {
    const next = validViews.has(name) ? name : 'home';
    views.forEach((view) => {
      view.dataset.active = String(view.dataset.view === next);
    });
    buttons.forEach((button) => {
      const selected = button.dataset.viewButton === next;
      button.setAttribute('aria-pressed', String(selected));
    });
    if (updateHash) history.replaceState(null, '', `#${next}`);
  }

  buttons.forEach((button) => {
    button.addEventListener('click', () => activate(button.dataset.viewButton));
  });

  window.addEventListener('hashchange', () => activate(location.hash.slice(1), { updateHash: false }));
  activate(location.hash.slice(1) || 'home', { updateHash: false });
})();
