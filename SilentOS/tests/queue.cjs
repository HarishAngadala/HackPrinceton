// Deterministic camera/network simulation; no real uploads.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const html=fs.readFileSync(__dirname+'/../static/index.html','utf8');
const elements={};const el=id=>elements[id]??=( {value:id==='duration'?'8000':'',checked:true,dataset:{},prepend(){}} );
let now=0,requests=[],instances=[],cameraOpens=0,trackStops=0;
class Recorder{static isTypeSupported(){return true}constructor(){this.state='inactive';instances.push(this)}start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['video'])});setImmediate(()=>this.onstop())}}
const context={document:{getElementById:el,createElement:()=>({})},performance:{now:()=>now},Blob,AbortSignal,MediaRecorder:Recorder,window:{MediaRecorder:Recorder,addEventListener(){}},navigator:{mediaDevices:{getUserMedia:async()=>{cameraOpens++;return {getTracks:()=>[{stop(){trackStops++}}],getVideoTracks:()=>[{addEventListener(){}}]}}}},setInterval:()=>1,clearInterval(){},fetch:async(path)=>{if(path==='/api/config')return{ok:true,json:async()=>({api_url:'test'})};if(path==='/api/ready')return{ok:true,json:async()=>({model_loaded:true})};return new Promise(resolve=>requests.push(resolve));}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/command.js','utf8'),context);vm.runInContext(html.split('<script>')[1].split('</script>')[0],context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await flush();assert.equal(cameraOpens,1);assert.equal(el('enable').hidden,true);await el('start').onclick();
 // Explicit Finish pauses and Start resumes before the previous upload finishes.
 now+=1000;el('finish').onclick();assert.equal(el('start').disabled,true);await flush();
 assert.equal(instances.at(-1).state,'inactive');assert.equal(el('start').disabled,false);
 await el('start').onclick();assert.equal(instances.at(-1).state,'recording');assert.equal(requests.length,1);
 assert.equal(cameraOpens,1);assert.equal(trackStops,0);
 const finish=async()=>{now+=1000;vm.runInContext('endCapture()',context);assert.equal(el('finish').disabled,true);await flush()};
 await finish();assert.equal(requests.length,1);assert.equal(instances.at(-1).state,'recording');
 await finish();assert.equal(requests.length,1);assert.match(el('queueStatus').textContent,/2\/2 waiting/);assert.match(el('status').textContent,/Catching up/);
 requests[0]({ok:true,json:async()=>({text:'first',audio_used:false})});await flush();assert.equal(requests.length,2);assert.equal(instances.at(-1).state,'recording');
 el('stop').onclick();await flush();assert.equal(instances.at(-1).state,'inactive');
 requests[1]({ok:false,json:async()=>({error:'offline'})});await flush();assert.equal(requests.length,2);assert.match(el('status').textContent,/discarded/);assert.equal(el('start').disabled,true);
 assert.equal(el('start').disabled,true);el('newCommand').onclick();await el('start').onclick();assert.equal(instances.at(-1).state,'recording');assert.equal(cameraOpens,1);assert.equal(trackStops,0);
 // Finish command must wait for the final clip, then isolate the next command.
 now+=1000;el('finishCommand').onclick();await flush();
 assert.equal(el('start').disabled,true);assert.match(el('commandStatus').textContent,/Waiting/);
 requests[2]({ok:true,json:async()=>({text:'Send Alex on WhatsApp',audio_used:false})});await flush();
 assert.match(el('commandStatus').textContent,/Ready for review/);
 assert.equal(el('commandText').value,'Send Alex on WhatsApp');assert.equal(el('commandText').readOnly,false);
 el('commandText').value='Send Sam on WhatsApp hello';el('commandText').oninput();assert.equal(vm.runInContext('command.text',context),'Send Sam on WhatsApp hello');
 el('newCommand').onclick();assert.equal(el('commandText').value,'');assert.equal(el('start').disabled,false);
 assert.equal(el('transcript').value,'first\nSend Alex on WhatsApp');assert.equal(el('caption').textContent,'Send Alex on WhatsApp');assert.equal(el('captionWrap').hidden,false);console.log('PASS: overlap, queue bound, serialized uploads, stop, failure clearing, transcript order, video captions, automatic camera, finish/restart, recovery');
})().catch(e=>{console.error(e);process.exitCode=1});
