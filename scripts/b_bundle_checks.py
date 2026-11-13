"""Shared semantic label binding; identity comparisons require strict booleans."""

def check_annotations(rows, annotations):
    key=lambda r:(r['trial_id'],r['window_end'])
    index={key(r):r for r in annotations}
    if len(index)!=len(annotations) or len({key(r) for r in rows})!=len(rows) or set(index)!={key(r) for r in rows}:
        raise ValueError('label inventory mismatch')
    for row in rows:
        label=index[key(row)]
        if label['split']!=row['split']:raise ValueError('label split mismatch')
        target=label['candidate_target']
        if target is not None and type(target) is not bool:raise ValueError('label must be boolean or null')
        if label['source_history_sha256']!=row['input_history_sha256']:raise ValueError('label history binding mismatch')
        if type(label['original_episode_target']) is not bool or label['original_episode_target'] is not row['original_episode_target']:
            raise ValueError('episode truth binding mismatch')
        if (target is None)!=bool(row['rejection_reasons']):raise ValueError('label eligibility mismatch')
    return index
