const assert=require('node:assert/strict');
const {freshness,windowSummary}=require('./static/logic.js');
const at=Date.parse('2026-11-03T18:00:00Z')/1000;
assert.equal(freshness('2026-11-03T17:00:00Z',at).state,'recent');
assert.equal(freshness('2026-11-01T17:00:00Z',at).state,'stale');
assert.equal(freshness(null,at).state,'unknown');
assert.equal(freshness('2026-11-03T19:00:00Z',at).state,'future time');
const s={fetched_at:'2026-11-03T18:00:00Z',normalized:{points:Array.from({length:96},(_,i)=>({epoch:at+(i+1)*3600,precipitation:0,wind_gusts_10m:3}))}};
assert.equal(windowSummary(s,24,at).total,0); // Real zero remains zero.
assert.equal(windowSummary(s,24,at).valid,24);
assert.equal(windowSummary(s,24,at+7*3600).total,null); // Stale forecast, despite plenty of future points.
assert.equal(windowSummary(s,24,at-1).total,null); // Future retrieval cannot be current.
s.normalized.points[4].precipitation=null;
assert.equal(windowSummary(s,24,at).total,null); // Missing must not become zero.
assert.equal(windowSummary(s,24,at).valid,23);
assert.equal(windowSummary(null,24,at).total,null);
assert.equal(windowSummary({...s,fetched_at:'invalid'},24,at).total,null);
console.log('12 freshness and forecast assertions passed');
