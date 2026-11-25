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
    mapLegendRecent:    'Recent (≤2 h)',
    mapLegendDelayed:   'Delayed (2–24 h)',
    mapLegendStale:     'Stale (>24 h)',
    mapLegendUnknown:   'Unknown',
    // Hero & sections
    heroEyebrow:        'OBSERVE · UNDERSTAND · PREPARE',
    heroTitle1:         'A clearer view of Nepal.',
    heroTitle2:         'With evidence in view.',
    heroDesc:           'Explore river observations, compare weather models, and understand the gaps. Preparedness begins with knowing what the data can tell us.',
    heroCta:            'Explore the weather outlook ↗',
    riversEyebrow:      'RIVER OBSERVATIONS',
    riversTitle:        'Know how recent the evidence is.',
    riversDesc:         'The latest archived reading for each station. Levels remain in unconfirmed source units; danger thresholds and flood probabilities are not inferred.',
    riversUnitWarn:     'Important: Some gauges report elevation-referenced levels (100–1,350+) while others report local stage (0–15). Values are unconfirmed source units — do not compare across stations or use for flood safety decisions.',
    weatherEyebrow:     'WEATHER OUTLOOK',
    weatherTitle:       'Look ahead. Keep uncertainty visible.',
    weatherDesc:        'Numerical weather predictions from ECMWF and NOAA, delivered by Open-Meteo. These are precipitation forecasts, including snow water equivalent, not flood forecasts.',
    evidenceEyebrow:    'SOURCES & COVERAGE',
    evidenceTitle:      'Trust is built from visible evidence.',
    evidenceDesc:       'Inspect collection status, the history of missing observations, and the limits of the analysis.',
    withheld:           'Withheld / unavailable',
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
    mapLegendRecent:    'ताजा (≤२ घण्टा)',
    mapLegendDelayed:   'ढिलाइ (२–२४ घण्टा)',
    mapLegendStale:     'पुरानो (>२४ घण्टा)',
    mapLegendUnknown:   'अज्ञात',
    // Hero & sections
    heroEyebrow:        'अवलोकन · बुझाइ · पूर्वतयारी',
    heroTitle1:         'नेपालको स्पष्ट दृश्य।',
    heroTitle2:         'प्रमाणसहित प्रस्तुत।',
    heroDesc:           'नदी अवलोकन, मौसम पूर्वानुमान मोडेल तुलना, र डेटा कमीहरू हेर्नुहोस्। पूर्वतयारी सही तथ्य बुझेर सुरु हुन्छ।',
    heroCta:            'मौसम पूर्वानुमान हेर्नुहोस् ↗',
    riversEyebrow:      'नदी अवलोकन',
    riversTitle:        'डेटा कति ताजा छ जान्नुहोस्।',
    riversDesc:         'प्रत्येक स्टेशनको पछिल्लो अभिलेख। सतह अपुष्टित स्रोत एकाइमा छ; खतराको तह वा बाढी सम्भावना अनुमान गरिएको छैन।',
    riversUnitWarn:     'महत्त्वपूर्ण: केही मापन केन्द्रले समुद्री सतह (१००–१,३५०+) र केहीले स्थानीय सतह (०–१५) देखाउँछन्। यी अपुष्टित स्रोत एकाइ हुन् — बाढी सुरक्षा निर्णयका लागि प्रयोग नगर्नुहोस्।',
    weatherEyebrow:     'मौसम पूर्वानुमान',
    weatherTitle:       'अगाडि हेर्नुहोस्। अनिश्चितता स्पष्ट राख्नुहोस्।',
    weatherDesc:        'ECMWF र NOAA बाट Open-Meteo मार्फत प्राप्त मौसम पूर्वानुमान। यी वर्षा पूर्वानुमान हुन्, बाढी चेतावनी होइनन्।',
    evidenceEyebrow:    'स्रोत र समेटिएको क्षेत्र',
    evidenceTitle:      'विश्वास स्पष्ट प्रमाणबाट बन्छ।',
    evidenceDesc:       'डेटा संकलन अवस्था, छुटेका अवलोकनको इतिहास, र विश्लेषणका सीमाहरू जाँच गर्नुहोस्।',
    withheld:           'रोकिएको / अनुपलब्ध',
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
