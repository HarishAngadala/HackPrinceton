const vm=require('node:vm'),fs=require('node:fs');
module.exports=function camera(){
 const elements={};const el=id=>elements[id]??={value:id==='duration'?'8000':'',checked:true,dataset:{},prepend(){}};
 const recorders=[],trackEvents={};let readyReply=async()=>({model_loaded:true});
 class Recorder{static isTypeSupported(){return true}constructor(){this.state='inactive';recorders.push(this)}start(){this.state='recording'}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['video'])});setImmediate(()=>this.onstop())}}
 const context={document:{getElementById:el,createElement:()=>({})},performance:{now:()=>1000},Blob,AbortSignal,MediaRecorder:Recorder,window:{MediaRecorder:Recorder,addEventListener(){}},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){}}],getVideoTracks:()=>[{addEventListener:(name,fn)=>trackEvents[name]=fn}]})}},setInterval:()=>1,clearInterval(){},fetch:async path=>({ok:true,json:path==='/api/ready'?()=>readyReply():async()=>({api_url:'test'})})};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../../static/command.js','utf8'),context);
 vm.runInContext(fs.readFileSync(__dirname+'/../../static/index.html','utf8').split('<script>')[1].split('</script>')[0],context);
 return{el,recorders,trackEvents,run:code=>vm.runInContext(code,context),setReady:fn=>readyReply=fn};
};
