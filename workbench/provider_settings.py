"""Local-only provider setup. Status never returns credential bytes."""
import os
import sys
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import provider_config
from configure_qwen import save_configuration

def status(legacy_key_zip=None):
    root=provider_config.ROOT
    environment=bool(os.environ.get('QWEN_API_KEY') or os.environ.get('DASHSCOPE_API_KEY'))
    path=root/'config/team_api_key'
    present=environment or (path.is_file() and path.stat().st_size > 0)
    source='environment' if environment else 'local_file' if present else 'missing'
    # Backward compatibility: inspect archive metadata only; never read or return its key.
    if not present and legacy_key_zip and Path(legacy_key_zip).is_file():
        try:
            with zipfile.ZipFile(legacy_key_zip) as archive:
                present=any(x.filename.endswith('/config/team_api_key') and x.file_size>0 for x in archive.infolist())
            if present:source='legacy_archive'
        except (OSError,zipfile.BadZipFile):pass
    return {'configured':present, 'key_source':source,
            'base_url':provider_config.base_url(), 'audio_model':provider_config.model(),
            'text_model':provider_config.model('text'), 'connection_tested':False,
            'environment_overrides': [k for k in ('QWEN_API_KEY','DASHSCOPE_API_KEY','QWEN_BASE_URL','QWEN_AUDIO_MODEL','QWEN_TEXT_MODEL') if os.environ.get(k)]}

def save(data):
    if not isinstance(data,dict):raise ValueError('Invalid configuration')
    if any(not isinstance(data.get(k),str) or not 0 < len(data[k]) <= 2048 for k in ('key','base_url','audio_model','text_model')):
        raise ValueError('Enter key, HTTPS endpoint and model names.')
    if any(any(c.isspace() for c in data[k]) for k in ('audio_model','text_model')):
        raise ValueError('Model names cannot contain whitespace.')
    save_configuration(provider_config.ROOT, data['key'], data['base_url'], data['audio_model'], data['text_model'])
    return status()


def production_needs_provider(policy,entries):
    """Imported bilingual pairs are offline; automatic cloud stages require a key."""
    return policy.get('workflow')!='bilingual' or any(not (row.get('source_subtitles') and row.get('target_subtitles')) for row in entries)

def require_production_provider(policy,entries,provider):
    if production_needs_provider(policy,entries) and not provider.get('configured'):
        raise ValueError('AI制作需要先配置自己的Qwen API Key。请打开AI接口设置，先查看免费额度并测试小片段，再准备计费和预算进行批量制作。/ Configure your own Qwen API key before AI production. Check trial eligibility, test a short clip, then prepare billing/budget for batch work.')
