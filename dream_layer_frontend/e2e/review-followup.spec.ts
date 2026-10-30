import { test, expect } from '@playwright/test';
import path from 'node:path';
import { writeFileSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { api, artifactPath } from './artifacts';

test('true pre-fix bundle: preserve on resume, warn, explicitly upgrade and supersede', async ({page,request}) => {
  const original=path.resolve('../tests/fixtures/legacy-browser-v1.zip');
  const hash=()=>createHash('sha256').update(readFileSync(original)).digest('hex');
  const beforeHash=hash();
  expect(beforeHash).toBe('584a1774f820e7325d0c5cd54d570bed38de5b48ea0250093e86d87d624274cf');
  await page.goto('/research');
  await page.getByLabel('Reload bundle').setInputFiles(original);
  await expect(page.getByRole('status')).toContainText('Bundle verified and imported');
  const eid=await page.getByLabel('Experiment',{exact:true}).inputValue();
  expect(eid).toBe('e7202f48-f94f-49d2-b32b-e2ee630561ea');
  const detail=async()=>await (await request.get(`${api}/api/research/experiments/${eid}`)).json();
  const before=await detail();
  const beforeAnalysis=await (await request.get(`${api}/api/research/experiments/${eid}/analysis`)).json();
  const count=(records:{kind:string}[],kind:string)=>records.filter(r=>r.kind===kind).length;
  await page.getByRole('button',{name:'Run / resume',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('resume preserves existing results');
  await expect(page.getByTestId('job-state')).toContainText('complete');
  const resumed=await detail();
  expect(count(resumed.records,'result')).toBe(count(before.records,'result'));
  expect(count(resumed.records,'judge_call')).toBe(count(before.records,'judge_call'));
  expect(await (await request.get(`${api}/api/research/experiments/${eid}/analysis`)).json()).toEqual(beforeAnalysis);
  await page.getByLabel('Upgrade evaluators',{exact:true}).check();
  await page.getByRole('button',{name:'Run / resume',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('explicit upgrade will re-evaluate');
  await expect.poll(async()=>count((await detail()).records,'result')).toBe(count(before.records,'result')+6);
  await page.getByRole('button',{name:'Analyze',exact:true}).click();
  await expect(page.getByTestId('analysis-report')).toContainText('"superseded_evaluations": 6');
  const upgraded=await detail();
  const oldResults=before.records.filter((r:{kind:string})=>r.kind==='result');
  for(const old of oldResults) expect(upgraded.records.find((r:{id:string})=>r.id===old.id)).toEqual(old);
  expect(count(upgraded.records,'judge_call')).toBe(count(before.records,'judge_call'));
  const downloadEvent=page.waitForEvent('download');await page.getByRole('link',{name:'Export experiment',exact:true}).click();
  await (await downloadEvent).saveAs(artifactPath('legacy-upgrade','upgraded-experiment.zip'));
  const output={experiment_id:eid,original_bundle_sha256:beforeHash,plain_resume_added_results:0,
    upgrade_added_results:6,upgrade_superseded_results:6,additional_judge_calls:0,
    analysis:await (await request.get(`${api}/api/research/experiments/${eid}/analysis`)).json()};
  writeFileSync(artifactPath('legacy-upgrade','result.json'),JSON.stringify(output,null,2));
  await page.screenshot({path:artifactPath('legacy-upgrade','workbench.png'),fullPage:true});
  expect(hash()).toBe(beforeHash);
});
