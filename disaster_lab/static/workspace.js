'use strict';
const $=s=>document.querySelector(s);let token=null,result=null;
async function request(path,body){const response=await fetch(path,{headers:{...(body?{'Content-Type':'application/json','X-Lab-Token':token}:{})},method:body?'POST':'GET',...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw Error(data.error||'Request failed');return data;}
async function file(id){const f=$(id).files[0];if(!f)throw Error('Select the required JSON file.');if(f.size>15000)throw Error('This private web form accepts files below 15 KB. Use the local CLI for larger supported datasets.');return JSON.parse(await f.text());}
async function run(operation){$('#error').hidden=true;$('#status').textContent='Checking evidence…';try{if(!token)throw Error('Workspace session is not ready. Reload or sign in.');result=await operation();$('#result').textContent=JSON.stringify(result,null,2);renderSummary(result);$('#download').disabled=false;$('#status').textContent='Result ready. Review evidence scope and limitations before using it.';}catch(e){$('#error').textContent=e.message;$('#error').hidden=false;$('#status').textContent='Request not completed. Existing records are retained.';}}
$('#assessed-at').value=new Date().toISOString();
$('#case-read').onsubmit=e=>{e.preventDefault();run(()=>request('/api/cases?'+new URLSearchParams({id:$('#case-id').value,...($('#cutoff').value?{cutoff:$('#cutoff').value}:{})})));};
$('#list').onclick=()=>run(()=>request('/api/cases'));
$('#integrity').onclick=()=>run(()=>request('/api/case-integrity'));
const inspectBtn=$('#inspect-stations');if(inspectBtn)inspectBtn.onclick=()=>run(()=>request('/api/station-registry'));
$('#case-write').onsubmit=e=>{e.preventDefault();run(async()=>{if(!$('#case-id').value.trim())throw Error('Enter a case identifier first.');return request('/api/'+$('#entry-kind').value,{case_id:$('#case-id').value,document:await file('#case-document')});});};
$('#exposure').onsubmit=e=>{e.preventDefault();run(async()=>{const payload={hazards:await file('#hazards'),assets:await file('#assets'),at:$('#assessed-at').value,...($('#valid-at').value?{valid_at:$('#valid-at').value}:{})};if(JSON.stringify(payload).length>15500)throw Error('Combined exposure request exceeds 15.5 KB web form limit. Use the local CLI for larger datasets.');return request('/api/exposure',payload);});};
$('#download').onclick=()=>{if(!result)return;const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='terraraksha-research-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
request('/api/session').then(s=>{token=s.token;$('#status').textContent='Private workspace connected. No records are sent to external services.';}).catch(e=>{$('#error').textContent=e.message;$('#error').hidden=false;$('#status').textContent='Sign in to use this workspace.';});

function renderSummary(value){
 const target=$('#result-summary');target.replaceChildren();
 const text=(tag,content,parent=target)=>{const el=document.createElement(tag);el.textContent=content;parent.append(el);return el;};
 if(Array.isArray(value)){
  text('p',value.length+' recorded cases. Select a case to inspect its evidence and history.');
  for(const row of value){const card=text('article','');text('h3',row.title,card);text('p',row.hazard+' · '+row.revision_count+' revisions · '+row.action_count+' actions · '+row.outcome_count+' outcomes',card);const button=text('button','Open case',card);button.onclick=()=>{$('#case-id').value=row.case_id;run(()=>request('/api/cases?'+new URLSearchParams({id:row.case_id})));};}
 }else if(value.latest_revision){
  const d=value.latest_revision.payload;text('h3',d.title);text('p',d.geography.label+' · '+d.geography.review.status);text('p',d.valid_from+' to '+d.valid_to);text('p',d.evidence.length+' source references. '+value.events.length+' recorded revisions/actions/outcomes. Inspect full evidence JSON for model-specific values and review status.');
 }else if(Array.isArray(value.assets)){
  text('p',value.coverage);const table=text('table','');const header=text('tr','',table);for(const label of ['Asset','Sector','Assessment','Matching footprints'])text('th',label,header);
  for(const asset of value.assets){const row=text('tr','',table);for(const label of [asset.asset_id,asset.sector,asset.status.replaceAll('_',' '),String(asset.matches.length)])text('td',label,row);}
  text('p','No damage or safety conclusion is established.');
 }else if(value.candidates||value.schema_version){
  text('p',(value.candidates?value.candidates.length:0)+' candidate station mappings.');
  if(value.note)text('p',value.note);
  if(Array.isArray(value.candidates)&&value.candidates.length){
   const table=text('table','');const header=text('tr','',table);for(const label of ['Station ID','Place','Distance (km)','Status'])text('th',label,header);
   for(const c of value.candidates){const row=text('tr','',table);for(const val of [c.station_id,c.place_name,c.distance_km,c.verified?'Verified':'Pending'])text('td',String(val),row);}
  }
 }else if(value.hash_chains){text('p',value.cases+' cases; '+value.events+' records; hash chains '+value.hash_chains+'.');text('p',value.note);}
 else{text('p','Record saved. Inspect the full evidence JSON for its revision hash.');}
}
