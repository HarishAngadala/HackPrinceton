// Reviewed captions only. The request key prevents duplicate delivery on retries.
(()=>{
 const el=id=>document.getElementById(id),states=new WeakMap();
 let session=null,pollTimer,polling=false,creating=false,sending=false,lan=false,current=command;
 const config=fetch('/api/config',{signal:AbortSignal.timeout(15000)}).then(async r=>{if(!r.ok)throw Error('Cannot read room configuration');return r.json();});
 async function post(path,data){
  const c=await config;
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-SilentOS-Token':c.session_token},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)});
  const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);return result;
 }
 function stateFor(source){let state=states.get(source);if(!state||state.room!==session?.room){state={room:session?.room,payload:null,sent:false};states.set(source,state);}return state;}
 window.renderRoomHandoff=source=>{
  current=source;const state=stateFor(source);
  el('createRoom').disabled=!lan||creating||sending;
  el('copyRoom').disabled=!session||creating;
  el('sendRoom').disabled=!session||creating||sending||source.state!=='ready'||state.sent;
  el('sendRoom').textContent=state.sent?'Caption queued':sending?'Sending…':state.payload?'Retry same caption':'Send reviewed command to listener';
 };
 async function poll(){
  if(!session||polling)return;const selected=session;polling=true;
  try{
   const response=await fetch(`/api/room/poll?room=${encodeURIComponent(selected.room)}&role=speaker`,{headers:{Authorization:`Bearer ${selected.speaker_token}`},signal:AbortSignal.timeout(8000)});
   const result=await response.json();if(session!==selected)return;
   if(!response.ok){clearInterval(pollTimer);session=null;throw Error(result.error||'Room unavailable');}
   el('roomStatus').textContent=`${result.listener_connected?'Listener connected':'Waiting for listener'} · received through message ${result.received_through}`;
  }catch(e){if(session===selected||!session)el('roomStatus').textContent=`Room connection problem: ${e.message}`;}
  finally{polling=false;window.renderRoomHandoff(current);}
 }
 function invitation(){
  const host=el('roomHost').value.trim();
  if(!session||!/^([a-zA-Z0-9.-]+)$/.test(host))throw Error('Create a room and enter the LAN IP or hostname.');
  return `http://${host}:${location.port||'80'}/listen#${session.room}.${session.listener_token}`;
 }
 el('createRoom').onclick=async()=>{
  if(el('createRoom').disabled)return;creating=true;window.renderRoomHandoff(current);
  try{session=await post('/api/room/create',{});clearInterval(pollTimer);el('roomLink').textContent='';el('roomReceipt').textContent='';el('roomStatus').textContent='Room created. Enter your LAN IP and share the link.';pollTimer=setInterval(poll,2000);}
  catch(e){el('roomStatus').textContent=e.message;}
  finally{creating=false;window.renderRoomHandoff(current);}
 };
 el('copyRoom').onclick=async()=>{try{const link=invitation();el('roomLink').textContent=link;await navigator.clipboard.writeText(link);el('roomReceipt').textContent='Listener link copied. Share it privately.';}catch(e){el('roomReceipt').textContent=e.message+' If the link is shown above, copy it manually.';}};
 el('sendRoom').onclick=async()=>{
  if(el('sendRoom').disabled)return;const source=current,selected=session,state=stateFor(source);
  if(!source.text.trim()||source.text.length>2000){el('roomReceipt').textContent='Room captions must contain 1–2000 characters.';return;}
  state.payload??={room:selected.room,token:selected.speaker_token,text:source.text,request_key:crypto.randomUUID()};
  source.roomHandoffLocked=true;el('commandText').readOnly=true;sending=true;window.renderRoomHandoff(source);
  try{const result=await post('/api/room/send',state.payload);state.sent=true;if(session===selected)el('roomReceipt').textContent=`Message ${result.id} queued; waiting for listener receipt.`;}
  catch(e){if(session===selected)el('roomReceipt').textContent=e.message+' Retry uses the same caption; use New command to change it.';}
  finally{sending=false;window.renderRoomHandoff(current);}
 };
 config.then(c=>{lan=c.lan_enabled===true;el('roomStatus').textContent=lan?'Room not created.':'LAN sharing is off. To use a second device, restart with python3 server.py --lan, then reload.';window.renderRoomHandoff(current);}).catch(e=>{el('roomStatus').textContent=e.message;});
 window.addEventListener('pagehide',()=>{clearInterval(pollTimer);session=null;});
 window.renderRoomHandoff(current);
})();
