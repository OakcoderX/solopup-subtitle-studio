const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../workbench/studio.js'),'utf8');
const fn=source.slice(source.indexOf('function collectHumanReview('),source.indexOf('const humanReviewPanel='));
const limits=fs.readFileSync(path.join(__dirname,'../workbench/index.html'),'utf8').match(/function currentLimits[^\n]+/)[0];
const context={};vm.createContext(context);vm.runInContext(limits+'\n'+fn,context);
const state={standard:[{id:'D1',start:10,text:'Hello',checked:true,unresolved:'timing'}],sdh:[{id:'S1',start:5,text:'[wind]',kind:'sound',checked:false}],presentationTasks:[{track:'standard',cue_ids:['D1'],action:'review_vertical_jump'}]};
let tasks=context.collectHumanReview(state,c=>c.unresolved?[c.unresolved]:[]);
assert.equal(tasks.length,2);assert.equal(tasks[0].track,'standard');assert.equal(tasks[0].priority,2);assert.equal(tasks[1].priority,3);assert.equal(tasks[0].index,0);assert.equal(tasks[0].reasons.length,2);assert.equal(state.standard[0].checked,true);
state.sdh[0].checked=true;tasks=context.collectHumanReview(state,c=>c.unresolved?[c.unresolved]:[]);assert.equal(tasks.length,1);assert.equal(tasks[0].id,'D1');
state.standard[0].unresolved='';assert.equal(context.collectHumanReview(state,()=>[]).length,1);
state.presentationTasks=[];assert.equal(context.collectHumanReview(state,()=>[]).length,0);
console.log('Review task regression passed: cross-track routing, chronological order, scoped approval, saved layout retention.');

state.latestReviewFindings=[{id:'D1',reason:'Audible wording uncertain'}];
tasks=context.collectHumanReview(state,()=>[]);assert.equal(tasks.length,1);assert.equal(tasks[0].track,'standard');assert.equal(tasks[0].id,'D1');assert.ok(tasks[0].reasons[0].includes('Audible wording uncertain'));
const sound={id:'S2',kind:'sound',start:1,end:3,text:'[wind]',checked:false,semanticReview:{status:'machine_reviewed',caption:'[wind]',start:1,end:3,audioEvidence:'Wind heard',narrativeValue:'Storm arrives',evidence:['a','b'],uncertain:false}};
const reviewed={standard:[],sdh:[sound]};
assert.equal(context.collectHumanReview(reviewed,()=>[]).length,0);
assert.equal(sound.checked,false);
reviewed.soundEvidenceRecheckTasks=[{id:'S2',proposal:{reason:'Different audible source'}}];
assert.ok(context.collectHumanReview(reviewed,()=>[])[0].reasons[0].includes('Different audible source'));
reviewed.soundEvidenceRecheckTasks=[];sound.end=4;
assert.equal(context.collectHumanReview(reviewed,()=>[]).length,1);

const ranked={frameRate:24,standard:[{id:'wpm',start:0,end:1,text:'One two three.'},{id:'cps',start:3,end:4,text:'A much longer caption than seventeen.'},{id:'words',start:8,end:10,text:'Wrong words.',unresolved:'Targeted audio review remains uncertain: original wording'}],sdh:[]};
const ordered=context.collectHumanReview(ranked,c=>c.unresolved?[c.unresolved]:['reading speed']);
assert.deepEqual(Array.from(ordered,t=>t.id),['words','cps','wpm']);
assert.deepEqual(Array.from(ordered,t=>t.priority),[1,2,4]);
console.log('User priority regression passed: content, technical, other, WPM-only; timing is not treated as a transcription error.');
