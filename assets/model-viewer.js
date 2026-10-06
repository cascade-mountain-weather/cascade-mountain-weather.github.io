// Shared model-image viewer for the synoptic and precipitation tool pages.
//
//   CMWViewer.mount(rootEl, { selectors: [...], resolve(state) { ... } })
//
// `selectors` are chip groups ({key, label, options: [{value,label}] or a
// function of the state}). `resolve(state)` returns the current product:
//   { title, hours: [0, 6, ...] | [null], urlFor(run, hour), runs: [Date, ...],
//     runExact: bool, info: { what, how, source, sourceUrl }, fallbackUrl }
// `runs` are candidate model runs, newest first; the viewer loads the first
// frame of each until one works, so a missing newest run falls back to the
// previous one. Single-image products use hours: [null].
(function () {
    'use strict';

    const PAC = 'America/Los_Angeles';
    const fmtPac = new Intl.DateTimeFormat('en-US', {
        timeZone: PAC, weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', timeZoneName: 'short',
    });
    const fmtDay = new Intl.DateTimeFormat('en-US', { timeZone: PAC, weekday: 'short', month: 'numeric', day: 'numeric' });
    const fmtDayKey = new Intl.DateTimeFormat('en-CA', { timeZone: PAC });
    const fmtOnlyHour = new Intl.DateTimeFormat('en-US', { timeZone: PAC, hour: 'numeric', hour12: false });
    const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    const pad = (n, w) => String(n).padStart(w || 2, '0');
    const zulu = d => `${pad(d.getUTCHours())}Z ${DOW[d.getUTCDay()]} ${d.getUTCMonth() + 1}/${d.getUTCDate()}`;
    const pacific = d => fmtPac.format(d).replace(',', '').replace(/,/g, '');
    const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    // "PDT (UTC-7)" or "PST (UTC-8)" for right now, so the explainer is never stale.
    function pacificNow() {
        const parts = new Intl.DateTimeFormat('en-US', { timeZone: PAC, timeZoneName: 'short' }).formatToParts(new Date());
        const abbr = (parts.find(p => p.type === 'timeZoneName') || {}).value || 'PT';
        return { abbr, offset: abbr === 'PDT' ? 7 : 8 };
    }

    function probe(url) {
        return new Promise(resolve => {
            const im = new Image();
            im.onload = () => resolve(true);
            im.onerror = () => resolve(false);
            im.src = url;
        });
    }

    function mount(root, cfg) {
        const state = {};
        // restore from the URL hash so a view can be shared
        const hash = new URLSearchParams(location.hash.slice(1));
        cfg.selectors.forEach(s => {
            const opts = typeof s.options === 'function' ? s.options(state) : s.options;
            const want = hash.get(s.key);
            state[s.key] = (opts.find(o => o.value === want) || opts[0]).value;
        });

        root.classList.add('mv');
        root.innerHTML = `
            <div class="mv-selectors"></div>
            <h2 class="mv-title" aria-live="polite"></h2>
            <div class="mv-stage">
                <img class="mv-img SynopticPlot" alt="" />
                <div class="mv-loading" hidden>Loading…</div>
                <div class="mv-fail" hidden></div>
            </div>
            <div class="mv-controls" hidden>
                <button type="button" class="mv-btn mv-prev" aria-label="Previous frame">&#9664;</button>
                <button type="button" class="mv-btn mv-play" aria-label="Play">&#9654;</button>
                <button type="button" class="mv-btn mv-next" aria-label="Next frame">&#9654;</button>
                <div class="mv-sliderwrap">
                    <input type="range" class="mv-slider" min="0" value="0" step="1" aria-label="Forecast hour" />
                    <div class="mv-days" aria-hidden="true"></div>
                </div>
                <button type="button" class="mv-btn mv-speed" aria-label="Playback speed">1\u00d7</button>
            </div>
            <div class="mv-time" aria-live="polite"></div>
            <figure class="mv-extra" hidden><img class="mv-extra-img" alt="" /><figcaption></figcaption></figure>
            <details class="mv-info" open>
                <summary>What this shows</summary>
                <div class="mv-info-body"></div>
            </details>
            <details class="mv-timeguide">
                <summary>Reading the times (Z = UTC)</summary>
                <div class="mv-timeguide-body"></div>
            </details>`;

        const $ = sel => root.querySelector(sel);
        const selBox = $('.mv-selectors'), titleEl = $('.mv-title'), img = $('.mv-img');
        const loadingEl = $('.mv-loading'), failEl = $('.mv-fail');
        const controls = $('.mv-controls'), slider = $('.mv-slider'), daysEl = $('.mv-days');
        const playBtn = $('.mv-play'), speedBtn = $('.mv-speed'), timeEl = $('.mv-time');
        const infoBody = $('.mv-info-body'), guideBody = $('.mv-timeguide-body');

        let view = null, run = null, idx = 0, timer = null, token = 0;
        const missing = new Set();
        const speeds = [1000, 500, 250];
        let speedI = 0;

        function renderSelectors() {
            selBox.innerHTML = '';
            cfg.selectors.forEach(s => {
                const opts = typeof s.options === 'function' ? s.options(state) : s.options;
                if (!opts.find(o => o.value === state[s.key])) state[s.key] = opts[0].value;
                if (opts.length < 2 && !s.alwaysShow) return;
                const g = document.createElement('div');
                g.className = 'mv-group';
                g.innerHTML = `<span class="mv-label" id="mvl-${s.key}">${esc(s.label)}</span>`;
                const chips = document.createElement('div');
                chips.className = s.select ? 'mv-select-wrap' : 'mv-chips';
                chips.setAttribute('role', s.select ? 'group' : 'radiogroup');
                chips.setAttribute('aria-labelledby', 'mvl-' + s.key);
                if (s.select) {
                    const sel = document.createElement('select');
                    sel.className = 'mv-select';
                    sel.setAttribute('aria-labelledby', 'mvl-' + s.key);
                    sel.innerHTML = opts.map(o => `<option value="${esc(o.value)}"${o.value === state[s.key] ? ' selected' : ''}>${esc(o.label)}</option>`).join('');
                    sel.addEventListener('change', () => { state[s.key] = sel.value; changed(); });
                    chips.appendChild(sel);
                } else {
                    opts.forEach(o => {
                        const b = document.createElement('button');
                        b.type = 'button';
                        b.className = 'mv-chip';
                        b.textContent = o.label;
                        b.setAttribute('role', 'radio');
                        b.setAttribute('aria-checked', o.value === state[s.key] ? 'true' : 'false');
                        b.addEventListener('click', () => { state[s.key] = o.value; changed(); });
                        chips.appendChild(b);
                    });
                }
                g.appendChild(chips);
                selBox.appendChild(g);
            });
        }

        let playing = false;
        function stop() {
            playing = false;
            if (timer) { clearTimeout(timer); timer = null; }
            playBtn.innerHTML = '&#9654;';
            playBtn.setAttribute('aria-label', 'Play');
            playBtn.classList.remove('is-playing');
        }

        function validTime(i) {
            const h = view.hours[i];
            return h == null || !run ? null : new Date(run.getTime() + h * 3600e3);
        }

        function renderTimes() {
            const h = view.hours[idx];
            const lines = [];
            if (run && h != null) {
                const v = validTime(idx);
                lines.push(`<div class="mv-valid"><strong>${esc(pacific(v))}</strong><span class="mv-z">${esc(zulu(v))}</span></div>`);
                lines.push(`<div class="mv-run">Forecast hour F${pad(h, 3)} &middot; ${esc((view.runLabel || 'model run').toLowerCase())} ${esc(zulu(run))} (${esc(pacific(run))})${view.runExact ? '' : ' &mdash; estimated, the image file does not say which run it is'}</div>`);
            } else if (h != null) {
                lines.push(`<div class="mv-run">Forecast hour F${pad(h, 3)}</div>`);
            } else if (run) {
                lines.push(`<div class="mv-run">${esc(view.runLabel || 'Model run')} ${esc(zulu(run))} (${esc(pacific(run))}). Dates on the figure may be Z (UTC); see &ldquo;Reading the times&rdquo; below.</div>`);
            } else {
                const note = view.latestNote || 'Always the most recent run available. The image itself carries the run and valid times.';
                lines.push(`<div class="mv-run">${esc(note)}</div>`);
            }
            timeEl.innerHTML = lines.join('');
        }

        const fmtWd = new Intl.DateTimeFormat('en-US', { timeZone: PAC, weekday: 'short' });
        function renderDays() {
            daysEl.innerHTML = '';
            if (!run || view.hours.length < 2) return;
            const n = view.hours.length - 1;
            const width = daysEl.parentNode.clientWidth || 200;
            let prev = null, lastX = -1e9;
            view.hours.forEach((_, i) => {
                const v = validTime(i);
                const key = fmtDayKey.format(v);
                if (key === prev) return;
                prev = key;
                const x = i / n * width;
                if (x - lastX < 36) return; // skip a label that would crowd the previous one
                lastX = x;
                const s = document.createElement('span');
                s.style.left = (i / n * 100) + '%';
                s.textContent = fmtWd.format(v);
                s.title = fmtDay.format(v);
                daysEl.appendChild(s);
            });
        }
        window.addEventListener('resize', () => { if (view && run) renderDays(); });

        function show(i, opts) {
            opts = opts || {};
            const dir = opts.dir || 1, n = view.hours.length;
            const t = ++token;
            idx = (i % n + n) % n;
            // step past frames already known to be missing
            for (let k = 0; k < n && missing.has(idx); k++) idx = (idx + dir + n) % n;
            slider.value = idx;
            const url = view.urlFor(run, view.hours[idx]);
            failEl.hidden = true;
            img.classList.add('is-loading');
            if (!opts.quiet) loadingEl.hidden = false;
            const pre = new Image();
            pre.onload = () => {
                if (t !== token) return;
                img.src = url;
                img.alt = `${view.title}${view.hours[idx] != null ? ', forecast hour ' + view.hours[idx] : ''}`;
                img.classList.remove('is-loading');
                loadingEl.hidden = true;
                renderTimes();
                if (opts.then) opts.then();
            };
            pre.onerror = () => {
                if (t !== token) return;
                // a frame the source does not have: remember it and move on to the next one
                if (n > 1 && missing.size < n - 1) {
                    missing.add(idx);
                    return show(idx + dir, Object.assign({}, opts));
                }
                stop();
                img.classList.remove('is-loading');
                loadingEl.hidden = true;
                fail();
            };
            pre.src = url;
        }

        function fail() {
            const link = view.fallbackUrl || (view.info && view.info.sourceUrl);
            failEl.innerHTML = `<p><strong>This image isn't loading right now.</strong></p>
                <p>The source site may be down, or may have moved this product.</p>
                ${link ? `<p><a href="${esc(link)}" target="_blank" rel="noopener noreferrer">Open the source page &rarr;</a></p>` : ''}`;
            failEl.hidden = false;
            img.removeAttribute('src');
        }

        function play() {
            if (playing) return stop();
            playing = true;
            playBtn.innerHTML = '&#10074;&#10074;';
            playBtn.setAttribute('aria-label', 'Pause');
            playBtn.classList.add('is-playing');
            const tick = () => show(idx + 1, { quiet: true, then: () => { if (playing) timer = setTimeout(tick, speeds[speedI]); } });
            tick();
        }

        function renderInfo() {
            const i = view.info || {};
            infoBody.innerHTML =
                (i.what ? `<h3>What is this?</h3><p>${i.what}</p>` : '') +
                (i.how ? `<h3>How to use it</h3><p>${i.how}</p>` : '') +
                (i.source ? `<p class="mv-source">Source: ${i.sourceUrl ? `<a href="${esc(i.sourceUrl)}" target="_blank" rel="noopener noreferrer">${esc(i.source)}</a>` : esc(i.source)}</p>` : '');
        }

        function renderGuide() {
            const p = pacificNow();
            const clock = h => { const x = ((h % 24) + 24) % 24; return `${x % 12 === 0 ? 12 : x % 12} ${x < 12 ? 'AM' : 'PM'}`; };
            guideBody.innerHTML = `<p>Forecast models run on <strong>UTC</strong> (&ldquo;Zulu&rdquo;, Z). Pacific time is currently <strong>${p.abbr}</strong>, UTC&minus;${p.offset}, so subtract ${p.offset} hours from a Z time.</p>
                <ul>
                    <li><strong>12Z</strong> = ${clock(12 - p.offset)} ${p.abbr}, same day</li>
                    <li><strong>18Z</strong> = ${clock(18 - p.offset)} ${p.abbr}, same day</li>
                    <li><strong>00Z</strong> = ${clock(-p.offset)} ${p.abbr}, <em>previous</em> calendar day</li>
                    <li><strong>06Z</strong> = ${clock(6 - p.offset)} ${p.abbr}, <em>previous</em> calendar day</li>
                </ul>
                <p>This page shows Pacific time first with the Z time beside it, and the day labels under the slider mark where each Pacific day begins. Clocks change on Nov&nbsp;1, 2026 (PDT to PST), which shifts the offset by an hour.</p>`;
        }

        async function load() {
            stop();
            view = cfg.resolve(state);
            missing.clear();
            titleEl.textContent = view.title;
            renderInfo();
            const extra = $('.mv-extra');
            if (view.extraImg) {
                $('.mv-extra-img').src = view.extraImg.url;
                $('.mv-extra-img').alt = view.extraImg.caption;
                extra.querySelector('figcaption').textContent = view.extraImg.caption;
                extra.hidden = false;
            } else extra.hidden = true;
            const multi = view.hours.length > 1;
            controls.hidden = !multi;
            slider.max = view.hours.length - 1;
            idx = Math.min(idx, view.hours.length - 1);
            if (!multi) idx = 0;
            img.alt = view.title;

            // choose the newest candidate run whose first frame exists
            run = null;
            if (view.runs && view.runs.length) {
                const t = ++token;
                loadingEl.hidden = false;
                for (const r of view.runs) {
                    if (await probe(view.urlFor(r, view.probeHour != null ? view.probeHour : view.hours[0]))) { run = r; break; }
                    if (t !== token) return;
                }
                if (!run) { loadingEl.hidden = true; fail(); renderTimes(); renderDays(); return; }
            }
            renderDays();
            renderTimes();
            show(idx);
        }

        function changed() {
            const p = new URLSearchParams();
            cfg.selectors.forEach(s => p.set(s.key, state[s.key]));
            try { history.replaceState(null, '', '#' + p.toString()); } catch (e) { /* file:// etc. */ }
            renderSelectors();
            load();
        }

        // controls
        $('.mv-prev').addEventListener('click', () => { stop(); show(idx - 1, { dir: -1 }); });
        $('.mv-next').addEventListener('click', () => { stop(); show(idx + 1); });
        playBtn.addEventListener('click', play);
        speedBtn.addEventListener('click', () => {
            speedI = (speedI + 1) % speeds.length;
            speedBtn.textContent = ['1\u00d7', '2\u00d7', '4\u00d7'][speedI];
        });
        slider.addEventListener('input', () => { stop(); show(+slider.value); });

        // swipe on the image: left = next, right = previous
        let sx = null;
        const stage = $('.mv-stage');
        stage.addEventListener('touchstart', e => { sx = e.touches.length === 1 ? e.touches[0].clientX : null; }, { passive: true });
        stage.addEventListener('touchend', e => {
            if (sx == null || view.hours.length < 2) return;
            const dx = e.changedTouches[0].clientX - sx;
            sx = null;
            if (Math.abs(dx) > 50) { stop(); const d = dx < 0 ? 1 : -1; show(idx + d, { dir: d }); }
        }, { passive: true });

        // keyboard: arrows step, space plays, when focus is inside the viewer
        root.addEventListener('keydown', e => {
            if (view.hours.length < 2 || /^(SELECT|INPUT)$/.test(e.target.tagName) && e.key === ' ') return;
            if (e.key === 'ArrowLeft') { e.preventDefault(); stop(); show(idx - 1, { dir: -1 }); }
            else if (e.key === 'ArrowRight') { e.preventDefault(); stop(); show(idx + 1); }
        });

        renderGuide();
        renderSelectors();
        load();
    }

    window.CMWViewer = { mount };
}());
