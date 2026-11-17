"""Windows handle/clock observations and explicitly configured evidence budgets."""
import ctypes
from ctypes import wintypes
import math
import os


def process_resources(process):
    if os.name!='nt':return {'available':False,'reason':'Windows handle metrics unavailable'}
    try:
        class Memory(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD),
                      *[(name,ctypes.c_size_t) for name in ('peak_rss','rss','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile')]]
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(Memory),wintypes.DWORD];psapi.GetProcessMemoryInfo.restype=wintypes.BOOL
        kernel.GetPriorityClass.argtypes=[wintypes.HANDLE];kernel.GetPriorityClass.restype=wintypes.DWORD
        kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)];kernel.GetProcessTimes.restype=wintypes.BOOL
        handle=wintypes.HANDLE(int(process._handle));memory=Memory();memory.cb=ctypes.sizeof(memory)
        created,exited,kernel_time,user_time=(wintypes.FILETIME() for _ in range(4))
        if not psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),memory.cb):raise ctypes.WinError(ctypes.get_last_error())
        priority=kernel.GetPriorityClass(handle)
        if not priority or not kernel.GetProcessTimes(handle,ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel_time),ctypes.byref(user_time)):
            raise ctypes.WinError(ctypes.get_last_error())
        ticks=lambda value:(value.dwHighDateTime<<32)|value.dwLowDateTime
        return dict(available=True,rss_bytes=memory.rss,peak_rss_bytes=memory.peak_rss,priority_class=priority,
                    creation_filetime=ticks(created),cpu_seconds=(ticks(kernel_time)+ticks(user_time))/10000000)
    except (OSError,AttributeError,TypeError,ValueError) as exc:return {'available':False,'reason':type(exc).__name__}


def os_clocks():
    """OS elapsed includes low-power time; unbiased interrupt clock excludes it."""
    if os.name!='nt':return {'available':False,'reason':'Windows OS clock pair unavailable'}
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetTickCount64.restype=ctypes.c_ulonglong
        awake=ctypes.c_ulonglong()
        precise=getattr(kernel,'QueryUnbiasedInterruptTimePrecise',None)
        if precise is not None:
            precise.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)];precise.restype=None;precise(ctypes.byref(awake))
            source='QueryUnbiasedInterruptTimePrecise'
        else:
            query=kernel.QueryUnbiasedInterruptTime;query.argtypes=[ctypes.POINTER(ctypes.c_ulonglong)];query.restype=wintypes.BOOL
            if not query(ctypes.byref(awake)):raise ctypes.WinError(ctypes.get_last_error())
            source='QueryUnbiasedInterruptTime'
        return dict(available=True,elapsed_seconds=kernel.GetTickCount64()/1000,awake_seconds=awake.value/10000000,source=source)
    except (OSError,AttributeError) as exc:return {'available':False,'reason':type(exc).__name__}


THRESHOLDS={'max_sample_gap_seconds','min_coverage_ratio','max_os_excluded_seconds','max_collection_seconds','max_process_rss_bytes'}


def validate_thresholds(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!=THRESHOLDS:raise ValueError('explicit complete observation thresholds required')
    if any(type(item) not in (int,float) or not math.isfinite(item) for item in value.values()):raise ValueError('finite numeric thresholds required')
    if not 0<value['min_coverage_ratio']<=1 or value['max_os_excluded_seconds']<0:raise ValueError('invalid coverage/pause threshold')
    if any(value[key]<=0 for key in ('max_sample_gap_seconds','max_collection_seconds','max_process_rss_bytes')):raise ValueError('positive gap/collection/RSS budget required')
    return dict(value)


def assess(samples,*,duration,interval,thresholds,end_clock,actual_duration=None):
    thresholds=validate_thresholds(thresholds)
    expected=math.ceil(duration/interval)
    offsets=[row['phase_elapsed_seconds'] for row in samples]
    actual_duration=duration if actual_duration is None else actual_duration
    gaps=[offsets[0],max(0,actual_duration-offsets[-1])]+[b-a for a,b in zip(offsets,offsets[1:])] if offsets else [actual_duration]
    clocks=[row.get('os_clock',{}) for row in samples]+[end_clock]
    excluded=None;clock_complete=len(clocks)>=2 and all(row.get('available') is True and row.get('source') and all(type(row.get(key)) in (int,float) and math.isfinite(row[key]) for key in ('elapsed_seconds','awake_seconds')) for row in clocks)
    if clock_complete and len({row['source'] for row in clocks})!=1:clock_complete=False
    if clock_complete:
        elapsed=clocks[-1]['elapsed_seconds']-clocks[0]['elapsed_seconds']
        awake=clocks[-1]['awake_seconds']-clocks[0]['awake_seconds']
        if elapsed<0 or awake<0 or elapsed-awake<-.05:clock_complete=False
        else:excluded=max(0,elapsed-awake)
    processes={};resources_complete=bool(samples)
    for row in samples:
        resources=row.get('resources')
        if not resources:resources_complete=False;continue
        for resource in resources:
            if resource.get('available') is not True:resources_complete=False;continue
            if not resource.get('name') or any(type(resource.get(key)) not in (int,float) or not math.isfinite(resource[key]) or resource[key]<0 for key in ('pid','creation_filetime','rss_bytes','cpu_seconds')):
                resources_complete=False;continue
            key=f"{resource['name']}:{resource['pid']}:{resource['creation_filetime']}"
            previous=processes.get(key,dict(name=resource['name'],pid=resource['pid'],creation_filetime=resource['creation_filetime'],max_rss_bytes=0,max_cpu_seconds=0))
            previous['max_rss_bytes']=max(previous['max_rss_bytes'],resource['rss_bytes'])
            previous['max_cpu_seconds']=max(previous['max_cpu_seconds'],resource['cpu_seconds']);processes[key]=previous
    result=dict(samples=len(samples),expected_samples=expected,planned_duration_seconds=duration,actual_duration_seconds=actual_duration,
                coverage_ratio=min(1,len(samples)/expected),clock_quantization_allowance_seconds=.05,
                max_sample_gap_seconds=max(gaps),os_excluded_seconds=excluded,
                max_collection_seconds=max((row['collection_seconds'] for row in samples),default=None),
                resources_complete=resources_complete,os_clock_complete=clock_complete,processes=list(processes.values()),
                thresholds=thresholds,status='UNCONFIGURED',
                note='OS clock difference is low-power excluded time evidence, not a root-cause verdict. Bounds cover observed direct children only. Not overall acceptance.')
    if thresholds is None:return result
    if not samples or not clock_complete or not resources_complete:result['status']='INCOMPLETE';return result
    checks=dict(coverage=result['coverage_ratio']>=thresholds['min_coverage_ratio'],gap=result['max_sample_gap_seconds']<=thresholds['max_sample_gap_seconds'],
                os_excluded=excluded<=thresholds['max_os_excluded_seconds']+.05,collection=result['max_collection_seconds']<=thresholds['max_collection_seconds'],
                rss=all(row['max_rss_bytes']<=thresholds['max_process_rss_bytes'] for row in processes.values()))
    result.update(checks=checks,status='SATISFIED' if all(checks.values()) else 'VIOLATED')
    return result
