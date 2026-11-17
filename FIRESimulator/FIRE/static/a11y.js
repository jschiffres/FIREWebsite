// Accessibility enhancements applied on load and after every htmx swap.
(function () {
  function enhance(root) {
    root.querySelectorAll('i.bi:not([aria-label]):not([aria-hidden])').forEach(function (icon) {
      icon.setAttribute('aria-hidden', 'true');
    });
    root.querySelectorAll('thead th:not([scope])').forEach(function (th) {
      th.setAttribute('scope', 'col');
    });
    root.querySelectorAll('table.table').forEach(function (table) {
      if (table.closest('.table-responsive, .pricing-table-wrap')) return;
      var wrap = document.createElement('div');
      wrap.className = 'table-responsive';
      table.parentNode.insertBefore(wrap, table);
      wrap.appendChild(table);
    });
    root.querySelectorAll('canvas:not([role])').forEach(function (canvas) {
      if (!canvas.hasAttribute('aria-label')) return;
      canvas.setAttribute('role', 'img');
    });
  }
  function run(root) { enhance(root || document); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { run(); });
  else run();
  document.addEventListener('htmx:afterSwap', function (event) { run(event.detail && event.detail.target || document); });
})();
