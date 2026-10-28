/* SoloPup professional subtitle helpers. MIT. Browser-only; no uploads or AI calls. */
(function(root){
 'use strict';
 const base=(typeof module!=='undefined'&&module.exports)?require('./resource-tools.js'):root.SoloPupHelpers;
 function batchReport(text,threshold,minGap){
  threshold=Number(threshold);minGap=Number(minGap);
  if(!Number.isFinite(threshold)||threshold<=0||!Number.isFinite(minGap)||minGap<0)throw new Error('Use a positive CPS threshold and a nonnegative gap threshold. / 阈值应为正数，间隔不能为负数。');
  const cues=base.parseSrt(text);const rows=cues.map((c,i)=>{
   const seconds=(c.end-c.start)/1000,count=Array.from(c.text.replace(/[\r\n]/g,'')).length,cps=count/seconds;
   const gap=i?(c.start-cues[i-1].end)/1000:null;
   return {cue:i+1,startSeconds:c.start/1000,endSeconds:c.end/1000,durationSeconds:seconds,cps,gapBeforeSeconds:gap,aboveChosenCps:cps>threshold,belowChosenGap:gap!==null&&gap<minGap};
  });
  return {cues:rows.length,flagged:rows.filter(x=>x.aboveChosenCps||x.belowChosenGap).length,threshold,minGap,rows};
 }
 function lineReport(text,maxChars,maxLines){
  maxChars=Number(maxChars);maxLines=Number(maxLines);
  if(!Number.isInteger(maxChars)||maxChars<1||!Number.isInteger(maxLines)||maxLines<1)throw new Error('Choose positive integer character and line limits. / 请输入正整数上限。');
  text=String(text).replace(/\r\n?/g,'\n');if(!text.trim())throw new Error('Enter subtitle text. / 请输入字幕。');
  const lines=text.split('\n').map((line,i)=>({line:i+1,characters:Array.from(line).length,overChosenLimit:Array.from(line).length>maxChars,text:line}));
  return {lineCount:lines.length,tooManyLines:lines.length>maxLines,maxChars,maxLines,lines};
 }
 function frameDuration(frames,num,den,otherNum,otherDen){
  frames=Number(frames);num=Number(num);den=Number(den);otherNum=Number(otherNum);otherDen=Number(otherDen);
  if(!Number.isSafeInteger(frames)||frames<0||frames>1000000000)throw new Error('Frame count must be an integer from 0 to 1,000,000,000. / 帧数须为范围内非负整数。');
  for(const x of [num,den,otherNum,otherDen])if(!Number.isInteger(x)||x<1||x>1000000)throw new Error('FPS numerators and denominators must be positive integers up to 1,000,000.');
  const seconds=frames*den/num,comparisonSeconds=frames*otherDen/otherNum;
  return {frames,fpsNumerator:num,fpsDenominator:den,seconds,comparisonSeconds,differenceSeconds:seconds-comparisonSeconds,formula:frames+' × '+den+' / '+num};
 }
 const requirements=['master','roles','timing','source','target','issues'];
 function handoffReport(checked,unresolved){
  unresolved=Number(unresolved);if(!Number.isSafeInteger(unresolved)||unresolved<0)throw new Error('Use a nonnegative integer for unresolved questions. / 待定问题数量须为非负整数。');
  const missing=requirements.filter(key=>checked[key]!==true);return {status:missing.length||unresolved?'REVIEW_DRAFT':'READY_FOR_HUMAN_HANDOFF',missing,unresolved,platformApproval:false,reportedBy:'user checkbox input, not independently verified'};
 }
 const api={batchReport,lineReport,frameDuration,handoffReport};root.SoloPupProHelpers=api;
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 if(typeof document==='undefined')return;
 const el=id=>document.getElementById(id);
 function bind(form,out,fn){if(!el(form))return;el(form).addEventListener('submit',event=>{event.preventDefault();try{el(out).textContent=fn();}catch(e){el(out).textContent=e.message;}});}
 bind('batch-form','batch-result',()=>{const x=batchReport(el('batch-srt').value,el('batch-cps').value,el('batch-gap').value);return 'Cues / 屏数: '+x.cues+'\nFlagged by your thresholds / 按所选阈值提示: '+x.flagged+'\n'+x.rows.map(row=>'#'+row.cue+'  '+row.durationSeconds.toFixed(3)+' s  '+row.cps.toFixed(2)+' CPS  gap / 间隔 '+(row.gapBeforeSeconds===null?'—':row.gapBeforeSeconds.toFixed(3)+' s')+(row.aboveChosenCps?'  CPS ↑':'')+(row.belowChosenGap?'  gap ↓':'')).join('\n')+'\nMechanical hints only; replay the video. / 仅机械线索，请回看原片。';});
 bind('line-form','line-result',()=>{const x=lineReport(el('line-text').value,el('line-limit').value,el('line-count-limit').value);return x.lineCount+' lines / 行\n'+x.lines.map(line=>'#'+line.line+': '+line.characters+' characters / 字符'+(line.overChosenLimit?' — over your limit / 超所选上限':'')).join('\n')+'\n'+(x.tooManyLines?'More lines than your chosen limit. / 行数超过所选上限。':'Within your chosen line count. / 未超所选行数。')+'\nNo automatic reflow or timing change. / 未自动改写或调整时码。';});
 bind('frame-form','frame-result',()=>{const x=frameDuration(el('frame-count').value,el('fps-num').value,el('fps-den').value,el('fps-other-num').value,el('fps-other-den').value);return x.formula+' = '+x.seconds.toFixed(6)+' s\nComparison / 对照: '+x.comparisonSeconds.toFixed(6)+' s\nDifference / 差值: '+x.differenceSeconds.toFixed(6)+' s\nThis compares mathematical durations; it does not inspect or retime a video. / 仅比较数学时长，未检测或变速视频。';});
 bind('handoff-form','handoff-result',()=>{const x=handoffReport(Object.fromEntries(requirements.map(key=>[key,el('handoff-'+key).checked])),el('handoff-unresolved').value);return x.status+'\nMissing checks / 未勾选: '+(x.missing.join(', ')||'none / 无')+'\nUnresolved questions / 待定问题: '+x.unresolved+'\nBased on your self-report. It never establishes platform approval. / 根据人工自报生成，不代表平台批准。';});
})(typeof globalThis!=='undefined'?globalThis:this);
