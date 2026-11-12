import test from 'node:test'
import assert from 'node:assert/strict'
import { AckIntent, ResponseOrder, CloseIntent } from '../src/c-state.js'

const event={event_id:'event-a',version:1,lifecycle:'OPEN',ack_status:'UNACKNOWLEDGED'}
test('uncertain response retry preserves original key and version after polling',()=>{
  const intent=new AckIntent()
  const original=intent.prepare(event,()=> 'operation-1')
  const retried=intent.prepare({...event,version:3,ack_status:'ACKNOWLEDGED'},()=>{throw new Error('must not generate new key')})
  assert.strictEqual(retried,original)
  assert.equal(retried.expected_version,1)
  intent.reset() // After explicit conflict, the user reviews the fresh event.
  assert.equal(intent.prepare({...event,version:3},()=> 'operation-2').expected_version,3)
})
test('switching events never reuses a previous event operation',()=>{
  const intent=new AckIntent()
  intent.prepare(event,()=> 'a')
  assert.equal(intent.prepare({...event,event_id:'event-b'},()=> 'b').idempotency_key,'b')
  intent.reset()
  assert.throws(()=>intent.prepare({...event,lifecycle:'CLOSED'}))
})
test('slow experiment response loses to new request or changed context',async()=>{
  const order=new ResponseOrder()
  const old=order.next()
  const current=order.next()
  assert.equal(order.current(old),false)
  assert.equal(order.current(current),true)
  order.next() // device/token/trial change invalidates the in-flight request.
  assert.equal(order.current(current),false)
})

test('close requires recovery and preserves uncertain original intent',()=>{
  const intent=new CloseIntent()
  assert.throws(()=>intent.prepare({...event,physical_status:'ACTIVE',ack_status:'ACKNOWLEDGED'}))
  const ready={...event,physical_status:'CLEARED',ack_status:'ACKNOWLEDGED'}
  const first=intent.prepare(ready,()=> 'close-1')
  assert.strictEqual(intent.prepare({...ready,version:3,lifecycle:'CLOSED'},()=> 'wrong'),first)
  intent.reset()
  assert.equal(intent.prepare({...ready,version:3},()=> 'close-2').expected_version,3)
})
