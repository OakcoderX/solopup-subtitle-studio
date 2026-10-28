"""Versioned, explicit project delivery targets. Existing episodes are never migrated."""
import copy

LANGUAGES = {'en-US': 'English (US)', 'en-GB': 'English (UK)'}
PROFILES = {
    'children': {'id': 'amazon_itt_children_17_120', 'cps': 17, 'wpm': 120},
    'adult': {'id': 'amazon_itt_adult_20_220', 'cps': 20, 'wpm': 220},
}

def validate(settings):
    if not isinstance(settings, dict):
        raise ValueError('Select language, platform and audience.')
    language = settings.get('targetLanguage')
    audience = settings.get('audience')
    if language not in LANGUAGES:
        raise ValueError('Automatic production currently supports English US/UK only. Other languages require verified language profiles.')
    if settings.get('platform') != 'amazon' or audience not in PROFILES:
        raise ValueError('Select Amazon and children or adult.')
    workflow=settings.get('workflow','sdh')
    if workflow not in ('sdh','bilingual'):raise ValueError('Select a supported workflow.')
    if workflow=='bilingual':
        if settings.get('sourceLanguage','zh-CN')!='zh-CN':raise ValueError('Bilingual production currently supports Chinese audio to English.')
        rate=str(settings.get('editFrameRate','source'))
        if rate not in ('source','24','25','30','50','60'):raise ValueError('Invalid subtitle editing frame rate.')
        return {'workflow':'bilingual','sourceLanguage':'zh-CN','targetLanguage':language,
                'platform':'amazon','audience':audience,'editFrameRate':rate,
                'policyVersion':'bilingual-screens-v1','subtitleSpec':'bilingual_17_21',
                'limits':{'targetCps':17,'maxCps':21,'wpmHardGate':False,'maxLines':2,
                          'enLineChars':42,'zhLineChars':16,'minDurationSeconds':5/6,
                          'maxDurationSeconds':7,'gapEditFrames':2},
                'ruleSource':'User selected localization profile; confirm title-specific Amazon requirements.'}
    return {'targetLanguage': language, 'platform': 'amazon', 'audience': audience,
            'subtitleSpec': PROFILES[audience]['id'], 'policyVersion': 'prime-english-2026-08-v1',
            'ruleSource': 'Amazon English SDH/CC 2026-08; verify title-specific and newer locale instructions',
            'limits': {**PROFILES[audience], 'max_lines': 2, 'max_line_chars': 42,
                       'min_frames': 20, 'max_seconds': 7, 'gap_frames': 2}}

def profile(state=None):
    from timed_text import PROFILE
    state = state or {}
    spec = state.get('subtitleSpec', 'prime')
    result = copy.deepcopy(PROFILE)
    if spec == 'amazon_itt_adult_20_220':
        result.update(PROFILES['adult'], review_threshold_cps=20, note='Archived Amazon English SDH August 2026: adult 20 CPS, preferred180–200 WPM, maximum220 WPM. Verify current locale/title-specific instructions.')
    elif spec == 'amazon_itt_children_13':
        result.update(id=spec, cps=13, review_threshold_cps=13, note='General children13CPS selection. Confirm locale/title rules; retained120WPM is a local gate, not a universal platform rule.')
    if state.get('projectSettings'):
        result['source_hierarchy']=['title-specific delivery instructions','language-specific Amazon guide','Amazon general principles','explicit project rules']
        if spec=='amazon_itt_children_17_120':result['note']='Archived Amazon English SDH August2026 children profile:17CPS/120WPM. Confirm newer locale/title-specific requirements.'
    return result
