/* Shared display rules: no stale or incomplete forecast totals, no safety labels. */
(function(root){
  const finite=v=>typeof v==='number'&&Number.isFinite(v);
  const epoch=v=>typeof v==='string'?Date.parse(v)/1000:NaN;
  function freshness(value,at=Date.now()/1000){
    const t=epoch(value),age=(at-t)/60;
    if(!Number.isFinite(t))return {state:'unknown',age:null};
    return {state:age < -5?'future time':age<=120?'recent':age<=1440?'delayed':'stale',age};
  }
  function windowSummary(source,hours=24,at=Date.now()/1000){
    const start=Math.ceil(at/3600)*3600,end=start+hours*3600;
    const result={state:'unavailable',total:null,gust:null,valid:0,start,end,points:[]};
    if(!source)return result;
    const age=(at-epoch(source.fetched_at))/3600;
    const lookup=new Map(source.normalized.points.map(p=>[p.epoch,p]));
    result.points=Array.from({length:hours},(_,i)=>lookup.get(start+(i+1)*3600)||null);
    result.valid=result.points.filter(p=>p&&finite(p.precipitation)).length;
    result.state=!Number.isFinite(age)?'unknown':age<0?'future retrieval':age>6?'stale':result.valid===hours?'recent':'incomplete';
    if(result.state==='recent')result.total=result.points.reduce((sum,p)=>sum+p.precipitation,0);
    if(age>=0&&age<=6&&result.points.every(p=>p&&finite(p.wind_gusts_10m)))result.gust=Math.max(...result.points.map(p=>p.wind_gusts_10m));
    return result;
  }
  function dischargeState(source,at=Date.now()/1000){
    if(!source)return 'unavailable';
    if(source.normalized?.reach_verified!==true)return 'mapping unverified';
    const age=(at-epoch(source.fetched_at))/3600;
    return !Number.isFinite(age)||age<0||age>24?'stale / unavailable':'experimental model output';
  }
  const exports={finite,epoch,freshness,windowSummary,dischargeState};
  if(typeof module!=='undefined')module.exports=exports;else root.TerraLogic=exports;
})(typeof globalThis!=='undefined'?globalThis:this);
