PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, homepage TEXT NOT NULL,
 access_status TEXT NOT NULL, rights_notes TEXT NOT NULL, limitations TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
 mode TEXT NOT NULL, status TEXT NOT NULL, error TEXT
);
CREATE TABLE IF NOT EXISTS fetches (
 id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id), source TEXT NOT NULL,
 url TEXT NOT NULL, fetched_at TEXT NOT NULL, http_status INTEGER,
 sha256 TEXT, raw_path TEXT, byte_count INTEGER, headers TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS record_versions (
 id INTEGER PRIMARY KEY, collection TEXT NOT NULL, native_id TEXT NOT NULL,
 sha256 TEXT NOT NULL, payload TEXT NOT NULL CHECK(json_valid(payload)),
 first_fetch_id INTEGER NOT NULL REFERENCES fetches(id), first_seen_at TEXT NOT NULL,
 UNIQUE(collection,native_id,sha256)
);
CREATE TABLE IF NOT EXISTS records (
 collection TEXT NOT NULL, native_id TEXT NOT NULL,
 version_id INTEGER NOT NULL REFERENCES record_versions(id),
 first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
 latest_fetch_id INTEGER NOT NULL REFERENCES fetches(id),
 PRIMARY KEY(collection,native_id)
);
CREATE TABLE IF NOT EXISTS changes (
 id INTEGER PRIMARY KEY, collection TEXT NOT NULL, native_id TEXT NOT NULL,
 previous_version_id INTEGER REFERENCES record_versions(id),
 version_id INTEGER NOT NULL REFERENCES record_versions(id),
 observed_at TEXT NOT NULL, fetch_id INTEGER NOT NULL REFERENCES fetches(id)
);
CREATE INDEX IF NOT EXISTS change_time ON changes(observed_at);
CREATE INDEX IF NOT EXISTS change_record ON changes(collection,native_id,id);
CREATE TABLE IF NOT EXISTS collection_runs (
 id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 collection TEXT NOT NULL, query_start TEXT, query_end TEXT,
 pages INTEGER NOT NULL DEFAULT 0, rows_seen INTEGER NOT NULL DEFAULT 0,
 new_records INTEGER NOT NULL DEFAULT 0, revised_records INTEGER NOT NULL DEFAULT 0,
 status TEXT NOT NULL, note TEXT, started_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS issues (
 id INTEGER PRIMARY KEY, run_id TEXT REFERENCES runs(id), collection TEXT,
 severity TEXT NOT NULL, code TEXT NOT NULL, detail TEXT NOT NULL, observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS research_references (
 id TEXT PRIMARY KEY, title TEXT, publisher TEXT, publication_date TEXT, url TEXT,
 prior_access_notes TEXT, evidence_status TEXT NOT NULL DEFAULT 'prior_research_not_revalidated'
);
CREATE TABLE IF NOT EXISTS response_actions (
 id TEXT PRIMARY KEY, event_collection TEXT, event_native_id TEXT,
 place_code TEXT, action_type TEXT NOT NULL, responsible_organization TEXT,
 requested_at TEXT, started_at TEXT, completed_at TEXT, outcome_metric TEXT,
 outcome_value REAL, outcome_unit TEXT, evidence_url TEXT,
 verification_status TEXT NOT NULL CHECK(verification_status IN ('unverified','provider_reported','independently_checked')),
 notes TEXT
);
CREATE TABLE IF NOT EXISTS event_links (
 left_collection TEXT NOT NULL, left_id TEXT NOT NULL,
 right_collection TEXT NOT NULL, right_id TEXT NOT NULL,
 relation TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'candidate', evidence TEXT,
 PRIMARY KEY(left_collection,left_id,right_collection,right_id)
);
CREATE VIEW IF NOT EXISTS current_payloads AS
 SELECT r.*,v.payload,v.sha256 FROM records r JOIN record_versions v ON v.id=r.version_id;
CREATE VIEW IF NOT EXISTS incident_current AS
 SELECT r.native_id AS incident_id,
 json_extract(r.payload,'$.title') AS title,
 json_extract(r.payload,'$.incidentOn') AS occurred_at,
 substr(json_extract(r.payload,'$.incidentOn'),1,10) AS local_event_date,
 json_extract(r.payload,'$.reportedOn') AS reported_at,
 json_extract(r.payload,'$.modifiedOn') AS source_modified_at,
 json_extract(r.payload,'$.hazard') AS hazard_id,
 json_extract(h.payload,'$.title') AS hazard,
 json_extract(h.payload,'$.type') AS source_hazard_type,
 json_extract(r.payload,'$.point.coordinates[0]') AS longitude,
 json_extract(r.payload,'$.point.coordinates[1]') AS latitude,
 json_extract(r.payload,'$.wards') AS ward_ids,
 json_array_length(json_extract(r.payload,'$.wards')) AS ward_count,
 json_extract(r.payload,'$.verified') AS source_verified,
 json_extract(r.payload,'$.approved') AS source_approved,
 json_extract(r.payload,'$.event') AS source_event_group,
 json_extract(r.payload,'$.dataSource') AS originating_source,
 json_extract(r.payload,'$.loss.peopleDeathCount') AS reported_deaths,
 json_extract(r.payload,'$.loss.peopleMissingCount') AS reported_missing,
 json_extract(r.payload,'$.loss.peopleInjuredCount') AS reported_injured,
 json_extract(r.payload,'$.loss.peopleAffectedCount') AS reported_people_affected,
 json_extract(r.payload,'$.loss.familyAffectedCount') AS reported_families_affected,
 json_extract(r.payload,'$.loss.infrastructureDestroyedHouseCount') AS reported_houses_destroyed,
 json_extract(r.payload,'$.loss.estimatedLoss') AS estimated_loss_source_units,
 r.first_seen_at,r.last_seen_at,r.version_id,r.latest_fetch_id
 FROM current_payloads r LEFT JOIN current_payloads h
 ON h.collection='bipad:hazard' AND h.native_id=CAST(json_extract(r.payload,'$.hazard') AS TEXT)
 WHERE r.collection='bipad:incident';
CREATE VIEW IF NOT EXISTS natural_incidents AS
 SELECT * FROM incident_current WHERE source_hazard_type='natural';
DROP VIEW IF EXISTS incident_places;
CREATE VIEW incident_places AS
 SELECT r.native_id AS incident_id,CAST(j.value AS TEXT) AS ward_id,
 json_extract(wv.payload,'$.title') AS ward_number,
 json_extract(mv.payload,'$.title') AS municipality,
 json_extract(dv.payload,'$.title') AS district,
 json_extract(pv.payload,'$.title') AS province
 FROM records r JOIN record_versions rv ON rv.id=r.version_id,
 json_each(json_extract(rv.payload,'$.wards')) j
 LEFT JOIN records w ON w.collection='bipad:ward' AND w.native_id=CAST(j.value AS TEXT)
 LEFT JOIN record_versions wv ON wv.id=w.version_id
 LEFT JOIN records m ON m.collection='bipad:municipality' AND m.native_id=CAST(json_extract(wv.payload,'$.municipality') AS TEXT)
 LEFT JOIN record_versions mv ON mv.id=m.version_id
 LEFT JOIN records d ON d.collection='bipad:district' AND d.native_id=CAST(json_extract(mv.payload,'$.district') AS TEXT)
 LEFT JOIN record_versions dv ON dv.id=d.version_id
 LEFT JOIN records p ON p.collection='bipad:province' AND p.native_id=CAST(json_extract(dv.payload,'$.province') AS TEXT)
 LEFT JOIN record_versions pv ON pv.id=p.version_id
 WHERE r.collection='bipad:incident';
CREATE VIEW IF NOT EXISTS river_observations AS
 SELECT native_id AS observation_id,json_extract(payload,'$.station') AS station_id,
 json_extract(payload,'$.title') AS station_name,json_extract(payload,'$.basin') AS basin,
 json_extract(payload,'$.waterLevelOn') AS observed_at,
 json_extract(payload,'$.waterLevel') AS water_level_source_units,
 json_extract(payload,'$.warningLevel') AS warning_level_source_units,
 json_extract(payload,'$.dangerLevel') AS danger_level_source_units,
 json_extract(payload,'$.status') AS source_status,
 json_extract(payload,'$.point.coordinates[0]') AS longitude,
 json_extract(payload,'$.point.coordinates[1]') AS latitude,
 'unconfirmed_source_native_units' AS unit_status,
 version_id,latest_fetch_id,first_seen_at,last_seen_at
 FROM current_payloads WHERE collection='bipad:river';
CREATE VIEW IF NOT EXISTS rain_observations AS
 SELECT r.native_id AS observation_id,json_extract(r.payload,'$.station') AS station_id,
 json_extract(r.payload,'$.title') AS station_name,json_extract(r.payload,'$.basin') AS basin,
 json_extract(r.payload,'$.measuredOn') AS observed_at,
 json_extract(a.value,'$.interval') AS source_interval,
 json_extract(a.value,'$.value') AS rainfall_source_units,
 json_extract(a.value,'$.status.warning') AS source_warning,
 json_extract(a.value,'$.status.danger') AS source_danger,
 'unconfirmed_source_native_units_and_accumulation' AS unit_status,
 r.version_id,r.latest_fetch_id,r.first_seen_at,r.last_seen_at
 FROM current_payloads r, json_each(json_extract(r.payload,'$.averages')) a
 WHERE r.collection='bipad:rain';
CREATE VIEW IF NOT EXISTS earthquake_current AS
 SELECT native_id AS earthquake_id,json_extract(payload,'$.properties.title') AS title,
 json_extract(payload,'$.properties.time') AS occurred_epoch_ms,
 strftime('%Y-%m-%dT%H:%M:%fZ',json_extract(payload,'$.properties.time')/1000.0,'unixepoch') AS occurred_at,
 json_extract(payload,'$.properties.updated') AS source_updated_epoch_ms,
 json_extract(payload,'$.properties.mag') AS magnitude,
 json_extract(payload,'$.properties.magType') AS magnitude_type,
 json_extract(payload,'$.geometry.coordinates[0]') AS longitude,
 json_extract(payload,'$.geometry.coordinates[1]') AS latitude,
 json_extract(payload,'$.geometry.coordinates[2]') AS depth_km,
 json_extract(payload,'$.properties.status') AS source_review_status,
 'regional_bounding_box_includes_neighboring_countries' AS geography_scope,
 version_id,latest_fetch_id,first_seen_at,last_seen_at
 FROM current_payloads WHERE collection='usgs:earthquake';
CREATE VIEW IF NOT EXISTS alert_current AS
 SELECT native_id AS alert_id,
 json_extract(payload,'$.title') AS title,
 json_extract(payload,'$.titleNe') AS title_ne,
 json_extract(payload,'$.description') AS description,
 json_extract(payload,'$.source') AS issuer,
 json_extract(payload,'$.referenceType') AS reference_type,
 json_extract(payload,'$.hazard') AS hazard_id,
 json_extract(payload,'$.startedOn') AS starts_at,
 json_extract(payload,'$.expireOn') AS expires_at,
 json_extract(payload,'$.createdOn') AS created_at,
 json_extract(payload,'$.verified') AS source_verified,
 json_extract(payload,'$.public') AS source_public,
 json_extract(payload,'$.point.coordinates[0]') AS longitude,
 json_extract(payload,'$.point.coordinates[1]') AS latitude,
 version_id,latest_fetch_id,first_seen_at,last_seen_at
 FROM current_payloads WHERE collection='bipad:alert';
