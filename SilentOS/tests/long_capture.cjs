// Deterministic camera/network simulation; no real uploads.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const html=fs.readFileSync(__dirname+'/../static/index.html','utf8');
assert.match(html, /<option value="8000" selected>8 sec<\/option>/);
const elements={};const el=id=>elements[id]??=( {value:id==='duration'?'60000':'',checked:false,dataset:{},prepend(){}} );
let tick;let now=0,requests=[],instances=[],cameraOpens=0,trackStops=0;
class Recorder{static isTypeSupported(){return true}constructor(){this.state='inactive';instances.push(this)}start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['video'])});setImmediate(()=>this.onstop())}}
const context={document:{getElementById:el,createElement:()=>({})},performance:{now:()=>now},Blob,AbortSignal,MediaRecorder:Recorder,window:{MediaRecorder:Recorder,addEventListener(){}},navigator:{mediaDevices:{getUserMedia:async()=>{cameraOpens++;return {getTracks:()=>[{stop(){trackStops++}}],getVideoTracks:()=>[{addEventListener(){}}]}}}},setInterval:fn=>{tick=fn;return 1},clearInterval(){},fetch:async(path)=>{if(path==='/api/config')return{ok:true,json:async()=>({api_url:'test'})};if(path==='/api/ready')return{ok:true,json:async()=>({model_loaded:true})};return new Promise(resolve=>requests.push(resolve));}};
vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../static/command.js','utf8'),context);vm.runInContext(html.split('<script>')[1].split('</script>')[0],context);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 await flush(); await el('start').onclick();
 let count=0;
 while(instances.at(-1).state==='recording'){
  const began=now;
  while(instances.at(-1).state==='recording'){now+=50;tick();}
  assert.ok(now-began>=59800&&now-began<=60000,'full clip reaches sixty seconds');
  await flush();
  const resolve=requests[count++];assert.ok(resolve);
  resolve({ok:true,json:async()=>({text:`part ${count}`,audio_used:false})});await flush();
  assert.ok(count===1,'60-second input produces one request');
 }
 assert.equal(count,1);assert.ok(now>=59500&&now<=60000);assert.equal(el('start').disabled,false);
 assert.equal(el('transcript').value.split('\n').length,1);
 await el('start').onclick();assert.equal(instances.at(-1).state,'recording');
 console.log('PASS: 60-second take, single upload, full transcript, automatic stop and restart');
})().catch(e=>{console.error(e);process.exitCode=1});
