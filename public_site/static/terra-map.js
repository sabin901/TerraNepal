/**
 * TerraNepal interactive station map — Leaflet.js wrapper.
 *
 * Bundled locally to comply with the strict `default-src 'self'` CSP.
 * Include this file AFTER leaflet.js and leaflet.css in your HTML.
 *
 * Usage (public site):
 *   const map = TerraMap.init('map-container', snapshot.rivers);
 *   TerraMap.update(map, snapshot.rivers);
 *
 * Features:
 *  - Choropleth freshness colouring (recent/delayed/stale/unknown)
 *  - Nepal province polygon overlay from /nepal.geojson
 *  - Popup with station name, basin, last observation, level
 *  - Legend and attribution
 *  - Works without geojson (gracefully degrades)
 */
'use strict';

const TerraMap = (() => {
  const FRESHNESS_COLORS = {
    recent:           '#2d7d58',
    delayed:          '#c17f24',
    stale:            '#b03a2e',
    future_timestamp: '#7f3fbf',
    unknown:          '#7f8c8d',
  };
  const LEGEND_LABELS = {
    recent:   'Recent (≤1 h)',
    delayed:  'Delayed (1–6 h)',
    stale:    'Stale (>6 h)',
    unknown:  'Unknown',
  };

  /**
   * Compute freshness state from an ISO timestamp.
   * Mirrors the Python data.freshness() logic exactly.
   */
  function freshnessState(observedAt) {
    if (!observedAt) return 'unknown';
    const t = new Date(observedAt).getTime() / 1000;
    if (!isFinite(t)) return 'unknown';
    const age = (Date.now() / 1000 - t) / 60;
    if (age < -5) return 'future_timestamp';
    if (age <= 60) return 'recent';
    if (age <= 360) return 'delayed';
    return 'stale';
  }

  function markerColor(station) {
    return FRESHNESS_COLORS[freshnessState(station.observed_at)] || FRESHNESS_COLORS.unknown;
  }

  function circleOpts(station) {
    return {
      radius: 7,
      fillColor: markerColor(station),
      color: '#fff',
      weight: 1.5,
      opacity: 0.9,
      fillOpacity: 0.85,
    };
  }

  function popupHtml(s, t) {
    const esc = v => String(v ?? '—').replace(/[&<>"']/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmt = v => (v == null ? '—' : Number(v).toLocaleString('en-US', {maximumFractionDigits: 3}));
    const d = v => v ? new Date(v).toLocaleString('en-GB',
      {timeZone:'Asia/Kathmandu',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : 'Unknown';
    const state = freshnessState(s.observed_at);
    return `<div class="map-popup">
      <strong>${esc(s.name)}</strong>
      <small>${esc(s.basin || '')} basin</small>
      <dl>
        <dt>Last observation</dt><dd>${d(s.observed_at)} NPT</dd>
        <dt>Freshness</dt><dd>${esc(state)}</dd>
        <dt>Level</dt><dd>${fmt(s.level)} <em>source units — unconfirmed</em></dd>
      </dl>
      <small>Units and vertical datum not independently verified. No warning threshold.</small>
    </div>`;
  }

  /**
   * Initialise a Leaflet map in the given container element ID.
   * @param {string} containerId - DOM element id
   * @param {Array} stations     - river station objects from snapshot
   * @param {object|null} geojson - Nepal province GeoJSON (or null)
   * @returns {object} - { map, markers, geojsonLayer, legend }
   */
  function init(containerId, stations, geojson) {
    // Nepal bounds
    const bounds = [[26.3, 79.8], [30.5, 88.2]];
    const map = L.map(containerId, {
      center: [28.0, 84.0],
      zoom: 7,
      minZoom: 6,
      maxZoom: 14,
      maxBounds: [[24, 76], [33, 92]],
      zoomControl: true,
      attributionControl: true,
    });

    // Tile layer — OpenStreetMap (open license, no API key)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    // Province boundaries
    let geojsonLayer = null;
    if (geojson) {
      try {
        geojsonLayer = L.geoJSON(geojson, {
          style: {
            color: '#6a9b6a',
            weight: 1.2,
            fillColor: '#d8ead6',
            fillOpacity: 0.25,
          },
        }).addTo(map);
      } catch (_) { /* graceful degradation */ }
    }

    // Station markers
    const markers = new Map();
    for (const s of (stations || [])) {
      if (!isFinite(s.latitude) || !isFinite(s.longitude)) continue;
      const m = L.circleMarker([s.latitude, s.longitude], circleOpts(s))
        .bindPopup(popupHtml(s), { maxWidth: 280 })
        .addTo(map);
      markers.set(s.id, { marker: m, station: s });
    }

    map.fitBounds(bounds);

    // Legend
    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'terra-map-legend');
      div.innerHTML = '<b>Data freshness</b>' +
        Object.entries(LEGEND_LABELS).map(([state, label]) =>
          `<div><i style="background:${FRESHNESS_COLORS[state]}"></i>${label}</div>`
        ).join('') +
        '<small>Units unconfirmed. No warning threshold.</small>';
      return div;
    };
    legend.addTo(map);

    return { map, markers, geojsonLayer, legend };
  }

  /**
   * Update marker colours after a snapshot refresh.
   */
  function update(handle, stations) {
    if (!handle || !handle.markers) return;
    for (const s of (stations || [])) {
      const entry = handle.markers.get(s.id);
      if (!entry) continue;
      entry.station = s;
      entry.marker.setStyle(circleOpts(s));
      entry.marker.setPopupContent(popupHtml(s));
    }
  }

  return { init, update, freshnessState };
})();

if (typeof module !== 'undefined') module.exports = TerraMap;
