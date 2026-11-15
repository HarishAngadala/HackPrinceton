const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const script=fs.readFileSync(__dirname+'/../static/listener.js','utf8');
const store=new Map();let reads=0,acks=0;
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function page(hash,storageBlocked=false){
 const elements={};const el=id=>elements[id]??={textContent:'',children:[],append(node){this.children.push(node)}};
 const location={hash,pathname:'/listen'},events={};let nextTick;
 const context={location,sessionStorage:{getItem:key=>store.get(key)??null,setItem:(key,v)=>{if(storageBlocked)throw Error('blocked');store.set(key,v)}},history:{replaceState(){location.hash=''}},document:{getElementById:el,createElement:()=>({})},window:{addEventListener:(name,fn)=>events[name]=fn},AbortSignal,setTimeout:fn=>(nextTick=fn,1),clearTimeout(){},fetch:async path=>{
  if(path==='/api/room/ack'){acks++;return {ok:true};}
  reads++;return{ok:true,json:async()=>({messages:[{id:1,text:'hello'}]})};
 }};
 vm.createContext(context);vm.runInContext(script,context);return{el,location,events,tick:()=>nextTick?.()};
}
(async()=>{
 const first=page('#room.token');await flush();assert.equal(first.el('messages').children[0].textContent,'hello');assert.equal(first.location.hash,'');assert.equal(acks,1);
 const reloaded=page('');await flush();assert.equal(reloaded.el('messages').children.length,1);assert.match(reloaded.el('status').textContent,/Connected/);
 reloaded.tick();await flush();assert.equal(reloaded.el('messages').children.length,1,'repeated poll must not duplicate captions');
 const blocked=page('#room.other-token',true);await flush();assert.equal(blocked.location.hash,'#room.other-token','blocked storage must preserve invitation');
 const invalid=page('#invalid');await flush();assert.match(invalid.el('status').textContent,/Invalid invitation/);
 const before=reads;first.events.pagehide();first.tick();await flush();assert.equal(reads,before,'page close stops polling');
 console.log('PASS: listener reload, invitation fallback, caption deduplication, invalid links, cleanup');
})().catch(e=>{console.error(e);process.exitCode=1});
