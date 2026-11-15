import assert from 'node:assert/strict';
import {checkReady,transcribeVideo} from '../flare.mjs';
let payload=null,calls=0;
globalThis.fetch=async()=>{calls++;return{ok:true,status:200,text:async()=>JSON.stringify(payload)}};
for(const value of [null,[],42,'invalid']){payload=value;await assert.rejects(checkReady(),/JSON object/);}
payload={model_loaded:true};assert.equal((await checkReady()).model_loaded,true);
const huge=new Blob([new Uint8Array(50*1024*1024+1)],{type:'video/webm'});const before=calls;
await assert.rejects(transcribeVideo(huge),/50 MiB/);assert.equal(calls,before,'oversize video must not be uploaded');
payload={text:'hello',audio_used:true};await assert.rejects(transcribeVideo(new Blob(['video'],{type:'video/webm'})),/visual-only/);
payload={text:'hello',audio_used:false};assert.equal((await transcribeVideo(new Blob(['video'],{type:'video/webm'}))).text,'hello');
console.log('PASS: FLARE JSON validation, size limit before upload, visual-only transcript checks');
