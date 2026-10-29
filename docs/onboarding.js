'use strict';
(function () {
  const original = [
    { start: 0, end: 2000, zh: '门在那边。', en: 'The door is over there.' },
    { start: 2200, end: 4200, zh: '等一下。', en: 'Wait a moment.' },
    { start: 4400, end: 6400, zh: '我们一起走。', en: "Let's go together." }
  ];
  function stamp(ms) {
    return `${String(Math.floor(ms / 3600000)).padStart(2,'0')}:${String(Math.floor(ms / 60000) % 60).padStart(2,'0')}:${String(Math.floor(ms / 1000) % 60).padStart(2,'0')},${String(ms % 1000).padStart(3,'0')}`;
  }
  function cleanText(s) {
    return String(s).replace(/\r\n?/g,'\n').split('\n').map(x => x.trim()).filter(Boolean).join('\n');
  }
  function srt(cues, language) {
    if (!['en','zh'].includes(language)) throw new Error('Unknown language');
    if (cues.some(c => !cleanText(c[language]))) throw new Error('Every screen needs subtitle text / 每一屏都需要文字');
    return cues.map((c, i) => `${i+1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${cleanText(c[language])}\n`).join('\n');
  }
  function commands(os) {
    const win = os === 'windows', py = win ? '.venv\\Scripts\\python.exe' : '.venv/bin/python';
    return [(win ? 'py -3' : 'python3') + ' bootstrap.py --install', `${py} scripts/doctor.py --json`, `${py} scripts/make_demo.py`, `${py} start_workbench.py --video examples/demo/generated/demo.mp4 --standard-srt examples/demo/normal.srt --sdh-srt examples/demo/sdh.srt --port 8877`].join('\n');
  }
  if (typeof module !== 'undefined') module.exports = { original, stamp, cleanText, srt, commands };
  if (typeof document === 'undefined') return;
  const $ = id => document.getElementById(id);
  if ($('translation')) {
    let cues = original.map(c => ({...c}));
    function show() {
      const i = Number($('cue-choice').value), c = cues[i];
      $('cue-number').textContent = `SCREEN ${i+1} / 3 · REVIEW_DRAFT · ${stamp(c.start)} → ${stamp(c.end)}`;
      $('translation').value = c.en;
      $('source-preview').textContent = c.zh;
      update();
    }
    function update() {
      const i = Number($('cue-choice').value), c = cues[i]; c.en = $('translation').value;
      $('translation-preview').textContent = c.en || '…';
      const n = Array.from(c.en.replace(/\r?\n/g,'')).length;
      $('demo-metrics').textContent = `${n} characters / 字符 · ${(n / ((c.end-c.start)/1000)).toFixed(1)} CPS · ${((c.end-c.start)/1000).toFixed(1)} seconds · Pending human review / 待人工审核`;
    }
    $('cue-choice').addEventListener('change',show);
    $('translation').addEventListener('input',()=>{update();$('demo-status').textContent='Changed in this tab only / 修改仅保留在本页';});
    $('demo-reset').addEventListener('click',()=>{cues=original.map(c=>({...c}));$('cue-choice').value='0';show();$('demo-status').textContent='Synthetic sample restored / 已恢复合成示例';});
    for (const language of ['en','zh']) $('export-'+language).addEventListener('click',()=>{
      try {
        const text = srt(cues,language), url=URL.createObjectURL(new Blob([text],{type:'text/plain;charset=utf-8'}));
        const a=document.createElement('a');a.href=url;a.download=`solopup-demo.REVIEW_DRAFT.${language}.srt`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        $('demo-status').textContent=`Download requested: ${a.download}. Check your browser downloads. / 已请求下载，请查看浏览器下载记录。`;
      } catch(e) {$('demo-status').textContent=e.message;}
    });
    show();
  }
  if ($('install-os')) {
    function render() {$('install-commands').textContent=commands($('install-os').value);$('copy-status').textContent='';}
    $('install-os').addEventListener('change',render);render();
    $('copy-commands').addEventListener('click',async()=>{
      try {await navigator.clipboard.writeText($('install-commands').textContent);$('copy-status').textContent='Copied. Review before running / 已复制，执行前请检查。';}
      catch {$('copy-status').textContent='Copy is unavailable here. Select and copy the visible commands manually. / 请手动选择上方命令复制。';}
    });
  }
  if ($('resource-query')) {
    const items=Array.from($('resource-results').children);
    function filter() {
      const terms=$('resource-query').value.trim().toLowerCase().split(/\s+/).filter(Boolean), lang=$('resource-language').value;
      let count=0;
      for(const li of items){const text=li.textContent.toLowerCase();li.hidden=!(terms.every(t=>text.includes(t))&&(lang==='all'||li.dataset.lang===lang));if(!li.hidden)count++;}
      $('resource-count').textContent=count ? `${count} resources / 项资源` : 'No matches. Try a shorter term or All languages. / 没有匹配项，请缩短关键词或选择全部语言。';
    }
    $('resource-query').addEventListener('input',filter);$('resource-language').addEventListener('change',filter);filter();
  }
})();
