const assert=require('node:assert/strict');
const Command=require('../static/command.js');
const c=new Command();
c.enqueue();c.enqueue();c.accept(' Send Alex on WhatsApp ');
assert.equal(c.state,'draft');c.finish();assert.equal(c.state,'waiting');
assert.throws(()=>c.enqueue(),/closed/);
c.accept("I'll be there in ten minutes.");
assert.equal(c.state,'ready');assert.equal(c.text,"Send Alex on WhatsApp I'll be there in ten minutes.");
c.finish();assert.equal(c.state,'ready');
const empty=new Command();empty.finish();assert.equal(empty.state,'empty');
const failed=new Command();failed.enqueue();failed.enqueue();failed.accept('Send Alex');failed.fail('offline');failed.finish();assert.equal(failed.state,'incomplete');
const invalid=new Command();invalid.enqueue();invalid.accept(' ');invalid.finish();assert.equal(invalid.state,'incomplete');
const cancelled=new Command();cancelled.enqueue();cancelled.cancel();cancelled.accept('late result');assert.equal(cancelled.text,'');assert.equal(cancelled.state,'cancelled');
// Preserve repetitions and punctuation: do not guess at overlap or missing words.
const repeat=new Command();repeat.enqueue();repeat.accept('very');repeat.enqueue();repeat.accept('very good.');repeat.finish();assert.equal(repeat.text,'very very good.');
console.log('PASS: command boundaries, pending clips, empty/failed/cancelled commands, exact phrase order');
