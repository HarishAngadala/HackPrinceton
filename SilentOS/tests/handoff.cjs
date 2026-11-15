// Exercise the browser handoff with deferred parsing and lost queue responses.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const Assembly=require('../static/command.js');
const elements={};const el=id=>elements[id]??={value:'',disabled:false,checked:false,textContent:'',children:[],append(x){this.children.push(x)},replaceChildren(){this.replacements=(this.replacements||0)+1;this.children=[]}};
el('messageMode').value='draft';
el('taskProvider').value='heyclicky';
let timer,parseRequests=[],queuePayloads=[],failQueue=false,holdQueue=false,heldQueue;
const first=new Assembly();first.enqueue();first.accept('Send Alex on WhatsApp saying hello');first.finish();
const context={command:first,crypto:require('node:crypto'),AbortSignal,window:{},document:{getElementById:el,hidden:false,createElement:()=>({append(){}})},navigator:{clipboard:{writeText:async()=>{}}},setTimeout:fn=>(timer=fn,1),clearTimeout:()=>{timer=null},setInterval(){},fetch:async(path,options)=>{
 if(path==='/api/config')return{ok:true,json:async()=>({session_token:'test',connector_command:'python3 test.py',photon:{configured:false},companion:{configured:false}})};
 if(path==='/api/companion/messages')return{ok:true,json:async()=>({messages:[],worker:{worker_active:false,worker_photon_enabled:false}})};
 if(path==='/api/tasks/parse')return new Promise(resolve=>parseRequests.push(resolve));
 if(path==='/api/commands'&&options.method==='POST'){
  queuePayloads.push(JSON.parse(options.body));if(holdQueue)return new Promise(resolve=>heldQueue=resolve);if(failQueue)throw new Error('lost response');
  return{ok:true,json:async()=>({mode:'draft',recipient:'Alex'})};
 }
 return{ok:true,json:async()=>({commands:[]})};
}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/handoff.js','utf8'),context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const parsed=()=>({ok:true,json:async()=>({parsed:true,kind:'message',provider:'photon',app:'whatsapp',recipient:'Alex',message:'hello',reason:'Review'})});
(async()=>{
 timer();await flush();const replacements=el('commandQueue').replacements;await el('refreshCommands').onclick();assert.equal(el('commandQueue').replacements,replacements,'unchanged queue keeps its DOM');assert.equal(parseRequests.length,1);assert.equal(el('queueCommand').disabled,true);
 parseRequests[0](parsed());await flush();assert.equal(el('queueCommand').disabled,false);assert.equal(el('messageBody').value,'hello');
 failQueue=true;await el('queueCommand').onclick();assert.equal(queuePayloads.length,1);assert.equal(el('messageBody').disabled,true);assert.equal(first.handoffLocked,true);
 failQueue=false;await el('queueCommand').onclick();assert.equal(queuePayloads.length,2);assert.deepEqual(queuePayloads[0],queuePayloads[1]);assert.equal(el('queueCommand').disabled,true);
 context.window.renderCommandHandoff(first);assert.equal(queuePayloads.length,2);
 const second=new Assembly();second.enqueue();second.accept('Send Sam on SMS saying later');second.finish();
 context.window.renderCommandHandoff(second);timer();await flush();assert.equal(parseRequests.length,2);
 const third=new Assembly();context.window.renderCommandHandoff(third);
 parseRequests[1](parsed());await flush();assert.equal(el('messageBody').value,'');assert.equal(el('queueCommand').disabled,true);
 // Explicit opt-in queues only successfully parsed completed commands, once.
 el('autoQueue').checked=true;
 const fourth=new Assembly();fourth.enqueue();fourth.accept('Send Alex on WhatsApp saying hello');fourth.finish();
 context.window.renderCommandHandoff(fourth);timer();await flush();parseRequests[2](parsed());await flush();
 assert.equal(queuePayloads.length,3);assert.equal(queuePayloads[2].mode,'draft');
 context.window.renderCommandHandoff(fourth);assert.equal(queuePayloads.length,3);
 // Failed reparsing must not offer an old recipient/body for a new transcript.
 el('autoQueue').checked=false;
 const fifth=new Assembly();fifth.parts=['another command'];fifth.finish();
 context.window.renderCommandHandoff(fifth);timer();await flush();assert.equal(el('messageRecipient').value,'');assert.equal(el('messageBody').value,'');
 parseRequests[3]({ok:false,json:async()=>({error:'parser offline'})});await flush();assert.equal(el('queueCommand').disabled,true);assert.equal(el('messageBody').value,'');
 // Completing an older failed submit cannot lock a different command's fields.
 el('taskText').value='Open Downloads';el('taskMode').value='execute';el('taskText').oninput();holdQueue=true;
 const oldSubmit=el('queueCommand').onclick();await flush();
 const sixth=new Assembly();sixth.parts=['new command'];sixth.finish();context.window.renderCommandHandoff(sixth);timer();await flush();parseRequests[4](parsed());await flush();
 heldQueue({ok:false,json:async()=>({error:'offline'})});await oldSubmit;assert.equal(el('messageBody').disabled,false,'old cleanup must not lock the replacement command');
 const general=new Assembly();general.parts=['Open Downloads'];general.finish();context.window.renderCommandHandoff(general);timer();await flush();parseRequests[5]({ok:true,json:async()=>({parsed:true,kind:'task',provider:'heyclicky',task:'Open Downloads',reason:'General task'})});await flush();
 assert.equal(el('taskFields').hidden,false);assert.equal(el('messageFields').hidden,true);assert.equal(el('taskText').value,'Open Downloads');
 holdQueue=false;await el('queueCommand').onclick();assert.equal(queuePayloads.at(-1).kind,'task');assert.equal(queuePayloads.at(-1).task,'Open Downloads');
 assert.equal(queuePayloads.at(-1).provider,'heyclicky','HeyClicky remains the default task provider');
 const deep=new Assembly();deep.parts=['Summarize the recent queue'];deep.finish();context.window.renderCommandHandoff(deep);timer();await flush();parseRequests[6]({ok:true,json:async()=>({parsed:true,kind:'task',provider:'heyclicky',task:'Summarize the recent queue',reason:'General task'})});await flush();
 assert.equal(el('taskProvider').value,'heyclicky','each new command starts on the existing provider');
 el('taskProvider').value='deepagent';el('taskProvider').oninput();await el('queueCommand').onclick();assert.equal(queuePayloads.at(-1).provider,'deepagent');assert.equal(queuePayloads.at(-1).task,'Summarize the recent queue');
 console.log('PASS: review fields, lost-response idempotency, frozen payload, stale parse rejection, opt-in auto queue, explicit provider selection');
})().catch(e=>{console.error(e);process.exitCode=1});
