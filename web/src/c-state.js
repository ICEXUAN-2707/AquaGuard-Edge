// Keep an uncertain ACK request stable even if polling observes a newer version.
export class AckIntent {
  constructor() { this.reset() }
  reset() { this.eventId=null; this.body=null }
  prepare(event, makeId=()=>crypto.randomUUID()) {
    if(this.eventId===event.event_id && this.body) return this.body
    if(event.lifecycle!=='OPEN' || event.ack_status==='ACKNOWLEDGED' || !Number.isInteger(event.version) || event.version<1) throw new Error('事件当前不可确认')
    this.eventId=event.event_id
    this.body=Object.freeze({schema_version:'1.1',expected_version:event.version,idempotency_key:makeId(),ack_type:'ACKNOWLEDGE'})
    return this.body
  }
}

// A response is current only while no newer request/context has invalidated it.
export class ResponseOrder {
  constructor() { this.version=0 }
  next() { return ++this.version }
  current(version) { return version===this.version }
}
