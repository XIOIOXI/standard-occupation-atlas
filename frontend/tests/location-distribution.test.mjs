import test from 'node:test';
import assert from 'node:assert/strict';
import { getLocationDistribution, filterRecordsByProvince } from '../src/lib/locationDistribution.js';

test('derives regional location mentions from retained record locations without changing record counts', () => {
  const result = getLocationDistribution([
    { location: '北京, 上海, 深圳' },
    { location: '成都, 西安' },
    { location: '全国多地' },
  ]);
  const count = name => result.provinces.find(province => province.name === name).value;
  assert.equal(result.identifiableRecords, 2);
  assert.equal(count('北京'), 1);
  assert.equal(count('上海'), 1);
  assert.equal(count('广东'), 1);
  assert.equal(count('四川'), 1);
  assert.equal(count('陕西'), 1);
});

test('province selection uses the same location evidence as map counts and keeps source rows intact', () => {
  const records = [{ location: '北京, 上海, 深圳' }, { location: '广州、深圳' }, { location: '成都' }, { location: '全国多地' }, {}];
  assert.equal(filterRecordsByProvince(records, ''), records);
  for (const province of getLocationDistribution(records).provinces) {
    assert.equal(filterRecordsByProvince(records, province.name).length, province.value);
  }
  assert.deepEqual(filterRecordsByProvince(records, '广东'), records.slice(0, 2));
  assert.deepEqual(filterRecordsByProvince(records, '北京'), [records[0]]);
  assert.deepEqual(filterRecordsByProvince(records, '天津'), []);
  assert.deepEqual(filterRecordsByProvince(records, '未知'), []);
  assert.equal(records[0].location, '北京, 上海, 深圳');
});
