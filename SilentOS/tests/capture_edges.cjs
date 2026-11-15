const assert=require('node:assert/strict'),camera=require('./helpers/camera.cjs');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const c=camera();await flush();c.el('commandText').value='Send Alex on iMessage saying hello';c.el('commandText').oninput();
 c.run('ready=false');let resolveReady;c.setReady(()=>new Promise(resolve=>resolveReady=resolve));
 const start=c.el('start').onclick();await flush();c.el('finishCommand').onclick();assert.equal(c.run('command.state'),'ready');
 resolveReady({model_loaded:true});await start;assert.equal(c.recorders.length,0,'late readiness must not start recording after Finish command');
 c.trackEvents.ended();assert.equal(c.run('command.state'),'ready','idle camera disconnect must preserve a completed command');
 const next=camera();await flush();next.run('ready=false');let resolveNext;next.setReady(()=>new Promise(resolve=>resolveNext=resolve));const pending=next.el('start').onclick();await flush();next.el('newCommand').onclick();resolveNext({model_loaded:true});await pending;assert.equal(next.recorders.length,0,'late readiness must not record into a replacement command');
 c.el('transcript').value='old\nOpen Downloads';c.el('transcript').selectionStart=4;c.el('transcript').selectionEnd=18;c.el('transcript').oninput();assert.equal(c.el('useTranscript').disabled,false);c.el('useTranscript').onclick();assert.equal(c.run('command.text'),'Open Downloads');assert.equal(c.run('command.state'),'ready');
 console.log('PASS: readiness/finish race, readiness/new-command race, completed command survives idle camera loss');
})().catch(e=>{console.error(e);process.exitCode=1});
