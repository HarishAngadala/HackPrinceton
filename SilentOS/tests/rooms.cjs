const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),Assembly=require('../static/command.js');
const script=fs.readFileSync(__dirname+'/../static/rooms.js','utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(lan){
 const elements={};const el=id=>elements[id]??={value:'',disabled:false,textContent:''};let fail=false,payloads=[];
 const c=new Assembly();c.enqueue();c.accept('hello listener');c.finish();
 const context={command:c,crypto:require('node:crypto'),AbortSignal,location:{port:'8000'},document:{getElementById:el},window:{addEventListener(){}},setInterval:()=>1,clearInterval(){},fetch:async(path,options)=>{
  if(path==='/api/config')return{ok:true,json:async()=>({lan_enabled:lan,session_token:'test'})};
  if(path==='/api/room/create')return{ok:true,json:async()=>({room:'room',speaker_token:'speaker',listener_token:'listener'})};
  if(path==='/api/room/send'){payloads.push(JSON.parse(options.body));if(fail)throw Error('lost response');return{ok:true,json:async()=>({id:1})};}
 }};
 vm.createContext(context);vm.runInContext(script,context);return{context,el,c,payloads,setFail:value=>fail=value};
}
(async()=>{
 const off=setup(false);await flush();assert.equal(off.el('createRoom').disabled,true);assert.match(off.el('roomStatus').textContent,/--lan/);
 const p=setup(true);await flush();await p.el('createRoom').onclick();assert.equal(p.el('sendRoom').disabled,false);
 p.setFail(true);await p.el('sendRoom').onclick();assert.equal(p.c.roomHandoffLocked,true);assert.equal(p.el('commandText').readOnly,true);assert.equal(p.payloads.length,1);
 p.setFail(false);await p.el('sendRoom').onclick();assert.equal(p.payloads.length,2);assert.deepEqual(p.payloads[0],p.payloads[1]);assert.equal(p.el('sendRoom').disabled,true);
 await p.el('sendRoom').onclick();assert.equal(p.payloads.length,2,'already queued caption cannot be submitted again');
 const next=new Assembly();p.context.window.renderRoomHandoff(next);assert.equal(p.el('sendRoom').disabled,true);next.parts=['next'];next.finish();p.context.window.renderRoomHandoff(next);assert.equal(p.el('sendRoom').disabled,false);
 console.log('PASS: LAN configuration, finalized captions, frozen retries, one send per command');
})().catch(e=>{console.error(e);process.exitCode=1});
