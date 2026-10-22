import test from 'node:test';
import assert from 'node:assert/strict';
import { readBrowseState, writeBrowseState } from '../src/lib/browseStorage.js';
test('restores scoped browsing state and falls back for malformed or invalid values', () => {
  const values = new Map();
  const storage = { getItem:key => values.get(key) ?? null, setItem:(key,value) => values.set(key,value) };
  writeBrowseState('page', 'daily', storage);
  assert.equal(readBrowseState('page', 'atlas', value => ['daily','atlas'].includes(value), storage), 'daily');
  assert.equal(readBrowseState('other', 'atlas', undefined, storage), 'atlas');
  writeBrowseState('page', { broken:true }, storage);
  assert.equal(readBrowseState('page', 'atlas', value => typeof value === 'string', storage), 'atlas');
  storage.setItem('job-workbench:browse:v1:page', '{');
  assert.equal(readBrowseState('page', 'atlas', undefined, storage), 'atlas');
});
test('blocked or exhausted storage does not break browsing', () => {
  const storage = { getItem:() => { throw Error(); }, setItem:() => { throw Error(); } };
  assert.equal(readBrowseState('page', 'atlas', undefined, storage), 'atlas');
  assert.doesNotThrow(() => writeBrowseState('page', 'daily', storage));
});
