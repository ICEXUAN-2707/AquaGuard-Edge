"""Injected-clock adapter. Outputs returned to caller, never accumulated internally."""
from datetime import timedelta
from copy import deepcopy
from alignment import align
from edge.contracts.models import validate_raw_observation


class Stream:
    def __init__(self, device_id, first_end, *, step=5, capacity=1000, max_boots=32, max_windows=100, **config):
        if first_end.tzinfo is None or step <= 0 or capacity <= 0 or max_boots <= 0 or not isinstance(max_windows, int) or max_windows <= 0:
            raise ValueError('invalid stream configuration')
        # Validate algorithm configuration even before the first observation.
        align([], [], **config)
        self.device_id, self.next_end = device_id, first_end
        self.step, self.capacity, self.max_boots = step, capacity, max_boots
        self.max_windows = max_windows
        self.config = deepcopy(config)
        self.rows, self.retired = [], set()
        self.boot = None
        self.now = None
        self.last_published_end = None
        self.width = config.get('width',30)
        self.lateness = config.get('lateness',2)
        ttls = config.get('ttl_by_source') or {}
        self.retention = max([config.get('ttl',10), *ttls.values()])

    def advance(self, now, inclusive=True):
        if now.tzinfo is None or (self.now is not None and now < self.now):
            raise ValueError('clock must be aware and monotonic')
        result=[]
        while (self.next_end + timedelta(seconds=self.lateness) <= now if inclusive else self.next_end + timedelta(seconds=self.lateness) < now):
            if len(result) >= self.max_windows:
                break
            packet=align(self.rows,[self.next_end],**self.config)
            window=packet['windows'][0]
            if not self.rows:
                window['device_id']=self.device_id
                window['window_id']=window['window_id'].replace('demo:',self.device_id+':',1)
            result.append(packet)
            self.last_published_end = self.next_end
            self.next_end += timedelta(seconds=self.step)
            cutoff=self.next_end-timedelta(seconds=self.width+self.retention)
            self.rows=[r for r in self.rows if (validate_raw_observation(r).event_time or validate_raw_observation(r).received_at) >= cutoff]
        self.now=now
        return result

    def push(self, row):
        # Commit only after all validation, catch-up and capacity checks succeed.
        staged = deepcopy(self)
        result = staged._push(row)
        self.__dict__.update(staged.__dict__)
        return result

    def _push(self, row):
        r=validate_raw_observation(row)
        if r.event_time is not None and r.event_time > r.received_at:
            raise ValueError('future event cannot change stream state')
        if r.device_id != self.device_id:
            raise ValueError('wrong device')
        if self.now is not None and r.received_at < self.now:
            raise ValueError('arrival clock moved backwards')
        if r.boot_id in self.retired:
            raise ValueError('retired boot message rejected')
        if self.boot is not None and r.boot_id != self.boot and len(self.retired) >= self.max_boots:
            raise OverflowError('boot history full; restart experiment explicitly')
        # Preflight identity/capacity before changing clock or boot state.
        same_boot = self.boot in (None,r.boot_id)
        prospective = self.rows + [row] if same_boot else [row]
        align(prospective, [], **self.config)
        result=self.advance(r.received_at,inclusive=False)
        if self.next_end + timedelta(seconds=self.lateness) < r.received_at:
            raise OverflowError('catch-up required: advance clock in bounded batches before retry')
        if self.boot is not None and r.boot_id != self.boot and (r.quality != "valid" or r.time_basis == "RECEIVED_FALLBACK"):
            raise ValueError('new boot requires valid event-time evidence')
        if same_boot and row not in self.rows and len(self.rows) >= self.capacity:
            raise OverflowError('observation buffer full; input not accepted')
        if self.last_published_end is not None and (r.event_time or r.received_at) <= self.last_published_end:
            result.append(dict(windows=[], audit=[dict(code="ARRIVED_AFTER_PUBLICATION", observation_id=r.observation_id, last_published_end=self.last_published_end.isoformat())], config=deepcopy(self.config)))
        if self.boot is not None and r.boot_id != self.boot:
            self.retired.add(self.boot)
            self.rows=[]  # Conservative epoch reset, no pre-reboot state carried forward.
            result.append(dict(windows=[], audit=[dict(code="BOOT_RESET", old_boot=self.boot, new_boot=r.boot_id)], config=deepcopy(self.config)))
        self.boot=r.boot_id
        if row not in self.rows:
            self.rows.append(deepcopy(row))
        # Caller advances explicitly after all arrivals sharing this timestamp.
        return result
