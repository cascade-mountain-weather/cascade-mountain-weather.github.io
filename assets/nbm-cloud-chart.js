// NBM cloud-cover chart for one site, as an SVG string. Shared by the precipitation tools page (assets/model-tools-areas.js,
// where it is shown as an image) and the area pages (assets/area-page.js).
//   CMWCloud.chartSvg(nbmData, 'Stevens Pass')   nbmData is assets/data/nbm_plumes.json; returns null without cloud data
(function () {
    'use strict';
    const PAC_H = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', hourCycle: 'h23' });
    const PAC_D = new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', weekday: 'short', month: 'numeric', day: 'numeric' });

    function chartSvg(nbmData, siteName) {
        const site = nbmData && nbmData.sites && nbmData.sites[siteName];
        if (!site || !site.cloud_pct || !nbmData.cloud_time_utc) return null;
        const ts = nbmData.cloud_time_utc.map(t => Date.parse(t)), v = site.cloud_pct;
        const W_ = 820, H_ = 316, pad = { l: 52, r: 16, t: 48, b: 74 };
        const t0 = ts[0], t1 = ts[ts.length - 1];
        const X = t => pad.l + (t - t0) / (t1 - t0) * (W_ - pad.l - pad.r);
        const Y = p => pad.t + (100 - p) / 100 * (H_ - pad.t - pad.b);
        const out = [`<rect width="${W_}" height="${H_}" fill="#fff"/>`,
            `<text x="${pad.l}" y="18" font-size="14" font-weight="700" fill="#1e3c72">NBM cloud cover</text>`,
            `<text x="${pad.l}" y="34" font-size="11" fill="#64748b">Percent of sky covered, every 3 hours. Under 25% is mostly sunny; over 75% is mostly cloudy.</text>`];
        out.push(`<rect x="${pad.l}" y="${Y(100)}" width="${W_ - pad.l - pad.r}" height="${Y(75) - Y(100)}" fill="#e2e8f0" opacity="0.5"/>`);
        out.push(`<rect x="${pad.l}" y="${Y(25)}" width="${W_ - pad.l - pad.r}" height="${Y(0) - Y(25)}" fill="#fef3c7" opacity="0.6"/>`);
        for (const g of [0, 25, 50, 75, 100]) out.push(`<line x1="${pad.l}" x2="${W_ - pad.r}" y1="${Y(g)}" y2="${Y(g)}" stroke="#e2e8f0"/><text x="${pad.l - 6}" y="${Y(g) + 4}" text-anchor="end" font-size="11" fill="#64748b">${g}</text>`);
        // a tick and a Pacific clock label every 3 hours; midnights are dashed and carry the day name below
        const clock = h => (h === 0 ? '12a' : h < 12 ? h + 'a' : h === 12 ? '12p' : (h - 12) + 'p');
        for (let t = Math.ceil(t0 / 3600e3) * 3600e3; t <= t1; t += 3600e3) {
            const hr = +PAC_H.format(t);
            if (hr % 3 !== 0) continue;
            const mid = hr === 0;
            out.push(`<line x1="${X(t)}" x2="${X(t)}" y1="${pad.t}" y2="${H_ - pad.b}" stroke="${mid ? '#94a3b8' : '#e2e8f0'}"${mid ? ' stroke-dasharray="3 3"' : ''}/>`);
            if (X(t) < pad.l - 1 || X(t) > W_ - pad.r + 1) continue;
            out.push(`<text x="${X(t)}" y="${H_ - pad.b + 14}" text-anchor="middle" font-size="9.5" fill="${mid ? '#334155' : '#64748b'}">${clock(hr)}</text>`);
            if (mid && X(t) < W_ - pad.r - 50) out.push(`<text x="${X(t) + 4}" y="${H_ - pad.b + 30}" font-size="11" font-weight="700" fill="#334155">${PAC_D.format(t + 6 * 3600e3).replace(',', '')}</text>`);
        }
        out.push(`<text x="${pad.l}" y="${H_ - pad.b + 50}" font-size="10.5" fill="#64748b">Hour labels are Pacific time, every 3 hours (a = am, p = pm). Dashed lines mark midnight; the day name is the Pacific day that follows.</text>`);
        const pts = ts.map((t, i) => v[i] == null ? null : [X(t), Y(v[i])]);
        // draw in runs so a missing value breaks the line
        let seg = [];
        const flush = () => { if (seg.length > 1) out.push(`<polyline points="${seg.map(p => p.join(',')).join(' ')}" fill="none" stroke="#1e3c72" stroke-width="2.4"/>`); seg = []; };
        pts.forEach(p => { if (p) seg.push(p); else flush(); });
        flush();
        pts.forEach(p => { if (p) out.push(`<circle cx="${p[0]}" cy="${p[1]}" r="2.2" fill="#1e3c72"/>`); });
        out.push(`<text x="14" y="${(pad.t + H_ - pad.b) / 2}" transform="rotate(-90 14 ${(pad.t + H_ - pad.b) / 2})" text-anchor="middle" font-size="12" fill="#334155">cloud cover (%)</text>`);
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W_}" height="${H_}" viewBox="0 0 ${W_} ${H_}" font-family="-apple-system, Segoe UI, Roboto, Arial, sans-serif">${out.join('')}</svg>`;
        return svg;
    }

    window.CMWCloud = { chartSvg: chartSvg };
}());
