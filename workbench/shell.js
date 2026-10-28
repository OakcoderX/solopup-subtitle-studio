/* Fixed application actions. Existing episode editors and persisted state stay authoritative. */
(()=>{
 const words={
  save:['保存','Save','저장','保存'],saving:['保存中…','Saving…','저장 중…','保存中…'],export:['导出','Export','내보내기','書き出す'],projects:['分集','Episodes','에피소드','エピソード'],close:['关闭','Close','닫기','閉じる'],dirty:['有未保存修改','Unsaved changes','저장되지 않음','未保存の変更'],saved:['已保存','Saved','저장됨','保存済み'],failed:['保存未完成，请检查连接或版本冲突','Save incomplete: check connection or revision conflict','저장 실패: 연결 또는 버전 충돌 확인','保存できません：接続または版の競合を確認'],title:['导出字幕','Export subtitles','자막 내보내기','字幕を書き出す'],scope:['范围','Scope','범위','範囲'],episode:['当前分集','Current episode','현재 에피소드','現在の話'],project:['当前项目全部分集（每集最新可用版）','Project: latest available version of each episode','프로젝트: 에피소드별 최신 버전','プロジェクト：各話の最新利用可能版'],tracks:['字幕版本','Tracks','자막 버전','字幕版'],both:['普通版 + SDH','Normal + SDH','일반 + SDH','通常 + SDH'],normal:['普通版','Normal','일반','通常'],format:['格式','Format','형식','形式'],offset:['交付时间偏移（秒）','Delivery offset (seconds)','납품 시간 오프셋(초)','納品時刻オフセット（秒）'],note:['预览与编辑使用原视频时码；偏移只用于本次导出，不修改源字幕。','Preview/editing use source timecodes. Offset applies once to this export only.','미리보기와 편집은 원본 시각 기준입니다. 오프셋은 이번 내보내기에만 적용됩니다.','プレビューと編集は元動画の時刻。オフセットは今回の出力のみに適用。'],draft:['未通过交付检查的文件会标为 REVIEW_DRAFT；导出不代表审核通过。','Blocked tracks are labeled REVIEW_DRAFT. Export is not approval.','검사 미통과 자막은 REVIEW_DRAFT로 표시됩니다.','未通過の字幕は REVIEW_DRAFT と表示されます。'],run:['保存并生成压缩包','Save & create ZIP','저장 후 ZIP 생성','保存してZIPを作成'],busy:['正在保存和导出…','Saving and exporting…','저장 및 내보내는 중…','保存・書き出し中…'],error:['导出失败，修改仍保留：','Export failed; edits retained: ','내보내기 실패: ','書き出しに失敗：']
 };
 const t=k=>words[k]?.[['zh-CN','en','ko','ja'].indexOf(uiLocale)]||words[k]?.[1]||k;
 const pref={get(k){try{return localStorage.getItem(k)}catch(_){return null}},set(k,v){try{localStorage.setItem(k,v)}catch(_){}}};
 const header=document.querySelector('header.top'),toggle=document.getElementById('toggleProjects');
 toggle.textContent='☰';toggle.classList.add('drawerToggle');toggle.setAttribute('aria-controls','episodeDrawer');header.prepend(toggle);
 projectsPane.id='episodeDrawer';projectsPane.setAttribute('aria-label','Episodes');
 const dismiss=document.createElement('button');dismiss.id='closeEpisodeDrawer';dismiss.type='button';dismiss.textContent='×';projectsPane.querySelector('.projectHeading').append(dismiss);
 const backdrop=document.createElement('button');backdrop.className='drawerBackdrop';backdrop.tabIndex=-1;backdrop.setAttribute('aria-label','Close episodes');document.body.append(backdrop);
 function setDrawer(open){document.body.classList.toggle('drawerOpen',open);projectsPane.inert=!open;projectsPane.setAttribute('aria-hidden',String(!open));toggle.setAttribute('aria-expanded',String(open));backdrop.hidden=!open;pref.set('studio-drawer-open',String(open));requestAnimationFrame(()=>fitOverlay())}
 toggle.onclick=()=>setDrawer(!document.body.classList.contains('drawerOpen'));dismiss.onclick=()=>{setDrawer(false);toggle.focus()};backdrop.onclick=()=>setDrawer(false);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]')){setDrawer(false);toggle.focus()}});
 setDrawer(pref.get('studio-drawer-open')==='true');
 const actions=document.createElement('div');actions.className='headerActions';actions.innerHTML='<span id="globalSaveStatus" role="status" aria-live="polite"></span><button id="globalSave" type="button"></button><button id="globalExport" type="button" class="primary"></button>';header.append(actions);
 // The familiar status remains in the header; old per-track action IDs are retained for compatibility.
 for(const id of ['saveBtn','saveReviewBtn','exportStandardIttBtn','saveSoundBtn'])document.getElementById(id).classList.add('legacyAction');
 const pane=document.createElement('dialog');pane.id='exportDialog';pane.className='studioDialog exportDialog';pane.setAttribute('aria-labelledby','exportHeading');
 pane.innerHTML='<h2 id="exportHeading" data-shell="title"></h2><label><span data-shell="scope"></span><select id="exportScope"><option value="episode" data-shell="episode"></option><option value="project" data-shell="project"></option></select></label><label><span data-shell="tracks"></span><select id="exportTracks"><option value="both" data-shell="both"></option><option value="standard" data-shell="normal"></option><option value="sdh">SDH</option></select></label><label><span data-shell="format"></span><select id="bundleFormat"><option value="itt">Amazon ITT</option><option value="srt">SRT</option></select></label><label><span data-shell="offset"></span><input id="exportOffset" type="number" min="0" max="3600" step="0.001" value="0"></label><p data-shell="note"></p><p class="exportWarning" data-shell="draft"></p><p id="exportError" role="alert"></p><div class="dialogActions"><button id="cancelExport" type="button" data-shell="close"></button><button id="runExport" type="button" class="primary" data-shell="run"></button></div>';
 document.body.append(pane);
 let saving=false,failed=false,exporting=false;
 function status(){const pending=dirty||soundDirty;const el=document.getElementById('globalSaveStatus');const text=saving?t('saving'):failed?t('failed'):pending?t('dirty'):t('saved');if(el.textContent!==text)el.textContent=text;el.classList.toggle('unsaved',!!(pending||failed));document.getElementById('globalSave').disabled=saving||exporting;}
 async function saveAll(){if(saving)return false;saving=true;failed=false;status();try{const ok=await flushReview();if(!ok){failed=true;toast(t('failed'))}return ok}catch(_){failed=true;toast(t('failed'));return false}finally{saving=false;status()}}
 document.getElementById('globalSave').onclick=saveAll;
 document.addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='s'){e.preventDefault();saveAll()}});
 document.getElementById('globalExport').onclick=()=>{document.getElementById('exportError').textContent='';document.getElementById('exportOffset').value=pref.get('export-offset-'+currentEpisode)||'0';pane.showModal()};
 document.getElementById('cancelExport').onclick=()=>pane.close();
 document.getElementById('runExport').onclick=async()=>{
  if(exporting)return;exporting=true;const run=document.getElementById('runExport'),close=document.getElementById('cancelExport');run.disabled=close.disabled=true;run.textContent=t('busy');status();
  try{
   if(!await saveAll())throw Error(t('failed'));
   if(soundNeedsCompose){await enterFilm();if(soundNeedsCompose)throw Error('Sound decisions could not be composed; retry after reconnecting.')}
   const offset=document.getElementById('exportOffset');if(!offset.checkValidity())throw Error('Offset must be between 0 and 3600 seconds.');
   const scope=document.getElementById('exportScope').value;
   const query=new URLSearchParams({scope,project:selectedProject,tracks:document.getElementById('exportTracks').value,format:document.getElementById('bundleFormat').value,offset:offset.value||'0'});
   const r=await apiFetch('/api/export/bundle?'+query);
   if(!r.ok){const d=await r.json().catch(()=>({error:'Service upgrade or connection required'}));throw Error(d.error||'Export failed')}
   const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/)?.[1]||'subtitles.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);pref.set('export-offset-'+currentEpisode,offset.value);pane.close();
  }catch(e){document.getElementById('exportError').textContent=t('error')+e.message}
  finally{exporting=false;run.disabled=close.disabled=false;run.textContent=t('run');status()}
 };
 function locale(){toggle.setAttribute('aria-label',t('projects'));toggle.title=t('projects');dismiss.setAttribute('aria-label',t('close'));document.getElementById('globalSave').textContent=t('save');document.getElementById('globalSave').title=t('save')+' (⌘/Ctrl+S)';document.getElementById('globalExport').textContent=t('export')+' ▾';pane.querySelectorAll('[data-shell]').forEach(el=>el.textContent=t(el.dataset.shell));status()}
 document.getElementById('uiLanguage').addEventListener('change',locale);locale();
 // Detect both subtitle and sound edits without changing either editor's data model.
 const timer=setInterval(status,500);
 const mediaNotice=document.createElement('div');mediaNotice.className='mediaNotice';mediaNotice.setAttribute('role','status');mediaNotice.hidden=true;header.after(mediaNotice);
 async function mediaStatus(){try{const r=await apiFetch('/api/media-status');if(!r.ok)return;const d=await r.json();mediaNotice.hidden=d.available;document.body.classList.toggle('mediaMissing',!d.available);mediaNotice.textContent=uiLocale==='zh-CN'?'视频当前不可用；字幕和审核进度已保留。请接回素材盘后刷新，仍可编辑和保存字幕。':'Video unavailable; saved captions/reviews remain editable. Reconnect source media and refresh.';}catch(_){}}
 mediaStatus();const mediaTimer=setInterval(mediaStatus,15000);
 window.addEventListener('pagehide',()=>{clearInterval(timer);clearInterval(mediaTimer)});
})();
