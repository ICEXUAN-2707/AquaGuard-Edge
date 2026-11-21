import test from 'node:test'
import assert from 'node:assert/strict'
import {connectionStatus} from '../src/c-connection.js'
const good=()=>Object.fromEntries(['live','assessment','sync','events'].map(key=>[key,{value:{}}]))
test('credentials alone never imply service availability',()=>{
  assert.equal(connectionStatus(false,good()).kind,'idle')
  assert.equal(connectionStatus(true,{}).kind,'checking')
})
test('successful queries do not assert sensor or cloud success',()=>{
  const state=connectionStatus(true,good())
  assert.equal(state.kind,'available');assert.match(state.detail,/分别以页面数据为准/)
})
test('partial errors remain visible independently of successful live query',()=>{
  const data=good();data.sync={error:'查询失败'}
  assert.equal(connectionStatus(true,data).kind,'partial')
})
test('all failed queries remain unavailable after credentials were entered',()=>{
  const data=Object.fromEntries(['live','assessment','sync','events'].map(key=>[key,{error:'凭据无效'}]))
  assert.equal(connectionStatus(true,data).kind,'unavailable')
})
test('incomplete query set does not imply a full response',()=>{
  assert.equal(connectionStatus(true,{live:{value:{}}}).kind,'checking')
})
