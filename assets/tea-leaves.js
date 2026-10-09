// "Reading the Tea Leaves": predict the Cascades pattern from the current state of the PNA, ENSO, PDO and the MJO.
// Data: assets/data/tele_joint.json (joint regression of 36 SNOTEL stations, Nov-May 1992-2026; scripts/tele_export_joint.py),
// assets/data/tele_now.json (observed PNA and the GEFS PNA forecast, the observed MJO; scripts/tele_now.py, daily bot) and
// assets/data/climate_indices.json (latest ONI and PDO). Mount: <div class="tl-mount"></div>.
// Automatic mode reads those and predicts two windows (the next 7 days, days 8 to 14). "Your own values" lets a reader try other
// numbers, such as one ensemble member. Effect for a tier and measure = sum(b_i * z_i) + (c_phase - sum(f_k * c_k)): the departure
// from an average day. A pattern is named only when its approximate 90% range excludes zero.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const TIERS = [['all', 'All stations'], ['low', 'Low, under 4,000 ft'], ['mid', 'Mid, 4,000 to 5,000 ft'], ['high', 'High, 5,000 ft and up']];
    const NOTE = { low: 'Mostly near the rain-snow line: snow responds most.', mid: '', high: 'Temperature responds most; snowfall less.', all: '' };
    const CAP = 1.5;      // the fit is a straight line and few winters are extreme: an input is held at 1.5 standard deviations
    const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const iso = d => d.toISOString().slice(0, 10);
    const addDays = (d, n) => new Date(d.getTime() + n * 864e5);
    const md = d => `${MON[d.getUTCMonth()]} ${d.getUTCDate()}`;
    const signed = (v, dp) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(dp);
    const latest = s => { for (let i = s.values.length - 1; i >= 0; i--) if (s.values[i] != null) return s.values[i]; return 0; };

    function mount(root, J, CI, NOW) {
        const f = J.mjo_freq;
        const oni = CI ? +latest(CI.oni).toFixed(2) : 0, pdo = CI ? +latest(CI.pdo).toFixed(2) : 0;
        const z = (t, v) => Math.max(-CAP, Math.min(CAP, (v - J.stats[t].mean) / J.stats[t].sd));
        const heldTxt = t => { const v = t === 'ONI' ? oni : pdo; return Math.abs((v - J.stats[t].mean) / J.stats[t].sd) > CAP; };

        // ---- inputs for one target day, from the data feeds ----
        const gen = NOW && NOW.generated_utc ? new Date(NOW.generated_utc.slice(0, 10) + 'T00:00:00Z') : new Date();
        const pnaMap = {}, pnaSpread = {};
        if (NOW && NOW.pna) { NOW.pna.obs.forEach(o => { pnaMap[o.date] = o.v; }); NOW.pna.gefs.forEach(g => { pnaMap[g.date] = g.mean; pnaSpread[g.date] = (g.p90 - g.p10) / 2; }); }
        const mjoMap = {};
        if (NOW && NOW.mjo) NOW.mjo.series.forEach(s => { mjoMap[s.date] = s; });
        function pna5(d) { const v = []; for (let k = -2; k <= 2; k++) { const x = pnaMap[iso(addDays(d, k))]; if (x != null) v.push(x); } return v.length >= 3 ? v.reduce((a, b) => a + b, 0) / v.length : null; }
        function dayInputs(d) {
            const m = mjoMap[iso(addDays(d, -J.lag))];
            return { pna: pna5(d), spread: pnaSpread[iso(d)] != null ? pnaSpread[iso(d)] : 0, mjo: m ? m.phase : null };
        }
        function windowInputs(from, to) {
            const days = []; for (let i = from; i <= to; i++) days.push(addDays(gen, i));
            const di = days.map(dayInputs);
            const pv = di.map(x => x.pna).filter(v => v != null);
            const mj = di.map(x => x.mjo).filter(v => v != null);
            return { days, di, from: days[0], to: days[days.length - 1],
                pna: pv.length ? pv.reduce((a, b) => a + b, 0) / pv.length : null, spread: di.reduce((a, x) => a + x.spread, 0) / di.length, mjos: mj, nDays: days.length };
        }

        // ---- effect of one set of inputs: returns {v, h} per metric ----
        function effectOne(tier, metric, inp) {
            const c = J.tiers[tier][metric];
            let v = 0, h2 = 0;
            const zs = { PNA: inp.pna == null ? 0 : z('PNA', inp.pna), ONI: z('ONI', inp.oni), PDO: z('PDO', inp.pdo) };
            ['PNA', 'ONI', 'PDO'].forEach(t => { v += c[t][0] * zs[t]; h2 += Math.pow((c[t][2] - c[t][1]) / 2 * Math.abs(zs[t]), 2); });
            if (inp.pna != null && inp.spread) h2 += Math.pow(c.PNA[0] * inp.spread / J.stats.PNA.sd, 2);            // spread among the forecast members
            if (inp.mjo != null) {
                let avg = 0; for (let k = 1; k <= 8; k++) avg += f[k] * c['MJO' + k][0];
                const cm = inp.mjo ? c['MJO' + inp.mjo] : [0, 0, 0];
                v += cm[0] - avg; h2 += Math.pow((cm[2] - cm[1]) / 2, 2);
            }
            return { v, h: Math.sqrt(h2) };
        }
        // a window averages its days (each with its own MJO phase); a manual setting is one set of inputs
        function effectWin(tier, metric, W) {
            if (W.manual) return effectOne(tier, metric, W.manual);
            let v = 0, h = 0;
            W.di.forEach(x => { const e = effectOne(tier, metric, { pna: x.pna, spread: x.spread, oni, pdo, mjo: x.mjo }); v += e.v; h += e.h; });
            return { v: v / W.di.length, h: h / W.di.length };
        }
        const sign = e => (e.v - e.h > 0 ? 1 : e.v + e.h < 0 ? -1 : 0);
        function classify(tier, W) {
            const T = effectWin(tier, 'tanom', W), Sn = effectWin(tier, 'swe', W), R = effectWin(tier, 'rain', W), B = effectWin(tier, 'bigsnow', W);
            const t = sign(T), s = sign(Sn), r = sign(R), b = sign(B);
            let label, tone;
            if (t < 0 && (s > 0 || b > 0)) { label = 'Cooler and snowier'; tone = 'good'; }
            else if (t < 0) { label = s < 0 ? 'Cooler and drier' : 'Cooler'; tone = 'cool'; }
            else if (t > 0 && r > 0) { label = 'Warmer and wetter: rain-on-snow risk'; tone = 'warn'; }
            else if (t > 0 && s < 0) { label = 'Warmer with less snow'; tone = 'warn'; }
            else if (t > 0) { label = 'Warmer'; tone = 'warm'; }
            else if (s > 0 || b > 0) { label = 'Snowier'; tone = 'good'; }
            else if (s < 0) { label = 'Less snow'; tone = 'warn'; }
            else if (r > 0) { label = 'Rainier'; tone = 'warn'; }
            else if (r < 0) { label = 'Less rain'; tone = 'cool'; }
            else { label = 'No clear signal'; tone = 'none'; }
            return { label, tone, T, W: Sn, R, B };
        }

        const hasFeed = !!(NOW && NOW.pna && NOW.mjo);
        const wins = hasFeed ? [
            Object.assign({ id: 'w1', label: 'Next 7 days' }, windowInputs(1, 7)),
            Object.assign({ id: 'w2', label: 'Days 8 to 14' }, windowInputs(8, 14)),
        ] : [];
        const S = { sel: hasFeed ? 'w1' : 'own', own: { pna: 0, oni, pdo, mjo: null, spread: 0 } };
        if (hasFeed && wins[0].pna != null) { S.own.pna = +wins[0].pna.toFixed(1); }
        const range = w => `${md(w.from)} to ${md(w.to)}`;

        const pct = e => `${e.v >= 0 ? '+' : '−'}${Math.abs(Math.round(e.v * 100))}% <small>(±${Math.round(e.h * 100)})</small>`;
        const deg = e => `${e.v >= 0 ? '+' : '−'}${Math.abs(e.v).toFixed(1)} °F <small>(±${e.h.toFixed(1)})</small>`;
        const cls = (e, up) => { const s = sign(e); return s === 0 ? 'tl-n' : (s > 0) === up ? 'tl-g' : 'tl-b'; };
        const pnaWord = v => v <= -1.0 ? 'strong negative' : v <= -0.35 ? 'negative' : v < 0.45 ? 'near neutral' : v < 0.95 ? 'positive' : 'strong positive';
        const ensoWord = v => v >= 1 ? 'El Niño' : v >= 0.5 ? 'weak El Niño' : v <= -1 ? 'La Niña' : v <= -0.5 ? 'weak La Niña' : 'neutral';
        const MJO = [[null, 'Not given'], [0, 'Weak'], ...[1, 2, 3, 4, 5, 6, 7, 8].map(k => [k, 'Phase ' + k])];

        function windowOf(id) { return id === 'own' ? { id: 'own', label: 'Your own values', manual: S.own, di: [] } : wins.find(w => w.id === id); }

        function inputsSummary(W) {
            if (W.id === 'own') return 'The values you set below, applied to every day of the period. This is for trying a number you saw in an ensemble member or a different forecast.';
            const known = W.mjos.length, last = NOW && NOW.mjo && NOW.mjo.series.length ? NOW.mjo.series[NOW.mjo.series.length - 1].date : null;
            const when = W.id === 'w1' ? 'the next 7 days' : 'days 8 to 14', missing = W.nDays - known;
            const mjTxt = `The MJO phase used here is taken from ${J.lag} days before a given day because its effect on PNW snow is delayed about 1 week. `
                + (last ? `The most recent MJO value is from ${md(new Date(last + 'T00:00:00Z'))}, so for ${when} the phase is known for ${known} of ${W.nDays} days. ` : '')
                + (missing === 0 ? '' : known === 0 ? 'None of these days has an MJO input yet, so the prediction is made from the PNA, ENSO and PDO alone.'
                    : `The other ${missing} days have no MJO input yet, so for those days the prediction is made from the PNA, ENSO and PDO alone.`);
            return `<strong>What went in (${range(W)}):</strong> PNA ${W.pna == null ? 'no data' : signed(W.pna, 1) + ' (' + pnaWord(W.pna) + ')'}${W.spread ? ' &plusmn;' + W.spread.toFixed(1) + ' among forecast members' : ''}; ENSO ${signed(oni, 1)} (${ensoWord(oni)})${heldTxt('ONI') ? ', counted as +1.4 because few winters were that extreme' : ''}; PDO ${signed(pdo, 1)}. ${mjTxt}`;
        }

        function render() {
            const W = windowOf(S.sel);
            const rows = TIERS.map(([k, label]) => ({ k, label, c: classify(k, W) }));
            const overview = hasFeed ? `<table class="tl-over"><thead><tr><th></th>${TIERS.map(t => `<th>${esc(t[1])}</th>`).join('')}</tr></thead><tbody>${wins.map(w => `<tr><th><button type="button" class="tl-rowbtn" data-sel="${w.id}" aria-pressed="${S.sel === w.id}">${esc(w.label)}<small>${range(w)}</small></button></th>${TIERS.map(([k]) => { const c = classify(k, w); return `<td class="tl-${c.tone}">${esc(c.label)}</td>`; }).join('')}</tr>`).join('')}</tbody></table>` : '';
            const own = S.own;
            const offSeason = gen.getUTCMonth() >= 5 && gen.getUTCMonth() <= 9;      // June to October
            root.innerHTML = `<div class="tl">
                ${offSeason ? '<p class="ci-note">The relationships here were measured from November through May. Outside the ski season they are only a rough guide, and the SNOTEL snow measures mean nothing with no snow on the ground, so treat these numbers as a preview of how the tool will read once the season starts.</p>' : ''}
                ${hasFeed ? `<p class="ci-hint">Read automatically from the latest data (updated daily): the observed PNA and the GEFS PNA forecast (${esc(NOW.pna.gefs_init)} run, ${NOW.pna.gefs[0] ? NOW.pna.gefs[0].n : ''} members), the MJO index through ${esc(NOW.mjo.series[NOW.mjo.series.length - 1].date)}, and the latest ENSO and PDO. Select a row to see the detail, or choose your own values.</p>${overview}`
                    : '<p class="ci-note">The live data feed is not available right now, so this is set up with your own values.</p>'}
                <div class="ol-chips tl-sel" role="radiogroup" aria-label="Period">${wins.map(w => `<button type="button" class="ol-chip" role="radio" aria-checked="${S.sel === w.id}" data-sel="${w.id}">${esc(w.label)}, ${range(w)}</button>`).join('')}
                    <button type="button" class="ol-chip" role="radio" aria-checked="${S.sel === 'own'}" data-sel="own">Your own values</button></div>
                <p class="ci-hint">${inputsSummary(W)}</p>
                ${S.sel === 'own' ? `<div class="tl-inputs">
                    <div class="ol-group"><label class="ol-label" for="tl-pna">PNA (5-day mean): <b>${signed(own.pna, 1)}</b> <span class="tl-w">${pnaWord(own.pna)}</span></label><input id="tl-pna" type="range" min="-2.5" max="2.5" step="0.1" value="${own.pna}"></div>
                    <div class="ol-group"><label class="ol-label" for="tl-oni">ENSO, ONI: <b>${signed(own.oni, 1)}</b> <span class="tl-w">${ensoWord(own.oni)}</span></label><input id="tl-oni" type="range" min="-2.5" max="2.5" step="0.1" value="${own.oni}"></div>
                    <div class="ol-group"><label class="ol-label" for="tl-pdo">PDO: <b>${signed(own.pdo, 1)}</b></label><input id="tl-pdo" type="range" min="-3" max="3" step="0.1" value="${own.pdo}"></div>
                    <div class="ol-group tl-mjo"><span class="ol-label">MJO phase about ${J.lag} days before the period (read it from the figures below)</span>
                        <div class="ol-chips" role="radiogroup" aria-label="MJO phase">${MJO.map(([k, l]) => `<button type="button" class="ol-chip" role="radio" aria-checked="${k === own.mjo}" data-mjo="${k}">${l}</button>`).join('')}</div></div>
                    ${hasFeed ? '<div class="ol-group"><button type="button" class="ol-chip" id="tl-reset">Reset to the automatic values</button></div>' : ''}
                </div>` : ''}
                ${[['ONI', own.oni], ['PDO', own.pdo], ['PNA', own.pna]].some(([t, v]) => S.sel === 'own' && Math.abs((v - J.stats[t].mean) / J.stats[t].sd) > CAP) ? `<p class="ci-note">One of your values is beyond what the 35 winters can speak to. It is held at 1.5 standard deviations, so the result is conservative.</p>` : ''}
                <div class="tl-grid">${rows.map(r => `<div class="tl-card tl-${r.c.tone}">
                    <h3>${esc(r.label)}</h3>
                    <p class="tl-verdict">${esc(r.c.label)}</p>
                    <table><tbody>
                        <tr><th>Temperature</th><td class="${cls(r.c.T, false)}">${deg(r.c.T)}</td></tr>
                        <tr><th>New snow</th><td class="${cls(r.c.W, true)}">${pct(r.c.W)}</td></tr>
                        <tr><th>Big snow days</th><td class="${cls(r.c.B, true)}">${pct(r.c.B)}</td></tr>
                        <tr><th>Rain</th><td class="tl-n">${pct(r.c.R)}</td></tr>
                    </tbody></table>
                    ${NOTE[r.k] ? `<p class="tl-note">${NOTE[r.k]}</p>` : ''}</div>`).join('')}</div>
                <p class="ci-hint">Changes are against an average day in the November to May record, with the approximate 90% range in parentheses. Colors: green is favorable for snow, red is unfavorable, gray is within the noise.</p>
            </div>`;
            root.querySelectorAll('[data-sel]').forEach(b => b.addEventListener('click', () => { S.sel = b.dataset.sel; render(); }));
            if (S.sel === 'own') {
                [['pna', 'tl-pna'], ['oni', 'tl-oni'], ['pdo', 'tl-pdo']].forEach(([k, id]) => root.querySelector('#' + id).addEventListener('input', e => { S.own[k] = +e.target.value; render(); root.querySelector('#' + id).focus(); }));
                root.querySelectorAll('[data-mjo]').forEach(b => b.addEventListener('click', () => { S.own.mjo = b.dataset.mjo === 'null' ? null : +b.dataset.mjo; render(); const nb = root.querySelector('[data-mjo][aria-checked="true"]'); if (nb) nb.focus(); }));
                const rs = root.querySelector('#tl-reset');
                if (rs) rs.addEventListener('click', () => { S.sel = 'w1'; S.own = { pna: +(wins[0].pna || 0).toFixed(1), oni, pdo, mjo: null, spread: 0 }; render(); });
            }
        }
        render();
    }

    const root = document.querySelector('.tl-mount');
    if (!root) return;
    const get = n => fetch(BASE + 'data/' + n, { cache: 'no-cache' }).then(r => (r.ok ? r.json() : null)).catch(() => null);
    Promise.all([get('tele_joint.json'), get('climate_indices.json'), get('tele_now.json')])
        .then(([j, ci, now]) => { if (!j) throw new Error('no model'); mount(root, j, ci, now); })
        .catch(() => { root.innerHTML = '<p class="ol-fail">The relationship data could not be loaded right now.</p>'; });
}());
