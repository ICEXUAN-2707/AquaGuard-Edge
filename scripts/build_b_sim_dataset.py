"""Deterministic operation-labeled simulation data; no training or efficacy claim."""
from __future__ import annotations

import argparse
from datetime import datetime,timedelta,timezone
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
FORMAT='aquaguard-b-sim-dataset-1'
SCENARIOS=('idle','attended','brief_leave','unattended','hidden_present','presence_dropout')
ENDS=(30,35,40)
START=datetime(2026,11,10,tzinfo=timezone.utc)


def packed(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def sha(value):return hashlib.sha256(value).hexdigest()


def json_file(path,value):
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))


def generate_trial(trial_id,scenario,config):
    """Truth is the scripted episode, not any B classifier's output.

    A brief departure is labeled negative by episode annotation even while absent
    at a window end. This uses future script knowledge and is disclosed, not an
    online proof that a person will return. Hidden/persistent pairs are ambiguous.
    """
    cadence=config['cadence_sec'];rows=[]
    for sensor in ('flow','water','presence'):
        for seq,second in enumerate(range(0,41,cadence)):
            if sensor=='flow' and second==0:continue
            if scenario=='presence_dropout' and sensor=='presence' and second>=config['leave_at']:
                continue
            if sensor=='presence':
                if scenario in ('unattended','hidden_present','presence_dropout'):
                    present=second<config['leave_at']
                elif scenario=='brief_leave':
                    present=not config['brief_leave_at']<=second<config['brief_leave_at']+config['brief_duration']
                else:present=True
                value={'present':present,'moving':present,'still':False}
            elif sensor=='water':value={'wet':False}
            else:
                pulses=0 if scenario=='idle' else max(1,round(config['flow_lpm']*cadence))
                # Explicit synthetic K=60 pulses/L model; not hardware calibration.
                value={'pulse_count':pulses,'interval_ms':cadence*1000,
                       'estimated_lpm':pulses/cadence,'calibration_id':'synthetic-k60-not-hardware'}
            event=START+timedelta(seconds=second)
            rows.append({'schema_version':'1.1','observation_id':f'{trial_id}:{sensor}:{seq}',
                         'device_id':trial_id,'sensor_type':sensor,'boot_id':trial_id+':boot0',
                         'seq':seq,'uptime_ms':second*1000,'event_time':event.isoformat(),
                         'received_at':(event+timedelta(seconds=config['receive_delay_sec'])).isoformat(),
                         'time_basis':'DEVICE_SYNCED','value':value,'quality':'valid','source':'simulation'})
    return rows


def build(output,seed=20261110,cohorts=12):
    if type(seed) is not int or not 0<=seed<2**32 or type(cohorts) is not int or cohorts<6:
        raise ValueError('seed must be uint32 and cohorts must be at least six')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(ROOT))
    from edge.contracts.models import validate_raw_observation
    group_ids=[f'cohort-{number:03d}' for number in range(cohorts)]
    shuffled=list(group_ids);random.Random(seed).shuffle(shuffled)
    train=cohorts//2;validation=cohorts//4
    split_groups={'train':shuffled[:train],'validation':shuffled[train:train+validation],
                  'test':shuffled[train+validation:]}
    split_for={group:name for name,groups in split_groups.items() for group in groups}
    trials=[];observations=[];labels=[]
    for group in group_ids:
        group_seed=int(sha(packed([FORMAT,seed,group]))[:16],16)
        rng=random.Random(group_seed)
        config={'cadence_sec':rng.choice([1,2,5]),'receive_delay_sec':rng.choice([0,.1,.3]),
                'flow_lpm':rng.choice([.6,1.2,2.4,4.8]),'leave_at':rng.choice([10,15,18]),
                'brief_leave_at':rng.choice([22,24,25]),'brief_duration':rng.choice([3,5,8])}
        for scenario in SCENARIOS:
            trial_id=f'bsim1-s{seed}-{group}-{scenario}'
            rows=generate_trial(trial_id,scenario,config)
            for row in rows:validate_raw_observation(row)
            target=scenario in ('unattended','presence_dropout')
            trials.append({'trial_id':trial_id,'cohort_id':group,'split':split_for[group],
                           'scenario':scenario,'source':'simulation','parameters':config,
                           'candidate_target':target,'label_basis':'scripted persistent-unattended episode annotation',
                           'observation_count':len(rows)})
            observations.extend({'trial_id':trial_id,'observation':row} for row in rows)
            labels.extend({'trial_id':trial_id,'cohort_id':group,'split':split_for[group],
                           'window_end':(START+timedelta(seconds=end)).isoformat(),
                           'candidate_target':target,'sample_unit':'window','window_width_sec':30,
                           'label_basis':'scripted episode annotation, not classifier prediction'} for end in ENDS)
    raw=b''.join(packed(row)+b'\n' for row in observations)
    label_bytes=b''.join(packed(row)+b'\n' for row in labels)
    dataset_hash=sha(packed({'trials':trials,'labels':labels,'observations_sha256':sha(raw)}))
    dataset_id='b-sim1-'+dataset_hash[:16]
    (output/'observations.jsonl.gz').write_bytes(gzip.compress(raw,mtime=0))
    (output/'labels.jsonl').write_bytes(label_bytes)
    json_file(output/'trials.json',{'trials':trials})
    split={'dataset_id':dataset_id,'grouping':'cohort_id; all scenarios and overlapping windows stay together',
           'role':'declared development split; no model selection has run', 'groups':split_groups,
           'trials':{name:[trial['trial_id'] for trial in trials if trial['split']==name] for name in split_groups}}
    json_file(output/'split_manifest.json',split)
    json_file(output/'dataset.json',{
        'dataset_schema_version':FORMAT,'dataset_id':dataset_id,'source':'simulation','seed':seed,
        'generator_sha256':sha(Path(__file__).read_bytes()),'dataset_sha256':dataset_hash,
        'observations_uncompressed_sha256':sha(raw),'label_sha256':sha(label_bytes),
        'cohorts':cohorts,'trial_count':len(trials),'window_label_count':len(labels),
        'observation_count':len(observations),'positive_trials':sum(t['candidate_target'] for t in trials),
        'negative_trials':sum(not t['candidate_target'] for t in trials),
        'window_ends_sec':list(ENDS),'split_trial_counts':{name:len(ids) for name,ids in split['trials'].items()},
        'training_complete':False,'evaluation_complete':False,
        'limitations':[
            'Synthetic feasibility data, not real-world accuracy or a statistically representative sample.',
            'Same scenario families appear in all partitions; this split does not test unseen family generalization.',
            'Cohorts prevent splitting paired/overlapping samples, but synthetic settings may repeat across cohorts.',
            'Hidden-present and unattended observations are identical apart from trial-scoped identities.',
            'Brief-leave negative labels use complete operation-script knowledge, including a future return.',
            'Only window snapshots of one binary task; not an event false-alarm or response-latency benchmark.',
            'Cadence two may leave no flow endpoint at window end 35; UNKNOWN is a legitimate outcome.',
            'DEVICE_SYNCED and K=60 calibration are synthetic conventions, not measured hardware evidence.',
            'Water observations are dry; no model may replace the independent water-contact safety path.',
            'Train with approved sensor-derived features only: no labels, trial/cohort/scenario IDs, parameters or split fields.',
        ],
    })
    (output/'README.md').write_bytes(('''# B-SIM-001｜扩展仿真数据与声明分区

这是下一轮 B 实验的数据准备，不是已训练/已评估模型，也不代表 G3 通过。
默认 12 个 cohort × 6 个场景 = 72 trial，每个 trial 有 30/35/40 秒三个窗口标签。
同 cohort 的所有场景及同 trial 的所有重叠窗留在同一分区；声明的测试集不能用于调参。
场景：空闲、有人流水、短暂离开、持续离开、静止人员未检出、人员传感掉线。
标签来自操作脚本，不导入/调用被评估规则。短暂离开的负标签包含未来返回的先验；
静止在场与真实离开存在观测不可区分反例，不能据此宣称在线识别真实无人。

文件：dataset.json（身份/来源/限制）、split_manifest.json（分区）、trials.json（场景与标签依据）、
labels.jsonl（窗口标签）、observations.jsonl.gz（标准库 gzip 可读的完整观测）、manifest.json（文件哈希）。
观察身份在每个 trial 中唯一；不要把各 trial 合并成一个在线设备流。
分类器只能使用传感特征，不得使用场景名、生成参数、ID、标签或分区信息作为预测输入。

复现：python scripts/build_b_sim_dataset.py --output <全新目录> --seed 20261110 --cohorts 12
核验：python scripts/build_b_sim_dataset.py --verify <数据目录>
输出拒绝覆盖旧目录。生成时不计算 C0–C3 指标，不读取测试集调参。
''').encode('utf-8'))
    json_file(output/'manifest.json',{'format':'sha256-dataset-manifest-v1','files':[
        {'path':path.name,'sha256':sha(path.read_bytes()),'bytes':path.stat().st_size}
        for path in sorted(output.iterdir()) if path.is_file()]})
    return verify(output)


def verify(output):
    output=Path(output).resolve()
    meta=json.loads((output/'dataset.json').read_text(encoding='utf-8'))
    if meta['dataset_schema_version']!=FORMAT or meta['source']!='simulation' or meta['training_complete'] or meta['evaluation_complete']:
        raise ValueError('dataset scope mismatch')
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    paths=[entry['path'] for entry in manifest['files']]
    if len(paths)!=len(set(paths)) or set(paths)!={p.name for p in output.iterdir() if p.is_file() and p.name!='manifest.json'}:
        raise ValueError('dataset inventory mismatch')
    for item in manifest['files']:
        path=(output/item['path']).resolve()
        if not path.is_relative_to(output) or path.stat().st_size!=item['bytes'] or sha(path.read_bytes())!=item['sha256']:
            raise ValueError('dataset artifact mismatch')
    raw=gzip.decompress((output/'observations.jsonl.gz').read_bytes())
    observations=[json.loads(line) for line in raw.splitlines()]
    labels=[json.loads(line) for line in (output/'labels.jsonl').read_text(encoding='utf-8').splitlines()]
    trials=json.loads((output/'trials.json').read_text(encoding='utf-8'))['trials']
    splits=json.loads((output/'split_manifest.json').read_text(encoding='utf-8'))
    if sha(raw)!=meta['observations_uncompressed_sha256'] or sha((output/'labels.jsonl').read_bytes())!=meta['label_sha256']:
        raise ValueError('uncompressed data mismatch')
    if sha(packed({'trials':trials,'labels':labels,'observations_sha256':sha(raw)}))!=meta['dataset_sha256']:
        raise ValueError('dataset semantic digest mismatch')
    if meta['dataset_id']!='b-sim1-'+meta['dataset_sha256'][:16] or splits['dataset_id']!=meta['dataset_id']:
        raise ValueError('dataset identity mismatch')
    ids={trial['trial_id']:trial for trial in trials}
    if len(ids)!=len(trials) or len(trials)!=meta['trial_count'] or len(labels)!=meta['window_label_count']:
        raise ValueError('trial or label inventory mismatch')
    assigned={};group_splits={}
    for partition,members in splits['trials'].items():
        for identity in members:
            if identity in assigned or identity not in ids:raise ValueError('trial split overlap')
            assigned[identity]=partition
    if set(assigned)!=set(ids):raise ValueError('trial split incomplete')
    for trial in trials:
        identity=trial['trial_id'];group=trial['cohort_id'];partition=trial['split']
        if assigned[identity]!=partition or group_splits.setdefault(group,partition)!=partition or group not in splits['groups'][partition]:
            raise ValueError('cohort split leakage')
        if type(trial['candidate_target']) is not bool or trial['candidate_target']!=(trial['scenario'] in ('unattended','presence_dropout')):
            raise ValueError('script label mismatch')
    split_group_ids=[identity for members in splits['groups'].values() for identity in members]
    if len(split_group_ids)!=len(set(split_group_ids)) or set(split_group_ids)!=set(group_splits) or len(group_splits)!=meta['cohorts']:
        raise ValueError('cohort group inventory mismatch')
    windows=set()
    for label in labels:
        trial=ids[label['trial_id']];key=(label['trial_id'],label['window_end'])
        if key in windows or label['split']!=trial['split'] or type(label['candidate_target']) is not bool or label['candidate_target']!=trial['candidate_target']:
            raise ValueError('window label leakage/mismatch')
        windows.add(key)
    expected_windows={(identity,(START+timedelta(seconds=end)).isoformat()) for identity in ids for end in ENDS}
    if windows!=expected_windows:raise ValueError('window inventory mismatch')
    obs_ids=set();counts={identity:0 for identity in ids}
    for item in observations:
        identity=item['trial_id'];row=item['observation'];key=(identity,row['observation_id'])
        if identity not in ids or key in obs_ids or row['source']!='simulation':raise ValueError('observation scope mismatch')
        obs_ids.add(key);counts[identity]+=1
    if any(counts[t['trial_id']]!=t['observation_count'] for t in trials):raise ValueError('observation count mismatch')
    if len(observations)!=meta['observation_count'] or sum(t['candidate_target'] for t in trials)!=meta['positive_trials'] or sum(not t['candidate_target'] for t in trials)!=meta['negative_trials']:
        raise ValueError('dataset accounting mismatch')
    if meta['split_trial_counts']!={name:len(ids) for name,ids in splits['trials'].items()}:
        raise ValueError('split count mismatch')
    return {'status':'PASS','dataset_id':meta['dataset_id'],'trials':len(trials),'window_labels':len(labels),
            'observations':len(observations),'split_trial_counts':meta['split_trial_counts'],'training_complete':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output',type=Path);group.add_argument('--verify',type=Path)
    parser.add_argument('--seed',type=int,default=20261110);parser.add_argument('--cohorts',type=int,default=12)
    args=parser.parse_args()
    print(json.dumps(build(args.output,args.seed,args.cohorts) if args.output else verify(args.verify),ensure_ascii=False))
