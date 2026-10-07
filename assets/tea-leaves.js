// "Reading the Tea Leaves": predict the Cascades pattern from an outlook of the PNA, ENSO (and PDO) and the MJO.
// Data: assets/data/tele_joint.json (scripts/tele_export_joint.py, the joint regression of 36 SNOTEL stations, Nov-May 1992-2026)
// and assets/data/climate_indices.json for the current ONI and PDO. Mount: <div class="tl-mount"></div>.
// Effect for a tier and measure = sum(b_i * z_i) + (c_phase - sum(f_k * c_k)): the departure from an average day. Its range
// combines the bootstrap ranges of the parts as if independent (approximate). A pattern is named only when its range excludes zero.
(function () {
    'use strict';
    const BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
    const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
    const TIERS = [['all', 'All stations'], ['low', 'Low, under 4,000 ft'], ['mid', 'Mid, 4,000 to 5,000 ft'], ['high', 'High, 5,000 ft and up']];
    const NOTE = { low: 'Mostly near the rain-snow line: snow responds most.', mid: '', high: 'Temperature responds most; snowfall less.', all: '' };

    function latest(series) { for (let i = series.values.length - 1; i >= 0; i--) if (series.values[i] != null) return series.values[i]; return 0; }

    function mount(root, J, CI) {
        const oniNow = CI ? +latest(CI.oni).toFixed(1) : 0, pdoNow = CI ? +latest(CI.pdo).toFixed(1) : 0;
        const S = { pna: 0, oni: oniNow, pdo: pdoNow, mjo: 0 };
        const MJO = [[0, 'Weak or none'], ...[1, 2, 3, 4, 5, 6, 7, 8].map(k => [k, 'Phase ' + k])];
        const f = J.mjo_freq;
        // The fit is a straight line, and only a few winters sit far out on ENSO or the PDO, so an input is held at 1.5 standard deviations.
        const CAP = 1.5;
        const capped = () => ['PNA', 'ONI', 'PDO'].filter(t => Math.abs((S[t.toLowerCase()] - J.stats[t].mean) / J.stats[t].sd) > CAP).map(t => t + ' (treated as ' + (S[t.toLowerCase()] > J.stats[t].mean ? '+' : '−') + (J.stats[t].mean + CAP * J.stats[t].sd * (S[t.toLowerCase()] > J.stats[t].mean ? 1 : -1)).toFixed(1).replace('-', '') + ')');

        // effect and half-width of its uncertainty for one tier and metric
        function effect(tier, metric) {
            const c = J.tiers[tier][metric];
            const z = {}; ['PNA', 'ONI', 'PDO'].forEach(t => { z[t] = Math.max(-CAP, Math.min(CAP, (S[t.toLowerCase()] - J.stats[t].mean) / J.stats[t].sd)); });
            let v = 0, h2 = 0;
            ['PNA', 'ONI', 'PDO'].forEach(t => { v += c[t][0] * z[t]; h2 += Math.pow((c[t][2] - c[t][1]) / 2 * Math.abs(z[t]), 2); });
            let avg = 0;
            for (let k = 1; k <= 8; k++) avg += f[k] * c['MJO' + k][0];
            const cm = S.mjo ? c['MJO' + S.mjo] : [0, 0, 0];
            v += cm[0] - avg;
            h2 += Math.pow((cm[2] - cm[1]) / 2, 2);
            return { v, h: Math.sqrt(h2) };
        }
        const sign = e => (e.v - e.h > 0 ? 1 : e.v + e.h < 0 ? -1 : 0);

        function classify(tier) {
            const T = effect(tier, 'tanom'), W = effect(tier, 'swe'), R = effect(tier, 'rain'), B = effect(tier, 'bigsnow');
            const t = sign(T), s = sign(W), r = sign(R), b = sign(B);
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
            return { label, tone, T, W, R, B };
        }

        const pct = e => `${e.v >= 0 ? '+' : '−'}${Math.abs(Math.round(e.v * 100))}% <small>(±${Math.round(e.h * 100)})</small>`;
        const deg = e => `${e.v >= 0 ? '+' : '−'}${Math.abs(e.v).toFixed(1)} °F <small>(±${e.h.toFixed(1)})</small>`;
        const cls = (e, up) => { const s = sign(e); return s === 0 ? 'tl-n' : (s > 0) === up ? 'tl-g' : 'tl-b'; };
        const pnaWord = v => v <= -1.0 ? 'strong negative' : v <= -0.35 ? 'negative' : v < 0.45 ? 'near neutral' : v < 0.95 ? 'positive' : 'strong positive';
        const ensoWord = v => v >= 1 ? 'El Niño' : v >= 0.5 ? 'weak El Niño' : v <= -1 ? 'La Niña' : v <= -0.5 ? 'weak La Niña' : 'neutral';

        function render() {
            const rows = TIERS.map(([k, label]) => ({ k, label, c: classify(k) }));
            root.innerHTML = `<div class="tl">
                <div class="tl-inputs">
                    <div class="ol-group"><label class="ol-label" for="tl-pna">PNA outlook (5-day mean): <b>${S.pna >= 0 ? '+' : '−'}${Math.abs(S.pna).toFixed(1)}</b> <span class="tl-w">${pnaWord(S.pna)}</span></label><input id="tl-pna" type="range" min="-2.5" max="2.5" step="0.1" value="${S.pna}"></div>
                    <div class="ol-group"><label class="ol-label" for="tl-oni">ENSO, ONI: <b>${S.oni >= 0 ? '+' : '−'}${Math.abs(S.oni).toFixed(1)}</b> <span class="tl-w">${ensoWord(S.oni)}</span></label><input id="tl-oni" type="range" min="-2.5" max="2.5" step="0.1" value="${S.oni}"></div>
                    <div class="ol-group"><label class="ol-label" for="tl-pdo">PDO: <b>${S.pdo >= 0 ? '+' : '−'}${Math.abs(S.pdo).toFixed(1)}</b></label><input id="tl-pdo" type="range" min="-3" max="3" step="0.1" value="${S.pdo}"></div>
                    <div class="ol-group tl-mjo"><span class="ol-label">MJO phase about ${J.lag} days before the period</span>
                        <div class="ol-chips" role="radiogroup" aria-label="MJO phase">${MJO.map(([k, l]) => `<button type="button" class="ol-chip" role="radio" aria-checked="${k === S.mjo}" data-mjo="${k}">${l}</button>`).join('')}</div></div>
                </div>
                <p class="ci-hint">The ONI and PDO start at their latest values (${oniNow >= 0 ? '+' : '−'}${Math.abs(oniNow).toFixed(1)} and ${pdoNow >= 0 ? '+' : '−'}${Math.abs(pdoNow).toFixed(1)}). Set the PNA and MJO from the outlook figures below. An MJO that is weak (inside the center of its diagram) has no effect in this model.</p>
                ${capped().length ? `<p class="ci-note">Beyond the range the 35 winters can speak to: ${capped().join(', ')}. The effect is held at that level, so the result is conservative for a more extreme value.</p>` : ''}
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
            [['pna', 'tl-pna'], ['oni', 'tl-oni'], ['pdo', 'tl-pdo']].forEach(([k, id]) => root.querySelector('#' + id).addEventListener('input', e => { S[k] = +e.target.value; render(); root.querySelector('#' + id).focus(); }));
            root.querySelectorAll('[data-mjo]').forEach(b => b.addEventListener('click', () => { S.mjo = +b.dataset.mjo; render(); const nb = root.querySelector('[data-mjo][aria-checked="true"]'); if (nb) nb.focus(); }));
        }
        render();
    }

    const root = document.querySelector('.tl-mount');
    if (!root) return;
    Promise.all([fetch(BASE + 'data/tele_joint.json').then(r => r.json()), fetch(BASE + 'data/climate_indices.json').then(r => r.json()).catch(() => null)])
        .then(([j, ci]) => mount(root, j, ci))
        .catch(() => { root.innerHTML = '<p class="ol-fail">The relationship data could not be loaded right now.</p>'; });
}());
