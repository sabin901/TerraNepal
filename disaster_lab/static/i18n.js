/**
 * TerraNepal / TerraRaksha — bilingual strings (English & Nepali).
 * Lab (private workspace) variant — same keys as public_site/static/i18n.js.
 */
'use strict';

const i18n = {
  en: {
    navOperations:      'Service health',
    navForecast:        'Forecast studio',
    navQuality:         'Evidence health',
    navOverview:        'Overview',
    navIncidents:       'Incident explorer',
    navRivers:          'River & replay lab',
    navSources:         'Sources & messages',
    navActions:         'Action notebook',
    navMap:             'Station map',
    recent:             'recent',
    delayed:            'delayed',
    stale:              'stale',
    unknown:            'unknown',
    station:            'Station',
    basin:              'Basin',
    lastObservation:    'Last observation',
    level:              'Level',
    units:              'Units (unconfirmed)',
    researchNote:       'Research beta. No flood warnings generated.',
    mapTitle:           'Station map',
    mapLegendRecent:    'Recent (≤1 h)',
    mapLegendDelayed:   'Delayed (1–6 h)',
    mapLegendStale:     'Stale (>6 h)',
    mapLegendUnknown:   'Unknown',
    toggleLang:         'नेपाली',
  },
  ne: {
    navOperations:      'सेवा स्वास्थ्य',
    navForecast:        'पूर्वानुमान स्टुडियो',
    navQuality:         'प्रमाण स्वास्थ्य',
    navOverview:        'सारांश',
    navIncidents:       'घटना अन्वेषक',
    navRivers:          'नदी र रिप्ले ल्याब',
    navSources:         'स्रोत र सन्देश',
    navActions:         'कार्य नोटबुक',
    navMap:             'स्टेशन नक्सा',
    recent:             'ताजा',
    delayed:            'ढिलाइ',
    stale:              'पुरानो',
    unknown:            'अज्ञात',
    station:            'स्टेशन',
    basin:              'नदी उपत्यका',
    lastObservation:    'अन्तिम अवलोकन',
    level:              'सतह',
    units:              'एकाइ (अपुष्टित)',
    researchNote:       'अनुसन्धान बिटा। कुनै बाढी चेतावनी उत्पन्न गरिँदैन।',
    mapTitle:           'स्टेशन नक्सा',
    mapLegendRecent:    'ताजा (≤१ घण्टा)',
    mapLegendDelayed:   'ढिलाइ (१–६ घण्टा)',
    mapLegendStale:     'पुरानो (>६ घण्टा)',
    mapLegendUnknown:   'अज्ञात',
    toggleLang:         'English',
  },
};

function getLang() { return localStorage.getItem('terra_lang') || 'en'; }
function setLang(lang) { if (i18n[lang]) localStorage.setItem('terra_lang', lang); }
