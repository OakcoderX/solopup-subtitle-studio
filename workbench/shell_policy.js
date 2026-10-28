/* Pure navigation policy shared by the app shell and regression tests. */
function episodeNumber(title){const m=String(title||'').match(/\bEP\s*0*(\d+)/i);return m?Number(m[1]):null}
function episodeGroups(episodes){
 const groups=new Map();
 for(const e of episodes){const n=episodeNumber(e.title),key=n===null?e.id:'EP'+n;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e)}
 return [...groups.values()].map(versions=>{
  const production=versions.filter(e=>!/烟测|smoke|计时测试|无人干预全集测试/i.test(e.title));
  const pool=production.length?production:versions;
  const ready=pool.filter(e=>e.status==='ready'),options=ready.length?ready:pool;
  const latest=[...options].sort((a,b)=>Number(b.created||0)-Number(a.created||0)||String(b.id).localeCompare(String(a.id)))[0];
  return {latest,history:versions.filter(e=>e!==latest).sort((a,b)=>Number(b.created||0)-Number(a.created||0))};
 }).sort((a,b)=>(episodeNumber(a.latest.title)??Infinity)-(episodeNumber(b.latest.title)??Infinity)||a.latest.title.localeCompare(b.latest.title));
}
if(typeof module!=='undefined')module.exports={episodeNumber,episodeGroups};
