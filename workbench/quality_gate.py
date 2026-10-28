"""One report for production, workbench and export. Never fabricate approval."""
from collections import Counter
from timed_text import check,blocking_issues
from project_policy import profile
VERSION='1.9.0'
RULESET='prime-en-us-localized-2026-09-project-17cps-120wpm-v7'
def policy_basis(state):
    spec=state.get('subtitleSpec','prime')
    common={'platform':'Amazon Prime Video',
            'authority_order':['title-specific Slate / Kids+ delivery instructions when supplied',
                               'language-specific timed-text technical style guide',
                               'current Prime Video general subtitling principles',
                               'stricter project editorial rules'],
            'editorial_acceptance':'not established by automated checks'}
    if spec=='amazon_itt_adult_20_220':
        return {**common,'selected_profile':spec,'project_policy':{'cps':20,'wpm_max':220,'wpm_preferred':'180–200','max_lines':2},'note':'English SDH/CC archived August 2026 profile. Confirm title-specific/current locale instructions; local checks do not establish platform acceptance.'}
    if spec=='amazon_itt_children_17_120':
        return {**common,'selected_profile':spec,
                'selected_localized_guide':'English (US/UK), archived September 2026 guide',
                'project_policy':{'children_cps':17,'wpm':120,'max_lines':2,'preserve_spoken_words':True},
                'note':'The public general guide updated 2026-10-01 recommends 13 CPS for children and directs teams to language-specific guides for detailed requirements. This selected English-specific profile uses 17 CPS; 120 WPM and lexical preservation are project gates. Confirm any title-specific delivery sheet before final delivery.'}
    if spec=='amazon_itt_children_13':
        return {**common,'selected_profile':spec,'project_policy':{'children_cps':13},
                'note':'13 CPS is the current public Prime Video general recommendation for children. Check the language-specific guide and title-specific delivery instructions for applicable detailed rules.'}
    if spec=='custom':
        return {**common,'selected_profile':spec,'note':'Custom profile; verify its supplied source and title scope before delivery.'}
    return {**common,'selected_profile':spec,
            'note':'Prime Video technical requirements vary by language and title. Select and record the applicable language-specific guide before delivery.'}
def report(state,duration=None):
    import copy
    from evidence_gate import refresh
    state=refresh(copy.deepcopy(state))
    tracks={}
    for track in ('standard','sdh'):
        issues=check(state.get(track,[]),state.get('frameRate','24'),duration,state.get('sourceManifest',{}).get(track),state.get('reviewPolicy',{}).get('songSpeedAdvisory',False),state.get('preferredSpellings'),profile(state))
        tracks[track]={'issues':issues,'blocking':len(blocking_issues(issues)),
                       'by_rule':dict(Counter(f for x in issues for f in x['flags']))}
    from song_library import audit as audit_songs
    song_issues=[]
    if state.get('songLibrary'):
        for track in ('standard','sdh'):
            song_issues.extend(dict(x,track=track) for x in audit_songs(state.get(track,[]),state['songLibrary']))
        for m in state['songLibrary'].get('matches',[]):
            song_issues.extend(dict(x,master_id=m['master_id'],rule='song_master_unresolved') for x in m.get('issues',[]))
    release=state.get('release',{})
    policy_errors=[]
    if state.get('targetLanguage','en-US') not in {'en-US','en-GB'}:policy_errors.append('No verified automatic delivery profile for this target language.')
    if state.get('projectSettings') and state.get('targetLanguage') != state['projectSettings'].get('targetLanguage'):policy_errors.append('Episode language differs from project policy; confirm a new delivery profile.')
    sound_tasks=state.get('soundEvidenceRecheckTasks',[])
    ready=not policy_errors and not sound_tasks and not state.get('latestReviewFindings') and not song_issues and all(not x['blocking'] for x in tracks.values()) and release.get('content_verified') is True and not release.get('blockers')
    script_rows=state.get('scriptComparison',[])
    script_counts=Counter(x.get('classification','unknown') for x in script_rows)
    return {'system_version':VERSION,'ruleset':('prime-english-2026-08-'+profile(state)['id']) if state.get('subtitleSpec')=='amazon_itt_adult_20_220' else RULESET,'policy_basis':policy_basis(state),
            'status':'READY_FOR_DELIVERY' if ready else 'REVIEW_REQUIRED',
            'tracks':tracks,'review_findings':state.get('latestReviewFindings',[]),'song_issues':song_issues,'evidence_tasks':state.get('evidenceTasks',[]),'sound_evidence_tasks':sound_tasks,'context_tasks':len(state.get('layoutTasks',[]))+len(state.get('presentationTasks',[]))+len(state.get('evidenceTasks',[]))+len(sound_tasks),
            'script_comparison':{'performed':bool(script_rows),'cue_count':len(script_rows),'by_classification':dict(script_counts),'authority':'reference only; final audio governs wording; differences are not automatic errors'},
            'content_verified':release.get('content_verified',False),'release_blockers':release.get('blockers',[])+policy_errors,
            'limits':{'cps':profile(state)['cps'],'wpm':profile(state)['wpm'],'lines':2,'characters_per_line':42,'min_frames':20,'max_seconds':7},
            'meaning':'Technical self-check plus recorded evidence; not Amazon acceptance or automatic human approval.'}
