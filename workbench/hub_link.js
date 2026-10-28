(()=>{
 const header=document.querySelector('header.top')||document.querySelector('body>header');if(!header)return;
 const button=document.createElement('button');button.id='unifiedProjects';button.type='button';button.textContent='项目与制作';button.style.cssText='white-space:nowrap;border:1px solid #435268;border-radius:6px;background:#243344;color:#fff;padding:7px 10px;margin-right:8px;cursor:pointer';
 const navigate=async(path)=>{if(typeof flushReview==='function'){if(!await flushReview())return}else if(typeof dirty!=='undefined'&&dirty){if(!await save())return}window.location.href=path};
 button.onclick=()=>navigate('/projects');const actions=header.querySelector('.actions,.headerActions');if(actions)actions.prepend(button);else header.append(button);
 // Existing toolbar buttons use the same shared creation/import surface.
 const newProject=document.getElementById('newProject'),add=document.getElementById('addEpisodes');
 if(newProject)newProject.onclick=()=>navigate('/projects?new=1');
 if(add)add.onclick=()=>navigate('/projects?add=1&project='+encodeURIComponent(typeof selectedProject==='undefined'?'':selectedProject));
})();
