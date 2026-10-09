// Live conditions map: one box per forecast area, small dots for its stations.
// Hover shows the area name; click opens a popup with a mini table of every
// station (high to low), a 72-hour checklist, and any data-quality cautions.
// Data: assets/data/live_conditions.json, written every 2 hours by
// scripts/collect_live_conditions.py. Missing values render as an en dash.

(function () {
    'use strict';

    const DASH = '–';
    const STALE_DATA_HOURS = 6;

    const mapEl = document.getElementById('conditions-map');
    if (!mapEl) return;
    const statusEl = document.getElementById('conditions-status');
    const allEl = document.getElementById('conditions-all');
    const dataUrl = mapEl.dataset.src;
    const basinsUrl = mapEl.dataset.basins;
    const zonesUrl = mapEl.dataset.zones;
    const base = mapEl.dataset.base || '';

    function setStatus(text, isWarning) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.classList.toggle('cmap-status--warn', !!isWarning);
    }

    if (typeof L === 'undefined') {
        setStatus('The map could not load. The full station list is on the live conditions page.', true);
        return;
    }

    // ---- formatting -------------------------------------------------------

    const esc = s => String(s).replace(/[&<>"']/g, c => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

    const num = (v, digits, unit) =>
        (v === null || v === undefined) ? DASH : `${Number(v).toFixed(digits)}${unit}`;

    const pacific = new Intl.DateTimeFormat('en-US', {
        timeZone: 'America/Los_Angeles',
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short',
    });

    // ---- popup / card body ------------------------------------------------

    function stationRow(s) {
        const flagged = !s.trust.ok;
        const wind = (s.wind_mph === null || s.wind_mph === undefined) ? DASH
            : `${Math.round(s.wind_mph)} mph` + ((s.gust_mph === null || s.gust_mph === undefined)
                ? '' : ` <small>g${Math.round(s.gust_mph)}</small>`);
        const obs = s.obs_time ? `Last report ${pacific.format(new Date(s.obs_time))}` : 'No recent report';
        return `<tr class="${flagged ? 'cmap-row--flag' : ''}">
            <th scope="row" title="${esc(obs)}">${esc(s.label)}${flagged ? ' <span class="cmap-warn" aria-label="questionable data">&#9888;</span>' : ''}
                <small>${esc(s.network)}</small></th>
            <td>${s.elev_ft === null ? DASH : s.elev_ft.toLocaleString() + "'"}</td>
            <td>${num(s.temp_f, 0, '°F')}</td>
            <td>${wind}</td>
            <td>${num(s.snow_depth_in, 1, ' in')}</td>
            <td>${num(s.swe_in, 1, ' in')}</td>
            <td>${num(s.precip_24h_in, 2, ' in')}</td>
        </tr>`;
    }

    // "Blewett Pass" -> "Blewett Pass Area" (names already ending in Area/Region are left alone).
    const areaLabel = name => /\b(area|region)$/i.test(name) ? name : `${name} Area`;

    // Which station the stat tiles show: the area's designated primary station if it
    // has any readings (even if flagged, with the warning shown), otherwise the first
    // station that does. Pills above the tiles switch to any other nearby station.
    const hasReadings = s => [s.temp_f, s.wind_mph, s.snow_depth_in, s.swe_in, s.precip_24h_in]
        .some(v => v !== null && v !== undefined);
    function defaultStation(area) {
        return area.stations.find(s => s.primary && hasReadings(s)) || area.stations.find(hasReadings) || null;
    }

    const areaById = new Map();

    function tile(label, value, opts) {
        const o = opts || {};
        return `<div class="cmap-tile${o.cls ? ' ' + o.cls : ''}"${o.title ? ` title="${esc(o.title)}"` : ''}><span>${label}</span><strong>${value}</strong></div>`;
    }

    function headlineHtml(area, h) {
        const pills = area.stations.length > 1
            ? `<div class="cmap-picks" role="group" aria-label="Choose a station">${area.stations.map((s, i) =>
                `<button type="button" class="cmap-pick" data-area="${esc(area.id)}" data-i="${i}" aria-pressed="${s === h}">${esc(s.label)}${s.elev_ft ? ` <small>${s.elev_ft.toLocaleString()}'</small>` : ''}${s.trust.ok ? '' : ' <span class="cmap-warn">&#9888;</span>'}</button>`).join('')}</div>` : '';
        if (!h) return `${pills}<p class="cmap-from">No station in this area has reported recently.</p>`;
        const wind = (h.wind_mph === null || h.wind_mph === undefined) ? DASH : `${Math.round(h.wind_mph)} mph`;
        const obs = h.obs_time ? `last report ${pacific.format(new Date(h.obs_time))}` : 'no recent report';
        // Dew point with relative humidity in parentheses. Air within 3 F of its dew point (or at 95% RH or more)
        // is near saturation, a rough cue for fog or low cloud, so the tile is tinted.
        const hasDew = h.dewpoint_f !== null && h.dewpoint_f !== undefined, hasRh = h.rh !== null && h.rh !== undefined;
        const dewText = hasDew || hasRh ? `${hasDew ? num(h.dewpoint_f, 0, '°F') : DASH} (${hasRh ? num(h.rh, 0, '%') : DASH})` : DASH;
        const humid = (hasDew && h.temp_f !== null && h.temp_f !== undefined && h.temp_f - h.dewpoint_f <= 3) || (hasRh && h.rh >= 95);
        return `${pills}
            <div class="cmap-tiles${h.trust.ok ? '' : ' cmap-tiles--flag'}">${tile('Temp', num(h.temp_f, 0, '°F'))}${tile('Dew pt (RH)', dewText, humid ? { cls: 'cmap-tile--humid', title: 'Near saturation: the temperature is within 3°F of the dew point, or RH is 95% or more. Fog or low cloud is possible.' } : {})}${tile('Wind', wind)}
                ${tile('Snow depth', num(h.snow_depth_in, 0, ' in'))}${tile('SWE', num(h.swe_in, 1, ' in'))}
                ${tile('Precip 24h', num(h.precip_24h_in, 2, ' in'))}</div>
            <p class="cmap-from">${esc(h.label)}${h.elev_ft ? ` &middot; ${h.elev_ft.toLocaleString()}'` : ''} &middot; ${esc(h.network)} &middot; ${esc(obs)}</p>
            ${h.trust.ok ? '' : `<p class="cmap-from cmap-warn">&#9888; ${h.trust.reasons.map(esc).join('; ')}</p>`}`;
    }

    function areaBody(area, headingTag) {
        areaById.set(area.id, area);
        const flagged = area.stations.filter(s => !s.trust.ok);
        const cautions = flagged.map(s =>
            `<li><strong>${esc(s.label)}</strong>: ${s.trust.reasons.map(esc).join('; ')}</li>`).join('');
        // Only what is happening is highlighted; the rest stays quiet. Details live in the tooltip.
        const checks = area.checklist.map(c => {
            const mark = c.status === 'yes' ? '&#10003; ' : c.status === 'no' ? '&times; ' : DASH + ' ';
            return `<li class="cmap-chip cmap-chip--${c.status}" title="${esc(c.detail || 'Not enough data')}">${mark}${esc(c.label)}</li>`;
        }).join('');
        const link = area.page
            ? `<a class="cmap-more" href="${esc(base + area.page)}">Forecast tools for the ${esc(areaLabel(area.name))} &rarr;</a>` : '';
        const cams = (area.webcams || []).length
            ? `<div class="cmap-cams">${area.webcams.map(c =>
                `<button type="button" class="cmap-cam" data-type="${esc(c.type)}" data-id="${esc(c.id)}" data-label="${esc(c.label)}">&#128247; ${esc(c.label)}</button>`).join('')}</div>` : '';

        return `<${headingTag} class="cmap-title">${esc(areaLabel(area.name))}</${headingTag}>
            ${area.note ? `<p class="cmap-note">${esc(area.note)}</p>` : ''}
            <div class="cmap-headline">${headlineHtml(area, defaultStation(area))}</div>
            <ul class="cmap-chips">${checks}</ul>
            ${cams}
            <details class="cmap-stations">
                <summary>Nearby stations (${area.stations.length})${flagged.length ? ' <span class="cmap-warn">&#9888;</span>' : ''}</summary>
                <div class="cmap-scroll"><table class="cmap-table">
                    <thead><tr><th scope="col">Station</th><th scope="col">Elev</th><th scope="col">Temp</th>
                        <th scope="col">Wind</th><th scope="col">Depth</th><th scope="col">SWE</th>
                        <th scope="col">Precip 24h</th></tr></thead>
                    <tbody>${area.stations.map(stationRow).join('')}</tbody>
                </table></div>
                ${cautions ? `<ul class="cmap-cautions">${cautions}</ul>` : ''}
            </details>
            ${link}`;
    }

    // Station pills: swap the tiles to the chosen station.
    document.addEventListener('click', e => {
        const pick = e.target.closest && e.target.closest('.cmap-pick');
        if (!pick) return;
        const area = areaById.get(pick.dataset.area);
        const box = pick.closest('.cmap-headline');
        if (!area || !box) return;
        box.innerHTML = headlineHtml(area, area.stations[Number(pick.dataset.i)]);
        if (openPopupRef && openPopupRef._updateLayout) { openPopupRef._updateLayout(); openPopupRef._updatePosition(); }
    });

    // ---- map --------------------------------------------------------------

    // Popup content for one or several areas sharing a watershed. With more than
    // one, each area gets a tab so every region in the basin stays reachable.
    const zoneNote = zone => zone ? `<p class="cmap-zone-note">Shaded: the <strong>${esc(zone)}</strong> NWAC forecast zone, shown only to group nearby stations. <strong>This is not an NWAC forecast.</strong> For avalanche forecasts go to <a href="https://nwac.us" target="_blank" rel="noopener noreferrer">nwac.us</a>.</p>` : '';
    function popupContent(areas, zone) {
        if (areas.length === 1) return `<div class="cmap-popup-body">${areaBody(areas[0], 'div')}${zoneNote(zone)}</div>`;
        const tabs = areas.map((a, i) =>
            `<button type="button" class="cmap-tab" role="tab" aria-selected="${i === 0}" data-tab="${i}">${esc(areaLabel(a.name))}</button>`).join('');
        const panels = areas.map((a, i) =>
            `<div class="cmap-panel" role="tabpanel" data-panel="${i}"${i ? ' hidden' : ''}>${areaBody(a, 'div')}</div>`).join('');
        return `<div class="cmap-popup-body"><div class="cmap-tabs" role="tablist">${tabs}</div>${panels}${zoneNote(zone)}</div>`;
    }

    // Delegated so it works however Leaflet builds the popup DOM.
    let openPopupRef = null;
    document.addEventListener('click', e => {
        const tab = e.target.closest && e.target.closest('.cmap-tab');
        if (!tab) return;
        const body = tab.closest('.cmap-popup-body');
        body.querySelectorAll('.cmap-tab').forEach(t => t.setAttribute('aria-selected', String(t === tab)));
        body.querySelectorAll('.cmap-panel').forEach(p => { p.hidden = p.dataset.panel !== tab.dataset.tab; });
        // popup.update() would re-render the stored HTML and undo the switch, so only
        // re-measure (Leaflet 1.9 internals; the version is pinned in the include).
        if (openPopupRef && openPopupRef._updateLayout) { openPopupRef._updateLayout(); openPopupRef._updatePosition(); }
    });

    // ---- webcam viewer ----------------------------------------------------

    // One modal shared by every webcam button (map popups and the all-areas cards).
    // YouTube streams use a plain iframe. Windy's timelapse player is an anchor plus
    // a script that upgrades anchors when it loads, so the script is re-added per open.
    let camModal;
    function openCam(type, id, label) {
        if (!camModal) {
            camModal = document.createElement('div');
            camModal.className = 'cmap-modal';
            camModal.hidden = true;
            camModal.innerHTML = '<div class="cmap-modal-box" role="dialog" aria-modal="true" aria-label="Webcam">' +
                '<button type="button" class="cmap-modal-close" aria-label="Close">&times;</button>' +
                '<div class="cmap-modal-title"></div><div class="cmap-modal-body"></div></div>';
            document.body.appendChild(camModal);
            const close = () => { camModal.hidden = true; camModal.querySelector('.cmap-modal-body').innerHTML = ''; };
            camModal.addEventListener('click', e => { if (e.target === camModal) close(); });
            camModal.querySelector('.cmap-modal-close').addEventListener('click', close);
            document.addEventListener('keydown', e => { if (e.key === 'Escape' && !camModal.hidden) close(); });
        }
        const body = camModal.querySelector('.cmap-modal-body');
        camModal.querySelector('.cmap-modal-title').textContent = label;
        if (type === 'youtube') {
            body.innerHTML = `<div class="cmap-video"><iframe src="https://www.youtube.com/embed/${encodeURIComponent(id)}?autoplay=1&mute=1"
                title="${esc(label)}" allow="autoplay; encrypted-media; picture-in-picture" allowfullscreen></iframe></div>`;
        } else {
            body.innerHTML = `<a name="windy-webcam-timelapse-player" data-id="${esc(id)}" data-play="day" data-loop="0" data-auto-play="0"
                data-force-full-screen-on-overlay-play="0" data-interactive="1" href="https://windy.com/webcams/${esc(id)}"
                target="_blank" rel="noopener">${esc(label)}</a>`;
            const s = document.createElement('script');
            s.async = true;
            s.src = 'https://webcams.windy.com/webcams/public/embed/v2/script/player.js?' + Date.now();
            body.appendChild(s);
        }
        camModal.hidden = false;
    }
    document.addEventListener('click', e => {
        const b = e.target.closest && e.target.closest('.cmap-cam');
        if (b) openCam(b.dataset.type, b.dataset.id, b.dataset.label);
    });

    // point-in-polygon (ray casting) for one ring, and for a GeoJSON Polygon/MultiPolygon
    function inRing(x, y, ring) {
        let c = false;
        for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
            const [xi, yi] = ring[i], [xj, yj] = ring[j];
            if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c;
        }
        return c;
    }
    function inGeom(lon, lat, g) {
        const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
        return polys.some(p => inRing(lon, lat, p[0]) && !p.slice(1).some(h => inRing(lon, lat, h)));
    }

    function build(data, basins, zones) {
        const map = L.map(mapEl, {
            scrollWheelZoom: false,
            dragging: true,   // one finger moves the map on phones too; the map is capped in height so there is page above and below it to scroll with
            maxZoom: 12,
        }).setView([47.4, -121.6], 7); // Leaflet needs a view before vector layers are added; refit below
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri',
            maxZoom: 12,
        }).addTo(map);

        const popupWidth = Math.min(400, window.innerWidth - 60);
        // Group areas by the shaded region they belong to: an NWAC forecast zone (the zone that holds most of the
        // area's stations) when the zone outlines are available, otherwise the USGS watershed the area lists.
        const regions = zones || basins;
        const keyOf = zones ? f => f.properties.zone : f => f.properties.huc8;
        const nameOf = zones ? f => f.properties.zone : f => f.properties.name;
        const areasByKey = new Map();
        const zoneOfArea = new Map();
        if (zones) {
            const near = (lon, lat) => {           // fall back to the nearest zone vertex for a point outside every outline
                let best = null, bd = Infinity;
                zones.features.forEach(f => { const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
                    polys.forEach(p => p[0].forEach(([x, y]) => { const d = (x - lon) ** 2 + (y - lat) ** 2; if (d < bd) { bd = d; best = f; } })); });
                return best;
            };
            data.areas.forEach(a => {
                const votes = new Map();
                a.stations.forEach(s => { const f = zones.features.find(z => inGeom(s.lon, s.lat, z.geometry)) || near(s.lon, s.lat);
                    if (f) votes.set(f.properties.zone, (votes.get(f.properties.zone) || 0) + 1); });
                const top = [...votes.entries()].sort((x, y) => y[1] - x[1])[0];
                if (top) { zoneOfArea.set(a, top[0]); if (!areasByKey.has(top[0])) areasByKey.set(top[0], []); areasByKey.get(top[0]).push(a); }
            });
        } else {
            data.areas.forEach(a => {
                (a.basins || [a.basin]).forEach(code => {
                    if (!areasByKey.has(code)) areasByKey.set(code, []);
                    areasByKey.get(code).push(a);
                });
            });
        }

        const openAt = (latlng, areas, preferred, zone) => {
            const ordered = preferred ? [preferred, ...areas.filter(a => a !== preferred)] : areas;
            // Cap the popup at about half the map so there is always map left to drag or tap to close;
            // anything taller scrolls inside the popup.
            const popup = L.popup({
                maxWidth: popupWidth, minWidth: Math.min(300, popupWidth), className: 'cmap-popup', autoPanPadding: [12, 12],
                maxHeight: Math.max(180, Math.round(map.getSize().y * 0.5)),
            }).setLatLng(latlng).setContent(popupContent(ordered, zone));
            openPopupRef = popup;
            popup.openOn(map);
        };

        const base = { color: '#1e3c72', weight: 1.5, fillColor: '#2a5298', fillOpacity: 0.15 };
        const layer = L.geoJSON(regions, {
            filter: f => areasByKey.has(keyOf(f)),
            style: () => base,
            onEachFeature: (f, lyr) => {
                const areas = areasByKey.get(keyOf(f)), zone = zones ? keyOf(f) : null;
                lyr.bindTooltip(zones ? `${esc(nameOf(f))} NWAC forecast zone (boundary only, not a forecast)` : nameOf(f), { sticky: true, direction: 'top', className: 'cmap-basin-tip' });
                lyr.on('mouseover', () => { lyr.setStyle({ weight: 3, fillOpacity: 0.35 }); });
                lyr.on('mouseout', () => lyr.setStyle(base));
                lyr.on('click', e => { openAt(e.latlng, areas, null, zone); });
            },
        }).addTo(map);
        const zoneNoteEl = document.getElementById('cmap-zone-note');
        if (zoneNoteEl) zoneNoteEl.hidden = !zones;

        // Station dots go on top of the basins; clicking one opens its own area first.
        data.areas.forEach(area => area.stations.forEach(s => {
            // SNOTEL stations are circles, NWAC stations are diamonds; grey means questionable or no recent data
            const shape = s.network === 'NWAC' ? 'diamond' : 'circle';
            const dot = L.marker([s.lat, s.lon], {
                icon: L.divIcon({
                    className: 'cmap-pin',
                    html: `<span class="cmap-pin-${shape}${s.trust.ok ? '' : ' cmap-pin--flag'}"></span>`,
                    iconSize: [18, 18], iconAnchor: [9, 9],
                }),
                bubblingMouseEvents: false, keyboard: false,
            }).addTo(map);
            dot.bindTooltip(`${esc(s.label)}${s.elev_ft ? ` (${s.elev_ft.toLocaleString()}')` : ''}`, { direction: 'top', offset: [0, -8] });
            dot.on('click', () => { const z = zoneOfArea.get(area); openAt(L.latLng(s.lat, s.lon), zones ? areasByKey.get(z) : areasByKey.get(area.basin), area, zones ? z : null); });
        }));

        map.fitBounds(layer.getBounds(), { padding: [12, 12] });
    }

    function renderAll(data) {
        if (!allEl) return;
        allEl.innerHTML = data.areas.map(area =>
            `<article class="cmap-card">${areaBody(area, 'h3')}</article>`).join('');
    }

    const getJson = url => fetch(url, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });

    // NWAC zone outlines are preferred; the watershed outlines are the fallback if that file is not there
    Promise.all([getJson(dataUrl), getJson(basinsUrl), zonesUrl ? getJson(zonesUrl).catch(() => null) : null])
        .then(([data, basins, zones]) => {
            const generated = new Date(data.generated_utc);
            const ageH = (Date.now() - generated.getTime()) / 3.6e6;
            setStatus(
                `Conditions as of ${pacific.format(generated)}. Updates about every 2 hours. ` +
                'NWAC stations via Synoptic, SNOTEL via NRCS. An en dash means that station does not report the value.' +
                (ageH > STALE_DATA_HOURS ? ' This data is more than 6 hours old, so it may be out of date.' : ''),
                ageH > STALE_DATA_HOURS);
            build(data, basins, zones);
            renderAll(data);
        })
        .catch(err => {
            console.error('Live conditions map failed:', err && err.stack ? err.stack : err);
            setStatus('Live conditions are temporarily unavailable. Please try again shortly.', true);
        });
}());
