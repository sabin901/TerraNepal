/**
 * TerraNepal / TerraRaksha — bilingual strings (English & Nepali).
 *
 * Usage:
 *   const t = i18n[lang];       // lang is 'en' or 'ne'
 *   element.textContent = t.riverStations;
 *
 * Rules:
 * - Keys are camelCase English identifiers, never translated.
 * - Values must NOT contain HTML; escape at the call site.
 * - Add both languages simultaneously; never leave a key untranslated.
 */
'use strict';

const i18n = {
  en: {
    // Navigation
    navOverview:        'Overview',
    navWeather:         'Weather',
    navRivers:          'Rivers',
    navEvidence:        'Evidence',
    navLab:             'Lab capabilities',
    navDischarge:       'Discharge',
    navHistory:         'History',
    navLimitations:     'Limitations',
    // Status bar
    publishedSnapshot:  'Published research snapshot.',
    snapshotNeedsUpdate:'Snapshot needs an update.',
    someSourcesNeedAttn:'Some source data needs attention.',
    pageRefreshFailed:  'Page refresh failed; showing the last loaded snapshot.',
    builtAt:            'Built',
    npt:                'NPT',
    // Freshness states
    recent:             'recent',
    delayed:            'delayed',
    stale:              'stale',
    unknown:            'unknown',
    futureTimestamp:    'future timestamp',
    // River / station table
    riverStations:      'River stations',
    station:            'Station',
    basin:              'Basin',
    lastObservation:    'Last observation',
    level:              'Level',
    units:              'Units (unconfirmed)',
    noRecentData:       'No recent data',
    unconfirmedUnits:   'Source units — unconfirmed',
    conflicting:        'Conflicting',
    // Weather
    weatherOutlook:     'Weather outlook',
    temperature:        'Temperature',
    precipitation:      'Precipitation',
    windGusts:          'Wind gusts',
    model:              'Model',
    place:              'Place',
    hoursAhead:         'Hours ahead',
    // Cards / stats
    archivedReports:    'Archived incident reports',
    stationsWithRecent: 'River stations with recent data',
    observationAge:     'Observation age ≤2 hours · not a safety assessment',
    // Limitations
    limitationsTitle:   'Limitations',
    researchNote:       'Research beta. No flood probabilities, evacuation advice or disaster warnings are generated.',
    // Map
    mapTitle:           'Station map',
    mapNote:            'Station locations are approximate. Colour indicates data freshness.',
    mapLegendRecent:    'Recent (≤1 h)',
    mapLegendDelayed:   'Delayed (1–6 h)',
    mapLegendStale:     'Stale (>6 h)',
    mapLegendUnknown:   'Unknown',
    // Language toggle
    toggleLang:         'नेपाली',
  },

  ne: {
    // Navigation
    navOverview:        'सारांश',
    navWeather:         'मौसम',
    navRivers:          'नदीहरू',
    navEvidence:        'प्रमाण',
    navLab:             'ल्याब क्षमता',
    navDischarge:       'प्रवाह',
    navHistory:         'इतिहास',
    navLimitations:     'सीमाहरू',
    // Status bar
    publishedSnapshot:  'प्रकाशित अनुसन्धान स्न्यापसट।',
    snapshotNeedsUpdate:'स्न्यापसट अद्यावधिक गर्नुपर्छ।',
    someSourcesNeedAttn:'केही स्रोत डेटा ध्यान दिन आवश्यक छ।',
    pageRefreshFailed:  'पृष्ठ ताजा गर्न असफल; अन्तिम लोड भएको स्न्यापसट देखाउँदैछ।',
    builtAt:            'बनाइएको',
    npt:                'नेपाल समय',
    // Freshness states
    recent:             'ताजा',
    delayed:            'ढिलाइ',
    stale:              'पुरानो',
    unknown:            'अज्ञात',
    futureTimestamp:    'भविष्यको मिति',
    // River / station table
    riverStations:      'नदी स्टेशनहरू',
    station:            'स्टेशन',
    basin:              'नदी उपत्यका',
    lastObservation:    'अन्तिम अवलोकन',
    level:              'सतह',
    units:              'एकाइ (अपुष्टित)',
    noRecentData:       'हालको डेटा छैन',
    unconfirmedUnits:   'स्रोत एकाइ — अपुष्टित',
    conflicting:        'विरोधाभासी',
    // Weather
    weatherOutlook:     'मौसम पूर्वानुमान',
    temperature:        'तापमान',
    precipitation:      'वर्षा',
    windGusts:          'हावाको झोका',
    model:              'मोडेल',
    place:              'स्थान',
    hoursAhead:         'घण्टा अगाडि',
    // Cards / stats
    archivedReports:    'संग्रहित घटना प्रतिवेदन',
    stationsWithRecent: 'हालका डेटासहित नदी स्टेशन',
    observationAge:     'अवलोकन उमेर ≤२ घण्टा · सुरक्षा मूल्याङ्कन होइन',
    // Limitations
    limitationsTitle:   'सीमाहरू',
    researchNote:       'अनुसन्धान बिटा। कुनै बाढी सम्भावना, निकासी सल्लाह वा विपद् चेतावनी उत्पन्न गरिँदैन।',
    // Map
    mapTitle:           'स्टेशन नक्सा',
    mapNote:            'स्टेशन स्थानहरू अनुमानित छन्। रङले डेटा ताजापन देखाउँछ।',
    mapLegendRecent:    'ताजा (≤१ घण्टा)',
    mapLegendDelayed:   'ढिलाइ (१–६ घण्टा)',
    mapLegendStale:     'पुरानो (>६ घण्टा)',
    mapLegendUnknown:   'अज्ञात',
    // Language toggle
    toggleLang:         'English',
  },
};

// Persist user language choice across page loads.
function getLang() {
  return localStorage.getItem('terra_lang') || 'en';
}
function setLang(lang) {
  if (!i18n[lang]) return;
  localStorage.setItem('terra_lang', lang);
}

// Export for use by app.js / logic.js
if (typeof module !== 'undefined') module.exports = { i18n, getLang, setLang };
