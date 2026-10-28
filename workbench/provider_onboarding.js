/* No key is read or stored here. This guide never invokes a model. */
(()=>{
 const zh=()=>!/^en/.test(document.getElementById('uiLanguage')?.value||document.documentElement.lang||'zh');
 const t=(a,b)=>zh()?a:b,modal=document.createElement('dialog');modal.id='qwenOnboarding';modal.style.cssText='max-width:720px;padding:24px;border:1px solid #426177;border-radius:12px;background:#14202d;color:#edf5fa';
 const button=document.createElement('button');button.type='button';button.id='qwenGettingStarted';button.style.margin='6px';(document.querySelector('header .actions')||document.querySelector('header')||document.body).append(button);document.body.append(modal);
 function content(){
  button.textContent=t('Qwen 入门与费用','Qwen setup & costs');
  modal.innerHTML='<h2>'+t('开始AI制作前，请先配置自己的Qwen API Key','Set up your own Qwen API key before AI production')+'</h2><ol><li>'+t('申请：开通阿里云百炼，在所选地域创建API Key；将Key、同地域接口地址和有权限的模型填入本机设置。','Apply: activate Alibaba Cloud Model Studio, create an API key in your region, then enter the key, matching endpoint and accessible model IDs locally.')+'</li><li>'+t('先评估：查询实际模型的免费额度和有效期；如适用，开启“免费额度用完即停”，先制作30—60秒真实对白片段。并非所有地域或模型都有免费额度。','Evaluate first: check the exact model’s trial quota and expiry. Where available, enable Free Quota Only and try 30–60 seconds of real dialogue. Not every region/model offers free quota.')+'</li><li>'+t('再批量：确认转写、翻译效果后，在百炼完成所需认证、准备余额和预算，并按官方说明设置计费。通常继续使用同一个Key，不是购买另一种“收费Key”。','Then scale up: check transcription and translation, complete the provider’s account requirements, prepare funds/budget and enable appropriate billing. Usually the same key continues; you do not buy a different “paid key”.')+'</li></ol><p>'+t('没有Key无法完成需要云模型的识别/翻译；导入已有字幕、播放与人工校对仍可离线使用。保存配置不测试连接、不调用模型，也不证明免费额度或付费权限可用。','Without a key, cloud AI production is unavailable. Imported-subtitle playback and manual review can still work offline. Saving settings makes no model request and does not verify quota or billing access.')+'</p><p><a style="color:#7ee3cb" target="_blank" rel="noopener noreferrer" href="https://help.aliyun.com/zh/model-studio/get-api-key/">'+t('官方Key申请说明','Official key setup')+'</a> · <a style="color:#7ee3cb" target="_blank" rel="noopener noreferrer" href="https://help.aliyun.com/'+(zh()?'zh':'en')+'/model-studio/new-free-quota">'+t('官方免费额度与计费说明','Official trial and billing rules')+'</a> · <a style="color:#7ee3cb" target="_blank" href="/qwen-setup-guide">'+t('完整操作指南','Full setup guide')+'</a></p><div style="display:flex;gap:12px;flex-wrap:wrap"><button id="qwenStartSetup">'+t('配置Qwen，开始制作','Configure Qwen')+'</button><button id="qwenOfflineOnly">'+t('暂不配置，只校对已有字幕','Skip: review existing subtitles offline')+'</button></div>';
  modal.querySelector('#qwenStartSetup').onclick=()=>{modal.close();const existing=document.getElementById('providerSetup')||document.getElementById('providerSettings');if(existing)existing.click();else location.href='/projects?setup=qwen'};
  modal.querySelector('#qwenOfflineOnly').onclick=()=>modal.close();
 }
 function open(){content();if(!modal.open)modal.showModal()}
 button.onclick=open;content();
 fetch('/api/provider',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{
  if(!d)return;
  if(new URLSearchParams(location.search).get('setup')==='qwen'){(document.getElementById('providerSetup')||document.getElementById('providerSettings'))?.click();return}
  if(!d.configured){let seen=false;try{seen=sessionStorage.getItem('solopup.qwenGuideSeen')==='yes';sessionStorage.setItem('solopup.qwenGuideSeen','yes')}catch(_){}if(!seen)open()}
 }).catch(()=>{});
})();
