import test from 'node:test'
import assert from 'node:assert/strict'
import { ageText, label, localTime } from '../src/c-display.js'

test('unknown or invalid clock never produces a reassuring age',()=>{
  const now=Date.parse('2026-11-10T00:00:10Z')
  assert.equal(ageText(null,'2026-11-10T00:00:00Z',now),'未知')
  assert.equal(ageText(0,'2026-11-10T00:01:00Z',now),'未知')
  assert.equal(ageText(2,'invalid',now),'未知')
  assert.equal(ageText(2,'2026-11-10T00:00:00Z',now),'12.0 秒')
})
test('unrecognized backend reasons remain inspectable',()=>{
  assert.equal(label('NEW_REASON'),'NEW_REASON')
  assert.equal(label('UNKNOWN'),'未知')
  assert.equal(localTime('invalid'),'暂无时间记录')
})
