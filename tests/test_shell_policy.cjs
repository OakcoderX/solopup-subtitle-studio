const {test}=require('node:test'),assert=require('node:assert/strict');
const {episodeGroups}=require('../workbench/shell_policy.js');
test('numeric episode order, latest usable draft and failed history retained',()=>{
 const rows=[{id:'old',title:'EP02 old',status:'failed',created:1},{id:'new',title:'EP02 final',status:'ready',created:2},{id:'smoke',title:'EP02 smoke',status:'ready',created:3},{id:'one',title:'EP01',status:'ready',created:1}];
 const groups=episodeGroups(rows);assert.deepEqual(groups.map(g=>g.latest.id),['one','new']);assert.equal(groups[1].history.length,2);assert.equal(rows.length,4);
});
