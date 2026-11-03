"""Experimental transition evidence: touching known intervals, plus supported right endpoint."""
def count_transitions(segments, *, endpoint=None):
    ordered=sorted(segments)
    comparable=False
    changes=0
    for previous,current in zip(ordered,ordered[1:]):
        if previous[1]==current[0]:
            comparable=True
            changes+=previous[2]!=current[2]
    if endpoint is not None and ordered:
        t,value=endpoint
        if ordered[-1][1]==t:
            comparable=True
            changes+=ordered[-1][2]!=value
    return changes if comparable else None
