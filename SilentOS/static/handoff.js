// SilentOS routes reviewed text through its API; no voice input or UI scraping.
(()=>{
 const el=id=>document.getElementById(id),states=new WeakMap();
 const config=fetch('/api/config',{signal:AbortSignal.timeout(15000)}).then(async r=>{if(!r.ok)throw Error('Cannot read SilentOS configuration');return r.json();});
 let current=null,revision=0,parsing=false,submitting=false,parseTimer,refreshVersion=0,lastQueueSnapshot,photonReady=false;
 config.then(c=>{photonReady=c.photon?.configured===true;el('photonStatus').textContent=photonReady?'Photon 2.0 configured. Verify sender/contact destinations before sending.':'Photon messaging is not configured. General HeyClicky tasks and local message previews are available.';render();}).catch(e=>{el('photonStatus').textContent=e.message;});
 async function request(path,data){
  const c=await config;const r=await fetch(path,{method:data===undefined?'GET':'POST',headers:{'X-SilentOS-Token':c.session_token,'Content-Type':'application/json'},...(data===undefined?{}:{body:JSON.stringify(data)}),signal:AbortSignal.timeout(15000)});
  const result=await r.json();if(!r.ok)throw Error(result.error||`HTTP ${r.status}`);return result;
 }
 function render(){
  const state=current&&states.get(current),task=state?.kind==='task';
  const available=current?.state==='ready'&&!parsing&&!submitting&&!state?.queued;
  el('taskFields').hidden=!task;el('messageFields').hidden=task;
  const valid=task?el('taskText').value.trim():el('messageRecipient').value.trim()&&el('messageBody').value.trim();
  const configured=task||el('messageMode').value!=='send'||photonReady;
  el('queueCommand').disabled=!available||!valid||!configured;
  el('queueCommand').textContent=state?.queued?'Queued':submitting?'Queueing…':task?'Queue task for HeyClicky':el('messageMode').value==='send'?'Send through Photon':'Save message preview';
  for(const id of ['taskKind','taskText','taskMode','messageApp','messageRecipient','messageBody','messageMode'])el(id).disabled=!available||Boolean(state?.payload);
 }
 function maybeAuto(){const state=current&&states.get(current);if(el('autoQueue').checked&&state?.parsed&&!state.attempted&&!el('queueCommand').disabled)enqueue();}
 async function parse(source,text,version){
  try{
   const result=await request('/api/tasks/parse',{text,kind:el('taskKind').value||'auto'});
   if(current!==source||revision!==version)return;
   const state=states.get(source);state.kind=result.kind;state.parsed=result.parsed;
   el('taskText').value=result.task||'';el('messageApp').value=result.app||'imessage';el('messageRecipient').value=result.recipient||'';el('messageBody').value=result.message||'';
   el('handoffStatus').textContent=result.reason;parsing=false;render();maybeAuto();
  }catch(e){if(current===source&&revision===version){parsing=false;el('handoffStatus').textContent=e.message;render();}}
 }
 window.renderCommandHandoff=source=>{
  const prior=current;current=source;let state=states.get(source);
  if(!state){state={text:null,key:crypto.randomUUID(),kind:'task',parsed:false,queued:false,attempted:false};states.set(source,state);}
  if(source.state==='ready'&&state.text!==source.text&&!state.queued&&!state.payload){
   state.text=source.text;state.parsed=false;const version=++revision;parsing=true;clearTimeout(parseTimer);
   el('messageRecipient').value='';el('messageBody').value='';el('taskText').value='';el('handoffStatus').textContent='Routing task text…';
   parseTimer=setTimeout(()=>parse(source,source.text,version),200);
  }else if(source.state!=='ready'){
   ++revision;clearTimeout(parseTimer);parsing=false;state.text=null;
   if(prior!==source){el('messageRecipient').value='';el('messageBody').value='';el('taskText').value='';}
   el('handoffStatus').textContent=source.state==='incomplete'?'Incomplete command — record a new instruction.':'Finish a command or use the transcript / selection as a task.';
  }
  render();
 };
 async function enqueue(){
  if(el('queueCommand').disabled)return;const source=current,state=states.get(source);submitting=true;state.attempted=true;source.handoffLocked=true;el('commandText').readOnly=true;
  state.payload??={request_key:state.key,transcript:source.text,kind:state.kind,
   ...(state.kind==='task'?{task:el('taskText').value,mode:el('taskMode').value}:{app:el('messageApp').value,recipient:el('messageRecipient').value,message:el('messageBody').value,mode:el('messageMode').value})};
  render();
  try{const result=await request('/api/commands',state.payload);state.queued=true;if(current===source)el('handoffStatus').textContent=result.provider==='heyclicky'?'Task queued in SilentOS. An active HeyClicky agent can pick it up.':result.mode==='draft'?'Message preview queued locally. Nothing will be sent.':'Photon message queued for the configured destination.';await refresh();}
  catch(e){if(current===source)el('handoffStatus').textContent=e.message+' Retry uses the same request. Use New command to change it.';}
  finally{submitting=false;render();maybeAuto();}
 }
 async function refresh(){
  const version=++refreshVersion;
  try{
   const {commands}=await request('/api/commands');if(version!==refreshVersion)return;const snapshot=JSON.stringify(commands);if(snapshot===lastQueueSnapshot)return;lastQueueSnapshot=snapshot;el('commandQueue').replaceChildren();
   for(const c of commands){
    const item=document.createElement('li'),text=document.createElement('span');
    text.textContent=`${c.status} · ${c.provider||'legacy'} · ${c.mode} · ${c.kind==='task'?c.task:`${c.app} → ${c.recipient}: ${c.message}`}${c.detail?' — '+c.detail:''}${c.external_id?' · '+c.external_id:''}`;item.append(text);
    if(c.status==='queued'||c.status==='claimed'){
     const action=document.createElement('button');action.className='subtle';action.textContent=c.status==='queued'?'Cancel':'Worker stopped: mark uncertain';
     if(c.status==='claimed'){const hint=document.createElement('p');hint.textContent='Stop the worker first. Marking uncertain does not remotely stop it. Check for effects before repeating.';item.append(hint);}
     action.onclick=async()=>{action.disabled=true;try{await request(c.status==='queued'?'/api/commands/cancel':'/api/commands/resolve',{id:c.id});await refresh();}catch(e){el('queueError').textContent=e.message;action.disabled=false;}};item.append(action);
    }
    el('commandQueue').append(item);
   }
   if(!commands.length){const li=document.createElement('li');li.textContent='No tasks queued.';el('commandQueue').append(li);}el('queueError').textContent='';
  }catch(e){if(version===refreshVersion)el('queueError').textContent=e.message;}
 }
 el('queueCommand').onclick=enqueue;el('refreshCommands').onclick=refresh;
 el('taskKind').onchange=()=>{const state=current&&states.get(current);if(state&&!state.payload){state.text=null;window.renderCommandHandoff(current);}};
 for(const id of ['taskText','taskMode','messageApp','messageRecipient','messageBody','messageMode'])el(id).oninput=render;
 el('copyConnector').onclick=async()=>{try{const c=await config;await navigator.clipboard.writeText(c.connector_command);el('queueError').textContent='Connector command copied. Use HeyClicky Settings → Integrations → Advanced → Command on this Mac.';}catch(e){el('queueError').textContent=e.message;}};
 el('copyTaskStarter').onclick=async()=>{try{await navigator.clipboard.writeText('HeyClicky agent: use the SilentOS connector to read general task text from the SilentOS API. Claim one task at a time with silentos_claim_next_command (wait_seconds 20), obey its mode and execution instructions, verify the result, and report it with silentos_report_result. Messaging belongs to Photon; do not send communications. Continue waiting for queued tasks until I stop this job. If the queue is empty, wait and check again; do not invent work. All host permission and confirmation rules apply.');el('queueError').textContent='Task starter copied. Paste it in HeyClicky to start an active worker; SilentOS does not start a HeyClicky job by itself.';}catch(e){el('queueError').textContent=e.message;}};
 window.renderCommandHandoff(command);refresh();setInterval(()=>{if(!document.hidden)refresh();},5000);
})();
