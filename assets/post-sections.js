// Collapsible post sections: Contents links open the section they jump to,
// and the Expand all / Collapse all buttons toggle every <details class="post-section">.
// Works without JS too (details/summary and plain anchors); this just adds the open-on-jump.
(function () {
  var sections = document.querySelectorAll('details.post-section');
  if (!sections.length) return;

  function openFor(hash) {
    if (!hash || hash.length < 2) return null;
    var target;
    try { target = document.getElementById(decodeURIComponent(hash.slice(1))); } catch (e) { return null; }
    if (!target) return null;
    var d = target.closest('details');
    if (d) d.open = true;
    return target;
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('a[href^="#"]');
    if (link) {
      var target = openFor(link.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        if (history.replaceState) history.replaceState(null, '', link.getAttribute('href'));
      }
      return;
    }
    var btn = e.target.closest('button[data-sections]');
    if (btn) {
      var open = btn.getAttribute('data-sections') === 'open';
      sections.forEach(function (d) { d.open = open; });
    }
  });

  window.addEventListener('hashchange', function () { openFor(location.hash); });
  if (location.hash) {
    var t = openFor(location.hash);
    if (t) setTimeout(function () { t.scrollIntoView(); }, 0);
  }
})();
