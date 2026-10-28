"""Complete cue context at review chunk boundaries; ownership stays unchanged."""
def complete_window(rows,start,end,duration,pad=4):
    selected=[c for c in rows if c['start']<end and c['end']>max(0,start-pad)]
    begin=max(0,min([start-pad]+[c['start']-1 for c in selected]))
    stop=min(duration,max([end+pad]+[c['end']+2 for c in selected]))
    return begin,stop,selected
