import {test} from 'node:test';import assert from 'node:assert/strict';import {calculate,breakdown} from '../dist/calculate.mjs';
test('1000 labels at 6 by 8 prints 21 whole sheets',()=>{const r=calculate(1000,6,8);assert.deepEqual([r.capacity,r.sheets,r.fullSheets,r.fullRows,r.extraLabels,r.produced,r.surplus],[48,21,20,6,4,1008,8]);assert.equal(breakdown(r),'20张整纸＋6行4枚');});
test('one extra label rounds up to another sheet',()=>{const r=calculate(481,6,8);assert.equal(r.sheets,11);assert.equal(r.remainder,1);assert.equal(r.produced,528);});
test('exact sheets have no extra paper',()=>{const r=calculate(476,7,34);assert.equal(r.sheets,2);assert.equal(r.surplus,0);assert.equal(breakdown(r),'2张整纸，刚好够用');});
test('less than a page and exact whole rows are readable',()=>{assert.equal(breakdown(calculate(14,7,34)),'2行');assert.equal(breakdown(calculate(3,7,34)),'3枚');assert.equal(calculate(1000,7,34).surplus,190);});
test('reject invalid quantities and capacities without stale results',()=>{for(const q of [0,-1,1.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1])assert.throws(()=>calculate(q,7,34));assert.throws(()=>calculate(1,0,34));});
