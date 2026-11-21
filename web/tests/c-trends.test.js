import test from 'node:test'
import assert from 'node:assert/strict'
import {coveragePercent,trendRange,coveragePath} from '../src/c-trends.js'
test('coverage rejects absent, nonfinite and out of range evidence',()=>{
  for(const value of [null,undefined,NaN,Infinity,-.1,1.1,'0.5'])assert.equal(coveragePercent(value),null)
  assert.equal(coveragePercent(0),0);assert.equal(coveragePercent(1),100)
})
test('range uses latest valid snapshot and includes boundaries',()=>{
  const range=trendRange([{time:600000},{time:0},{time:300000},{time:NaN}],5)
  assert.deepEqual(range.rows.map(row=>row.time),[300000,600000]);assert.equal(range.start,300000)
  assert.deepEqual(trendRange([],5),{start:null,end:null,rows:[]})
})
test('missing evidence and collection gaps break the curve',()=>{
  const row=(time,value)=>({time,summary:{flow:{coverage_ratio:value}}})
  const path=coveragePath([row(0,1),row(5000,.5),row(10000,null),row(15000,1),row(40000,1)],'flow',0,60000)
  assert.equal((path.match(/M/g)||[]).length,3);assert.equal((path.match(/L/g)||[]).length,1)
  assert.equal(coveragePath([],'flow',0,0),'')
})
