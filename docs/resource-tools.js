/* SoloPup free editorial helpers. MIT. No network, analytics or persistent storage. */
(function (root) {
  'use strict';
  function readingSpeed(text, duration, threshold) {
    duration = Number(duration); threshold = Number(threshold);
    if (!Number.isFinite(duration) || duration <= 0 || !Number.isFinite(threshold) || threshold <= 0) throw new Error('Duration and threshold must be positive numbers. / 时长和阈值必须大于零。');
    const count = Array.from(String(text).replace(/[\r\n]/g, '')).length;
    if (!count) throw new Error('Enter subtitle text. / 请输入字幕文字。');
    const cps = count / duration;
    return {count, duration, cps, threshold, exceeds: cps > threshold};
  }
  function parseSrt(text) {
    text = String(text).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').trim();
    if (!text) throw new Error('SRT is empty. / SRT 为空。');
    if (text.length > 1000000) throw new Error('Use a smaller SRT example (under one million characters).');
    const stamp = '(\\d{2,}):([0-5]\\d):([0-5]\\d)[,.](\\d{3})';
    const times = new RegExp('^' + stamp + '\\s+-->\\s+' + stamp + '$');
    let previousEnd = -1;
    return text.split(/\n[ \t]*\n/).map((block, index) => {
      const lines = block.split('\n');
      if (!/^\d+$/.test(lines[0].trim()) || Number(lines[0]) !== index + 1) throw new Error('Cue ' + (index+1) + ': use sequential numeric cue IDs beginning at 1.');
      const m = (lines[1] || '').trim().match(times);
      if (!m) throw new Error('Cue ' + (index+1) + ': unsupported or invalid SRT timestamp.');
      const ms = n => Number(m[n])*3600000 + Number(m[n+1])*60000 + Number(m[n+2])*1000 + Number(m[n+3]);
      const start = ms(1), end = ms(5), caption = lines.slice(2).join('\n').trim();
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end)) throw new Error('Cue ' + (index+1) + ': timestamp outside supported range.');
      if (end <= start) throw new Error('Cue ' + (index+1) + ': end must be after start.');
      if (start < previousEnd) throw new Error('Cue ' + (index+1) + ': overlapping or out-of-order timing; review against video.');
      if (!caption) throw new Error('Cue ' + (index+1) + ': text is empty.');
      previousEnd = end;
      return {start, end, text: caption};
    });
  }
  function compareSrt(source, target) {
    let a, b;
    try { a = parseSrt(source); } catch (e) { throw new Error('Source / 原文: ' + e.message); }
    try { b = parseSrt(target); } catch (e) { throw new Error('Translation / 译文: ' + e.message); }
    const mismatches = [];
    for (let i=0; i<Math.min(a.length, b.length); i++) if (a[i].start !== b[i].start || a[i].end !== b[i].end) mismatches.push(i+1);
    return {sourceCount:a.length, targetCount:b.length, mismatches, aligned:a.length===b.length && !mismatches.length};
  }
  function filenames(name, format) {
    name = String(name).trim();
    if (!name || /[\\/\x00-\x1f<>:"|?*]/.test(name) || name === '.' || name === '..' || name.endsWith('.') || name.length > 240) throw new Error('Enter a filename only, without paths, reserved punctuation or trailing dots. / 请输入文件名，不要输入路径。');
    if (!['srt','itt'].includes(format)) throw new Error('Choose SRT or ITT.');
    const at = name.lastIndexOf('.'), stem = at > 0 ? name.slice(0, at) : name;
    return {zh:stem+'.zh.'+format, en:stem+'.en.'+format};
  }
  function workflow(task, inputs) {
    if (!['sdh','bilingual'].includes(task) || !['paired','source','video'].includes(inputs)) throw new Error('Choose a supported workflow and input.');
    const route = task === 'bilingual' ? 'Create a Chinese-audio bilingual project. / 建立中文配音双语项目。' : 'Create an ordinary subtitles/SDH project. / 建立普通字幕与 SDH 项目。';
    if (inputs === 'paired') return route+'\nImport video and both corresponding tracks for local manual review; no AI key needed. / 导入视频和对应双轨，本地人工审校无需 AI Key。\nKeep source/translation identity distinct from ordinary/SDH identity.';
    if (inputs === 'source') return route+'\nThe second track still needs preparation. Translation or SDH sound decisions need their own review; configured cloud AI may incur charges. / 第二轨仍需制作，翻译或声音判断需独立审校；云端 AI 可能收费。';
    return route+'\nPrepare a transcript against final audio first. Optional local ASR requires separate dependencies/model weights; cloud processing requires provider access and may cost money. / 先按原声准备转写；本地识别需模型，云端处理可能收费。';
  }
  const api = {readingSpeed, parseSrt, compareSrt, filenames, workflow};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.SoloPupHelpers = api;
  if (typeof document === 'undefined') return;
  const el = id => document.getElementById(id);
  function bind(form, output, run) {
    if (!el(form)) return;
    el(form).addEventListener('submit', event => { event.preventDefault(); try { el(output).textContent=run(); } catch(e) { el(output).textContent=e.message; } });
  }
  bind('cps-form','cps-result',()=>{const x=readingSpeed(el('cue-text').value,el('duration').value,el('threshold').value);return x.count+' characters / 字符\n'+x.cps.toFixed(2)+' CPS\n'+(x.exceeds?'Above your threshold: review wording or timing. / 超出项目阈值，请审校文字或时长。':'Within this chosen threshold. Human review still required. / 未超此阈值，仍需人工审校。');});
  bind('pair-form','pair-result',()=>{const x=compareSrt(el('source-srt').value,el('target-srt').value);return 'Source screens / 原文屏数: '+x.sourceCount+'\nTranslation screens / 译文屏数: '+x.targetCount+'\n'+(x.aligned?'Counts and times align. Translation and audio are not checked. / 屏数和时码对应；未核对翻译与音轨。':'Not aligned / 未对齐. Different timing at cues: '+(x.mismatches.join(', ')||'none; cue counts differ.'));});
  bind('name-form','name-result',()=>{const x=filenames(el('video-name').value,el('format').value);return x.zh+'\n'+x.en+'\nPreview only; no files renamed. / 仅预览，未重命名文件。';});
  bind('workflow-form','workflow-result',()=>workflow(el('workflow').value,el('inputs').value));
})(typeof globalThis !== 'undefined' ? globalThis : this);
