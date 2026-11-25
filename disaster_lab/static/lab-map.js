/**
 * TerraRaksha Lab — interactive station map (Leaflet wrapper).
 * Lab variant: colours by freshness; adds incident cluster layer.
 * Include AFTER leaflet.js and leaflet.css in the HTML.
 */
'use strict';

const LabMap = (() => {
  const FRESHNESS_COLORS = {
    recent:           '#2d7d58',
    delayed:          '#c17f24',
    stale:            '#b03a2e',
    future_timestamp: '#7f3fbf',
    unknown:          '#7f8c8d',
  };

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

  function circleOpts(station) {
    return {
      radius: 7,
      fillColor: FRESHNESS_COLORS[freshnessState(station.observed_at)] || FRESHNESS_COLORS.unknown,
      color: '#fff', weight: 1.5, opacity: 0.9, fillOpacity: 0.85,
    };
  }

  function popupHtml(s) {
    const esc = v => String(v ?? '—').replace(/[&<>"']/g,
      c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmt = v => (v == null ? '—' : Number(v).toLocaleString('en-US', {maximumFractionDigits: 3}));
    const d = v => v ? new Date(v).toLocaleString('en-GB',
      {timeZone:'Asia/Kathmandu',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : 'Unknown';
    return `<div class="map-popup">
      <strong>${esc(s.station_name || s.name)}</strong>
      <small>${esc(s.basin || '')} basin · ID ${esc(s.id)}</small>
      <dl>
        <dt>Last observation</dt><dd>${d(s.observed_at)} NPT</dd>
        <dt>Freshness</dt><dd>${esc(freshnessState(s.observed_at))}</dd>
        <dt>Level</dt><dd>${fmt(s.level ?? s.water_level_source_units)} <em>unconfirmed units</em></dd>
      </dl>
      <small>No warning threshold. Units and datum unverified.</small>
    </div>`;
  }

  function init(containerId, stations, geojson) {
    const map = L.map(containerId, {
      center: [28.0, 84.0], zoom: 7, minZoom: 6, maxZoom: 14,
      maxBounds: [[24, 76], [33, 92]],
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }).addTo(map);

    if (geojson) {
      try {
        L.geoJSON(geojson, {
          style: { color: '#6a9b6a', weight: 1, fillColor: '#d8ead6', fillOpacity: 0.2 },
        }).addTo(map);
      } catch (_) {}
    }

    const markers = new Map();
    for (const s of (stations || [])) {
      if (!isFinite(s.latitude) || !isFinite(s.longitude)) continue;
      const m = L.circleMarker([s.latitude, s.longitude], circleOpts(s))
        .bindPopup(popupHtml(s), { maxWidth: 280 }).addTo(map);
      markers.set(s.id, { marker: m, station: s });
    }

    const legend = L.control({ position: 'bottomright' });
    legend.onAdd = () => {
      const div = L.DomUtil.create('div', 'terra-map-legend');
      div.innerHTML = '<b>Freshness</b>' +
        [['recent','#2d7d58','Recent (≤1 h)'],
         ['delayed','#c17f24','Delayed (1–6 h)'],
         ['stale','#b03a2e','Stale (>6 h)'],
         ['unknown','#7f8c8d','Unknown']]
        .map(([,c,l]) => `<div><i style="background:${c}"></i>${l}</div>`).join('') +
        '<small>Unconfirmed units. No warning.</small>';
      return div;
    };
    legend.addTo(map);

    map.fitBounds([[26.3, 79.8], [30.5, 88.2]]);
    return { map, markers };
  }

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
