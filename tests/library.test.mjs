import {test} from 'node:test';
import assert from 'node:assert/strict';
import {filterLibrary,restoreView,inferGrid,productOf} from '../dist/library.mjs';
const records=[{id:'normal',name:'Mini ROTH 0.022 345Hooks',product:'普通托槽',group:'小黑盒 · v2'},{id:'self',name:'MBT 0.022 NoHooks',product:'自锁托槽',group:'28孔蓝盒'},{id:'custom',name:'我自己的标签',custom:true}];
test('product and packaging filters preserve distinct styles',()=>{assert.deepEqual(filterLibrary(records,{product:'普通托槽',group:'小黑盒 · v2'}).map(r=>r.id),['normal']);assert.equal(filterLibrary(records,{product:'自锁托槽',group:'小黑盒 · v2'}).length,0);assert.equal(productOf(records[2]),'我的标签');});
test('search accepts Chinese hooks, English spelling and unordered terms',()=>{assert.equal(filterLibrary(records,{query:'345钩 roth 迷你'})[0].id,'normal');assert.equal(filterLibrary(records,{query:'无钩 MBT'})[0].id,'self');});
test('infer grids in old joined and new split footers, reject mismatch',()=>{assert.deepEqual(inferGrid('共 40 张 5 列 × 8 行'),{cols:5,rows:8});assert.deepEqual(inferGrid('共65张｜13列×5行'),{cols:13,rows:5});assert.deepEqual(inferGrid('5列 × 9行 共45枚'),{cols:5,rows:9});assert.equal(inferGrid('共40张 5列×9行'),null);assert.equal(inferGrid('样稿 30张'),null);});
test('view restore ignores malformed and invalid persisted values',()=>{assert.equal(restoreView('bad').quantity,1000);assert.equal(restoreView('{"quantity":-2}').quantity,1000);assert.equal(restoreView('{"id":"self","quantity":451,"product":"自锁托槽"}').quantity,451);});
