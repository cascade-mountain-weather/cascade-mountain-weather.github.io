// Weather-term popups. Definitions come from _data/glossary.yml (embedded as JSON by _includes/glossary.html).
// Finds the first appearance of each term in <main> (and in content added later, like the model viewers' descriptions),
// wraps it in a button, and shows the definition in a small popup on click or tap.
(function () {
    var dataEl = document.getElementById('glossary-data');
    var root = document.querySelector('main');
    if (!dataEl || !root) return;
    var terms;
    try { terms = JSON.parse(dataEl.textContent); } catch (e) { return; }
    var byId = {};
    terms = terms.map(function (t) {
        var res = [];
        (t.patterns || []).forEach(function (p) { try { res.push(new RegExp(p, 'i')); } catch (e) {} });
        t.res = res; byId[t.id] = t;
        return t;
    });

    var SKIP = 'A,BUTTON,SELECT,OPTION,TEXTAREA,INPUT,LABEL,SCRIPT,STYLE,NOSCRIPT,SVG,CANVAS,CODE,PRE,SUMMARY,H1,H2,H3,H4,H5,H6,TITLE,IMG,IFRAME';
    var SKIP_SET = {}; SKIP.split(',').forEach(function (n) { SKIP_SET[n] = 1; });
    function skippable(el) {
        for (; el && el !== root; el = el.parentNode) {
            if (el.nodeType !== 1) continue;
            if (SKIP_SET[el.nodeName.toUpperCase()]) return true;
            if (el.hasAttribute('data-no-glossary') || el.classList.contains('gl-pop') || el.classList.contains('PlotTitle')) return true;
        }
        return false;
    }

    function firstMatch(text, t) {
        var best = null;
        t.res.forEach(function (re) {
            var g = new RegExp(re.source, 'gi'), m;
            while ((m = g.exec(text))) {
                var ok = true;
                (t.not_after || []).forEach(function (s) {
                    if (text.slice(Math.max(0, m.index - s.length), m.index).toLowerCase() === s.toLowerCase()) ok = false;
                });
                if (ok && m[0]) { if (!best || m.index < best.index || (m.index === best.index && m[0].length > best.len)) best = { index: m.index, len: m[0].length }; break; }
                if (g.lastIndex === m.index) g.lastIndex++;
            }
        });
        return best;
    }

    function scan(node) {
        var placed = {};
        root.querySelectorAll('.gl-term').forEach(function (b) { placed[b.getAttribute('data-gl')] = 1; });
        var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, null);
        var texts = [], n;
        while ((n = walker.nextNode())) { if (n.data.trim() && !skippable(n.parentNode)) texts.push(n); }
        texts.forEach(function (tn) {
            for (;;) {
                var pick = null;
                terms.forEach(function (t) {
                    if (placed[t.id]) return;
                    var m = firstMatch(tn.data, t);
                    if (m && (!pick || m.index < pick.m.index || (m.index === pick.m.index && m.len > pick.m.len))) pick = { t: t, m: m };
                });
                if (!pick) return;
                var rest = tn.splitText(pick.m.index);
                var after = rest.splitText(pick.m.len);
                var b = document.createElement('button');
                b.type = 'button'; b.className = 'gl-term'; b.setAttribute('data-gl', pick.t.id);
                b.setAttribute('aria-haspopup', 'true');
                b.setAttribute('aria-expanded', 'false');
                b.title = 'What is this? ' + pick.t.label;
                rest.parentNode.replaceChild(b, rest);
                b.appendChild(rest);
                placed[pick.t.id] = 1;
                tn = after;
            }
        });
    }

    // Popup
    var pop = document.createElement('div');
    pop.className = 'gl-pop'; pop.id = 'gl-pop'; pop.hidden = true; pop.setAttribute('role', 'note');
    document.body.appendChild(pop);
    var current = null;
    function close() { if (current) { current.setAttribute('aria-expanded', 'false'); current.removeAttribute('aria-describedby'); } current = null; pop.hidden = true; }
    function link(o, cls) { return o && o.url ? '<a href="' + o.url + '" target="_blank" rel="noopener noreferrer">' + o.label + '</a>' : ''; }
    function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function open(btn) {
        var t = byId[btn.getAttribute('data-gl')];
        if (!t) return;
        if (current) current.setAttribute('aria-expanded', 'false');
        current = btn; btn.setAttribute('aria-expanded', 'true'); btn.setAttribute('aria-describedby', 'gl-pop');
        pop.innerHTML = '<button type="button" class="gl-close" aria-label="Close">&times;</button><strong>' + esc(t.label) + '</strong><p>' + esc(t.text) + '</p>'
            + (t.more ? '<p>' + link(t.more) + '</p>' : '')
            + (t.credit ? '<small>' + (t.credit.url ? '<a href="' + t.credit.url + '" target="_blank" rel="noopener noreferrer">' + esc(t.credit.label) + '</a>' : esc(t.credit.label)) + '</small>' : '');
        pop.hidden = false;
        var r = btn.getBoundingClientRect(), sx = window.pageXOffset, sy = window.pageYOffset;
        var w = pop.offsetWidth, left = Math.max(sx + 8, Math.min(r.left + sx, sx + document.documentElement.clientWidth - w - 8));
        var top = r.bottom + sy + 6;
        if (r.bottom + pop.offsetHeight + 12 > window.innerHeight && r.top > pop.offsetHeight + 12) top = r.top + sy - pop.offsetHeight - 6;
        pop.style.left = left + 'px'; pop.style.top = top + 'px';
    }
    document.addEventListener('click', function (e) {
        var b = e.target.closest && e.target.closest('.gl-term');
        if (b) { e.preventDefault(); if (b === current && !pop.hidden) close(); else open(b); return; }
        if (e.target.closest && e.target.closest('.gl-close')) { var c = current; close(); if (c) c.focus(); return; }
        if (!(e.target.closest && e.target.closest('.gl-pop'))) close();
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && current) { var c = current; close(); c.focus(); } });
    window.addEventListener('resize', close);

    // Scan now, then again as pages add content (model viewers, meteograms, charts).
    var timer = null, pending = [];
    var mo = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
            m.addedNodes.forEach(function (n) {
                if (n.nodeType === 1 && !n.classList.contains('gl-term') && !skippable(n.parentNode)) pending.push(n);
                else if (n.nodeType === 3 && n.parentNode && !n.parentNode.classList.contains('gl-term') && !skippable(n.parentNode)) pending.push(n.parentNode);
            });
        });
        if (pending.length && !timer) timer = setTimeout(run, 200);
    });
    function run() {
        timer = null;
        var batch = pending; pending = [];
        mo.disconnect();
        batch.forEach(function (n) { if (root.contains(n)) scan(n); });
        mo.observe(root, { childList: true, subtree: true });
    }
    scan(root);
    mo.observe(root, { childList: true, subtree: true });
})();
