# TerraRaksha release decision — 15 November 2026

## Verdict

Conditional GO for a clearly labelled noncommercial research demonstration and
technical feedback. NO-GO for a validated disaster prediction, operational warning,
complete nationwide sector platform or government-endorsed launch.

Company/product promotional launch is on HOLD until hosted data access is confirmed
appropriate. Open-Meteo's current terms explicitly list commercial products and
promotional activities as commercial use; being free to visitors is insufficient.
No accounts, paid services, outreach, tags or social posts were created.

The TerraRaksha display brand is implemented locally. Existing TerraNepal repository
and Pages URLs are preserved. Name screening is preliminary; company/domain/mark
clearance has not been established. No deployment was performed in this work session.

## Implemented

- Display name and social metadata updated; research/no-warning purpose preserved.
- Added reproducible JSON/Markdown situation briefs to the static build. Evidence
  hash, assessment time, model/source references, stale/missing values, failed
  attempts and river conflicts remain inspectable.
- Twelve sectors remain in scope, each with explicit missing evidence; no fabricated
  impact counts, damages, safe routes or warning status.
- Strict replay rejects evidence later than the assessment cutoff. CLI refuses
  input/output collisions and existing output overwrite. Source hash shape validated.
- Detailed invalid forecast diagnostics preserve negative precipitation as rejection,
  never zero. Updated methods to reflect implemented original-run acquisition,
  evidence retention and evaluator without claiming actual scientific validation.

## Live evidence checked

The existing deployed snapshot was checked around 20:19 UTC on 15 November:
205 river stations (146 recent), 398 rain timestamps (298 recent), 14 retained weather
pairs (10 usable), six discharge study points (zero verified reaches). Historical
incident export remains dated 3 November. These counts describe stored configured
coverage, not all Nepal, and will change over time.

Four ECMWF pairs were stale/failed: Kathmandu, Biratnagar, Birendranagar and Dhangadhi.
Retained initialized responses contained -0.1 mm rainfall for three samples. A live
Kathmandu rolling request reproduced the invalid negative values. Whole-response
rejection retains older valid evidence. Richer diagnostics do not repair coverage.
Selective per-variable quarantine is a separate schema change requiring reasons,
raw provenance, validation, backward compatibility and visible public missingness.

## Verification

72 public Python tests, 115 research Python tests, 15 archive Python tests and
29 JavaScript assertions passed. A static artifact built successfully using a fresh
download of the current deployed snapshot. Independent AI review found chronology,
output collision, hash format and build-time wording issues; they were fixed with
regression coverage. Exported assessment-time precision was also tested by exact
snapshot/brief replay. No human scientific approval is implied. No new interactive
browser test, Docker build or security audit was performed in this session.

## Remaining requirements by release claim

Research sharing:
- Use the dated brief and explicit coverage/limitations; check live freshness again
  immediately before sharing. Publish the reviewed changes only under a permitted
  noncommercial use/access context. Do not imply these local changes are already live.
- Retain source attribution, existing official links and a feedback request.

Company promotion:
- Resolve hosted data commercial-use permission or implement a separately reviewed
  permitted data path; review other source terms. Do not expand BIPAD raw redistribution.
- Complete name/domain checks before treating TerraRaksha as a cleared legal identity.

Scientific disaster intelligence:
- Approve station/grid/reach metadata and units with documented evidence.
- Build catchment precipitation/soil/routing and dated exposure before impact claims.
- Evaluate identical independent held-out cases, ordinary and extreme events, with
  missed events, false alarms, uncertainty and delivered lead time.
- Implement actual sector workflows and verified geography, bilingual comprehension
  and local user evaluation; a sector readiness list is not a completed service.

Operational warning service:
- Accountable human scientific/operational review and official warning lifecycle.
- Delivery/response procedures, recovery drills and dependable monitoring. User chose
  GitHub-only; this remains best-effort research delivery, not time-critical warning.

## LinkedIn draft — not posted

Use only after the appropriate data-access/use and publication conditions above are
resolved; replace the link if the repository is later renamed.

> I am developing TerraRaksha, a Nepal-focused weather and disaster-information
> research platform, built from the TerraNepal project.
>
> The aim is to make environmental evidence easier to inspect: where data came from,
> how old it is, what is missing, and where forecasts disagree. The next step is to
> connect that evidence to useful, locally validated decisions for communities,
> agriculture, infrastructure and public services.
>
> This is a research demonstration. It is not an official warning system, and we
> have not established locally validated disaster-prediction accuracy. Coverage and
> source limitations are shown openly. For official warnings, please use DHM.
>
> I would value technical feedback on the data quality, methods and practical
> workflows—especially what evidence would make this useful to people working in
> Nepal's disaster-risk and weather services.
>
> Project: https://sabin901.github.io/TerraNepal/

Ministry-facing sharing should request specific technical feedback, not endorsement.
If the user tags people, choose directly relevant technical roles and verify their
current profiles. No person or institution has reviewed or endorsed this project.
Avoid broad tagging or claims of partnerships, national accuracy or lives saved.

## Primary references checked

- https://open-meteo.com/en/terms
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://dhm.gov.np/
- https://satark.bipadportal.gov.np/

## Subsequent completion work — 15 November 2026

The user selected **noncommercial research publication now**, with company use to
be prepared separately. This supersedes the publication-choice hold above; it does
not change scientific or operational NO-GO findings or the company-use terms.

Implemented the reviewed partial-variable schema described earlier: finite invalid
rolling values become null with explicit original-value/time/variable receipts.
Raw bytes remain unchanged. Shape, units and nonnumeric/nonfinite failures still
reject the response. Original-run research remains strict. Public validation
reconstructs and re-normalizes receipts, rejecting tampering. Health stays degraded
for quarantined values, even outside the current display horizon.

Fresh isolated collection on this date obtained all14 weather pairs. All14 had
complete next24-hour windows; four ECMWF pairs carried12 invalid rainfall samples
later in their96-hour series. This is improved availability, not improved scientific
accuracy. Kathmandu72-hour rainfall was correctly withheld while temperature/gust
remained visible. All14 rolling raw responses were retained as hashed evidence.

The weather view now includes temperature ranges and explicit quarantine details.
Browser verification confirmed the24-hour/72-hour distinction and original negative
values in the disclosure. Pages deployment now depends on the full research and
archive suites plus the dependency audit, instead of only selected research tests.

Company transition preparation is in COMMERCIAL_DATA_TRANSITION.md. Neither a
source migration nor commercial permission is implied by research publication.

Final local checks for this update:78 public tests,119 research tests,15 archive
tests and36 JavaScript assertions passed. pip-audit reported no known vulnerabilities
in the pinned Python requirements. Publication verification is recorded separately
from local tests; no company or warning-service launch is claimed.
