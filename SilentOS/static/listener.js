// Keep invitations in this tab's session so reloading does not disconnect it.
(()=>{
 const $=id=>document.getElementById(id),storageKey='silentos-listener:'+location.pathname;
 let credentials=null;
 const fragment=location.hash.slice(1),parts=fragment.split('.');
 function valid(value){return value&&typeof value.room==='string'&&typeof value.token==='string'&&[value.room,value.token].every(v=>/^[A-Za-z0-9_-]{1,128}$/.test(v));}
 if(fragment){
  const candidate={room:parts[0],token:parts[1]};
  if(parts.length===2&&valid(candidate)){
   credentials=candidate;
   try{sessionStorage.setItem(storageKey,JSON.stringify(candidate));history.replaceState(null,'',location.pathname);}catch{} // With storage blocked, keep the fragment for reload.
  }
 }else{try{const saved=JSON.parse(sessionStorage.getItem(storageKey));if(valid(saved))credentials=saved;}catch{}}
 let cursor=0,enabled=false,polling=Boolean(credentials),ack=0,timer;
 function say(text){if(!enabled||!('speechSynthesis' in window))return;const utterance=new SpeechSynthesisUtterance(text);utterance.onerror=()=>{$('status').textContent='Voice playback failed. Captions remain available.';};speechSynthesis.speak(utterance);}
 $('enable').onclick=()=>{if(!('speechSynthesis' in window)){$('status').textContent='Speech synthesis unavailable. Captions remain available.';return;}enabled=true;speechSynthesis.resume();say('Voice enabled');$('status').textContent='Voice enabled. Waiting for captions.';};
 $('test').onclick=()=>{if(!enabled){$('status').textContent='Tap Enable voice first.';return;}say('SilentOS voice test');};
 async function tick(){
  if(!polling)return;const {room,token}=credentials;
  try{
   const res=await fetch(`/api/room/poll?room=${encodeURIComponent(room)}&role=listener&after=${cursor}`,{headers:{Authorization:`Bearer ${token}`},cache:'no-store',signal:AbortSignal.timeout(10000)});
   const data=await res.json();if(!res.ok){polling=false;throw Error(data.error||'Room unavailable');}
   if(!Array.isArray(data.messages))throw Error('Invalid caption response');
   for(const msg of data.messages){
    if(!Number.isInteger(msg.id)||typeof msg.text!=='string')throw Error('Invalid caption');
    if(msg.id<=cursor)continue;const li=document.createElement('li');li.textContent=msg.text;$('messages').append(li);cursor=msg.id;say(msg.text);
   }
   if(cursor>ack){const response=await fetch('/api/room/ack',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({room,token,id:cursor}),signal:AbortSignal.timeout(10000)});if(!response.ok)throw Error('Caption receipt failed');ack=cursor;}
   $('status').textContent=enabled?'Connected · Voice enabled':'Connected · Tap Enable voice. Messages received before enabling voice will appear as text only.';
  }catch(e){$('status').textContent=`Connection problem: ${e.message}`;}
  if(polling)timer=setTimeout(tick,1500);
 }
 window.addEventListener('pagehide',()=>{polling=false;clearTimeout(timer);if('speechSynthesis' in window)speechSynthesis.cancel();});
 if(!credentials)$('status').textContent='Invalid invitation. Ask the speaker for a new link.';else tick();
})();
