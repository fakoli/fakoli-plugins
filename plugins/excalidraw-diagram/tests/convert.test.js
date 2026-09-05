const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { convert } = require('../scripts/convert.js');
const shape = (id, extra = {}) => ({ type: 'rectangle', id, label: id, ...extra });

test('stable IDs, reciprocal arrow bindings and labels survive edits', () => {
  const original = convert({ elements: [shape('api'), shape('db'), {type:'arrow',id:'query',from:'api',to:'db'}] });
  original.files = {photo: {dataURL:'data:image/png;base64,fixture'}};
  original.appState.viewBackgroundColor = '#fdfdfd';
  original.custom = {preserve: true};
  const before = structuredClone(original);
  const next = convert({elements:[shape('cache',{x:800,y:50}),{type:'arrow',id:'fallback',from:'cache',to:'db'}]}, original);
  assert.deepEqual(original, before);
  assert.deepEqual(next.files, before.files);
  assert.deepEqual(next.custom, before.custom);
  assert.equal(next.appState.viewBackgroundColor, '#fdfdfd');
  assert.equal(next.elements.find(e=>e.id==='fallback').endBinding.elementId,'db');
  assert(next.elements.find(e=>e.id==='db').boundElements.some(e=>e.id==='fallback'));
});

test('invalid skeletons and unresolved edit references fail before output', () => {
  const original = convert({elements:[shape('api')]});
  for (const elements of [[null],[shape('x'),shape('x')],[{type:'bogus',id:'x'}],[shape('x',{width:-1})],
    [{type:'arrow',from:'missing',to:'api'}],[{type:'line',points:[[0,1]]}],[{type:'arrow',from:'api'}]]) {
    assert.throws(()=>convert({elements},original), /validation/);
  }
  assert.throws(()=>convert({elements:[],remove:['missing']},original));
});

test('frames auto-size and frame removal detaches children', () => {
  const scene = convert({elements:[shape('a',{x:100,y:100,width:200,height:80}),{type:'frame',id:'group',children:['a']}]});
  const frame=scene.elements.find(e=>e.id==='group');
  assert(frame.x<100 && frame.y<100 && frame.width>200 && frame.height>80);
  assert(scene.elements.filter(e=>e.id==='a'||e.containerId==='a').every(e=>e.frameId==='group'));
  const next=convert({elements:[],remove:['group']},scene);
  assert(next.elements.every(e=>e.frameId===null));
});

test('removing a shape cleans text and reciprocal bindings', () => {
  const scene=convert({elements:[shape('a'),shape('b'),{type:'arrow',id:'ab',from:'a',to:'b',label:'connect'}]});
  const next=convert({elements:[],remove:['a','ab']},scene);
  assert(next.elements.every(e=>e.id!=='a' && e.id!=='ab' && e.containerId!=='a' && e.containerId!=='ab'));
  assert(!next.elements.find(e=>e.id==='b').boundElements.some(e=>e.id==='ab'));
});

test('explicit zero and mixed coordinates remain positioned; leftward labels use signed midpoint', () => {
  const scene=convert({elements:[shape('a',{x:400,y:0}),shape('b',{x:0,y:0}),shape('c'),
    {type:'arrow',id:'back',from:'a',to:'b',label:'back'},{type:'line',id:'line',x:0,y:0,points:[[10,20],[30,40]]}]});
  assert.equal(scene.elements.find(e=>e.id==='a').x,400);
  assert.equal(scene.elements.find(e=>e.id==='line').x,0);
  const text=scene.elements.find(e=>e.containerId==='back');
  assert(text.x>200 && text.x<400);
});

test('empty scene has finite viewport and ordered valid fractional indices', () => {
  assert.equal(convert({elements:[]}).appState.scrollX,100);
  const scene=convert({elements:Array.from({length:100},(_,i)=>shape(`node-${i}`))});
  const indices=scene.elements.map(e=>e.index);
  assert.deepEqual(indices,[...indices].sort());
  assert.equal(new Set(indices).size,indices.length);
  assert(indices.every(i=>/^b[0-9A-Za-z]{2}$/.test(i)));
});

test('CLI creates a scene and a failed in-place modification preserves bytes', () => {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'excalidraw-test-'));
  try {
    const cli=path.resolve(__dirname,'../scripts/convert.js');
    const output=path.join(dir,'diagram.excalidraw');
    let result=spawnSync(process.execPath,[cli,'--stdin',output],{input:JSON.stringify({elements:[shape('a')]}),encoding:'utf8'});
    assert.equal(result.status,0,result.stderr);
    const before=fs.readFileSync(output,'utf8');
    const input=path.join(dir,'bad.json');fs.writeFileSync(input,'{"elements":[null]}');
    result=spawnSync(process.execPath,[cli,'--modify',output,input],{encoding:'utf8'});
    assert.equal(result.status,1);
    assert.equal(fs.readFileSync(output,'utf8'),before);
  } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});
