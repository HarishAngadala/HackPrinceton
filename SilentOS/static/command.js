// A command ends only on an explicit user action, never at a clip boundary.
(function(root){
 class CommandAssembly {
  constructor(){this.parts=[];this.pending=0;this.sealed=false;this.error='';this.cancelled=false;}
  get text(){return this.parts.join(' ');}
  get state(){return this.cancelled?'cancelled':this.error?'incomplete':!this.sealed?'draft':this.pending?'waiting':this.text?'ready':'empty';}
  enqueue(){if(this.sealed||this.cancelled)throw new Error('Command is closed');this.pending++;}
  accept(text){if(this.cancelled)return;if(!this.pending)throw new Error('No pending clip');this.pending--;if(typeof text!=='string'||!text.trim()){this.fail('Empty transcript');return;}this.parts.push(text.trim());}
  finish(){this.sealed=true;}
  fail(reason){if(!this.cancelled)this.error=reason;}
  cancel(){this.cancelled=true;}
 }
 root.CommandAssembly=CommandAssembly;
 if(typeof module!=='undefined')module.exports=CommandAssembly;
})(globalThis);
