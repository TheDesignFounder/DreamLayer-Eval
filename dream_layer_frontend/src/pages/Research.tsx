import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import type { Asset, Experiment, MetricResult, ResearchDetail, Rubric } from '@/types/research';

import { researchApi, jsonPost } from '@/services/researchApi';
import ResearchAnalysis from '@/components/ResearchAnalysis';
const base = '/api/research';
const initial = { schema_version: 1, name: 'My media experiment', models: ['imported'], prompts: [{ id: 'p1', text: 'Describe the intended task here', group_id: 'family-1', split: 'exploratory' }], assets: [], metrics: [{ id: 'pixel_luminance' }, { id: 'adjacent_pixel_stability' }], judges: [], concurrency: 1 };
const rubric: Rubric = { version: '1', criteria: [{ id: 'task', description: 'Does the visible evidence fulfill the original task? Use uncertain when evidence is inadequate.' }] };
const button = 'rounded border px-3 py-2 text-sm hover:bg-muted disabled:opacity-40';

export default function Research() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selected, setSelected] = useState('');
  const [detail, setDetail] = useState<ResearchDetail | null>(null);
  const [config, setConfig] = useState(JSON.stringify(initial, null, 2));
  const [rubricText, setRubricText] = useState(JSON.stringify(rubric, null, 2));
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [report, setReport] = useState<unknown>(null);
  const [definitions, setDefinitions] = useState<unknown>(null);
  const [rater, setRater] = useState('rater-1');
  const [mode, setMode] = useState('pointwise');
  const [includeMedia, setIncludeMedia] = useState(true);
  const [labelView, setLabelView] = useState('raw');
  const [requestId, setRequestId] = useState('');
  const [retryNote, setRetryNote] = useState('');
  const [unknownDelivery, setUnknownDelivery] = useState(false);
  const [upgradeEvaluators, setUpgradeEvaluators] = useState(false);
  useEffect(() => { setUpgradeEvaluators(false); }, [selected]);
  const [resolution, setResolution] = useState('not_delivered');
  const [recovered, setRecovered] = useState('{}');
  const refresh = useCallback(async () => {
    setExperiments(await researchApi<Experiment[]>('/experiments'));
    if (selected) setDetail(await researchApi<ResearchDetail>(`/experiments/${selected}`));
  }, [selected]);
  useEffect(() => { refresh().catch(e => setError(String(e))); }, [refresh]);
  useEffect(() => {
    if (!selected) return;
    const timer = window.setInterval(() => refresh().catch(e => setError(String(e))), 1500);
    return () => window.clearInterval(timer);
  }, [selected, refresh]);
  async function action(fn: () => Promise<void>) {
    setError(''); setNotice(''); setBusy(true);
    try { await fn(); await refresh(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const results = detail?.records.filter(r => r.kind === 'result') as MetricResult[] | undefined;
  const assets = detail?.records.filter(r => r.kind === 'asset') as Asset[] | undefined;
  return <main className="mx-auto max-w-7xl p-6 space-y-6">
    <header className="flex items-start justify-between gap-4"><div><h1 className="text-3xl font-semibold">Research workbench</h1><p className="mt-2 text-muted-foreground">Versioned image and video experiments · explicit evidence, failures, and uncertainty</p></div><Link className={button} to="/">Generation workspace</Link></header>
    {error && <div role="alert" className="rounded border border-red-500 p-3 text-red-600">{error}</div>}
    {notice && <div role="status" className="rounded border p-3">{notice}</div>}
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded border p-4 space-y-3"><h2 className="text-lg font-semibold">Import and configure</h2>
        <p className="text-sm text-muted-foreground">Upload media, edit its prompt and group, then freeze a new experiment. Related prompts, repeats and derived clips belong in the same split.</p>
        <label className="block">Import media <input aria-label="Import media" type="file" multiple accept="image/*,video/*" onChange={e => {
          const files = Array.from(e.target.files || []);
          action(async () => {
            const parsed = JSON.parse(config);
            for (const file of files) {
              const form = new FormData(); form.append('file', file);
              const uploaded = await researchApi<{path: string; original_filename: string}>('/upload', { method: 'POST', body: form });
              parsed.assets.push({ path: uploaded.path, original_filename: uploaded.original_filename, prompt_id: parsed.prompts[0].id, model: parsed.models[0], repeat_index: parsed.assets.length });
            }
            setConfig(JSON.stringify(parsed, null, 2)); setNotice(`Imported ${files.length} media files. Inspect the configuration before freezing.`);
          });
        }} /></label>
        <label className="block">Load config <input aria-label="Load config" type="file" accept=".json" onChange={e => { const file = e.target.files?.[0]; if (file) action(async () => setConfig(await file.text())); }} /></label>
        <label className="block text-sm" htmlFor="experiment-config">Experiment configuration, including editable criteria</label>
        <textarea id="experiment-config" className="w-full rounded border bg-background p-3 font-mono text-xs" rows={16} value={config} onChange={e => setConfig(e.target.value)} spellCheck={false} />
        <button className={button} disabled={busy} onClick={() => action(async () => { const preview = await researchApi<{config: unknown}>('/preview', jsonPost(JSON.parse(config))); setConfig(JSON.stringify(preview.config, null, 2)); setNotice('Interpreted criteria added. Review and edit them before creating the experiment.'); })}>Preview criteria</button>{' '}
        <button className={button} disabled={busy} onClick={() => action(async () => { const exp = await researchApi<Experiment>('/experiments', jsonPost(JSON.parse(config))); setSelected(exp.id); setNotice('Configuration frozen. Changes require a new experiment version.'); })}>Create experiment</button>
      </section>
      <section className="rounded border p-4 space-y-4"><h2 className="text-lg font-semibold">Execute and inspect</h2>
        <label className="block">Experiment <select aria-label="Experiment" className="ml-2 max-w-full border bg-background p-2" value={selected} onChange={e => { setSelected(e.target.value); setReport(null); }}><option value="">Select an experiment</option>{experiments.map(e => <option key={e.id} value={e.id}>{String(e.config.name)} · {e.id.slice(0, 8)}</option>)}</select></label>
        <p data-testid="job-state">State: {detail?.job.state || 'No experiment selected'}</p>
        {detail?.job.error && <p role="alert">{detail.job.error}</p>}
        <label className="block text-sm"><input aria-label="Upgrade evaluators" type="checkbox" checked={upgradeEvaluators} onChange={e => setUpgradeEvaluators(e.target.checked)} /> Upgrade changed evaluators on this run (re-evaluates and supersedes prior results)</label>
        <p className="text-sm text-muted-foreground">If an upgrade cannot run or fails, execution stops and its previously successful results stay current. Fix the evaluator environment before retrying the upgrade.</p>
        <div className="flex flex-wrap gap-2">
          <button className={button} disabled={!selected || busy} onClick={() => action(async () => setReport(await researchApi(`/experiments/${selected}/plan`)))}>Dry run</button>
          <button className={button} disabled={!selected || busy} onClick={() => action(async () => { const response = await researchApi<{resume_warnings: {message: string}[]}>(`/experiments/${selected}/run`, jsonPost({upgrade_evaluators: upgradeEvaluators})); setNotice(['Execution queued.', ...response.resume_warnings.map(w => w.message)].join(' ')); })}>Run / resume</button>
          <button className={button} disabled={!selected || busy} onClick={() => action(async () => { const response = await researchApi<{resume_warnings: {message: string}[]}>(`/experiments/${selected}/run`, jsonPost({rerun_failed: true, upgrade_evaluators: upgradeEvaluators})); setNotice(['Failed metric evaluations queued as new attempts.', ...response.resume_warnings.map(w => w.message)].join(' ')); })}>Rerun failed metrics</button>
          <button className={button} disabled={!selected || busy} onClick={() => action(async () => { await researchApi(`/experiments/${selected}/cancel`, jsonPost({})); setNotice('Cancellation requested. Completed work is retained.'); })}>Cancel</button>
          <button className={button} disabled={!selected || busy} onClick={() => action(async () => setReport(await researchApi(`/experiments/${selected}/analysis`, jsonPost({ seed: 0, label_view: labelView }))))}>Analyze</button>
        </div>
        <label className="block">Analysis labels <select aria-label="Analysis labels" value={labelView} onChange={e => setLabelView(e.target.value)}><option value="raw">Raw independent labels</option><option value="adjudicated">Adjudicated overlay</option></select></label>
        <button className={button} disabled={!selected || busy} onClick={() => action(async () => setReport(await researchApi(`/experiments/${selected}/comparison`, jsonPost({label_view: labelView}))))}>Compare metrics, judges and humans</button>
        {detail && <p className="break-all text-xs text-muted-foreground">Frozen configuration hash: {detail.experiment.config_hash}</p>}
        {detail && <details><summary>Frozen experiment settings</summary><pre className="max-h-72 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(detail.experiment.config, null, 2)}</pre></details>}
        <details><summary>Metric definitions and limitations</summary><button className={button} onClick={() => action(async () => setDefinitions(await researchApi('/metrics')))}>Load definitions</button><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{definitions ? JSON.stringify(definitions, null, 2) : 'Select Load definitions.'}</pre></details>
        <ResearchAnalysis value={report} />
        {report !== null && <pre data-testid="analysis-report" className="max-h-96 overflow-auto rounded bg-muted p-3 text-xs">{JSON.stringify(report, null, 2)}</pre>}
      </section>
    </div>
    <section className="rounded border p-4"><h2 className="mb-3 text-lg font-semibold">Results and partial failures</h2>
      {!results?.length ? <p>No metric results yet. Run an imported experiment to populate this table.</p> : <div className="overflow-auto"><table className="w-full text-left text-sm"><thead><tr>{['Metric', 'Version', 'Scope', 'Score', 'Status', 'Attempt', 'Reason'].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{results.map(r => <tr className="border-t" key={r.id}><td className="p-2">{r.metric_id}</td><td>{r.metric_version}</td><td>{r.scope}</td><td data-testid="metric-score">{r.score === null ? r.special_value === 'positive_infinity' ? '∞ (identical)' : '—' : r.score.toPrecision(6)}</td><td>{r.status}</td><td>{r.evaluation_attempt || 1} · {results.some(newer => newer.supersedes === r.id || newer.supersedes_ids?.includes(r.id)) ? 'Superseded' : 'Current'}</td><td>{r.reason || ''}</td></tr>)}</tbody></table></div>}
      <details className="mt-3"><summary>Attempts, raw judge responses and provenance</summary><pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(detail?.records.filter(r => ['attempt', 'judge_call', 'result'].includes(r.kind)), null, 2)}</pre></details>
    </section>
    <details className="rounded border p-4 space-y-3"><summary>Recover a failed judge assessment</summary>
      <p className="text-sm">Select the latest request from the saved provenance. Retries append attempts with the same presentation order. A retry permits one additional call, 40 evidence images and 1,000,000 reserved tokens. Unknown delivery requires reconciliation or explicit acceptance of a possible duplicate charge.</p>
      <label className="block">Judge request ID <input aria-label="Judge request ID" className="w-full border bg-background p-2" value={requestId} onChange={e => setRequestId(e.target.value)} /></label>
      <label className="block">Recovery note <input aria-label="Recovery note" className="w-full border bg-background p-2" value={retryNote} onChange={e => setRetryNote(e.target.value)} /></label>
      <label className="block"><input type="checkbox" checked={unknownDelivery} onChange={e => setUnknownDelivery(e.target.checked)} /> Retry despite unknown delivery and possible duplicate billing</label>
      <button className={button} disabled={busy || !requestId || !retryNote} onClick={() => action(async () => setReport(await researchApi(`/judges/${requestId}/retry`, jsonPost({note: retryNote, allow_unknown: unknownDelivery}))))}>Retry judge</button>
      <label className="block">Reconciliation <select aria-label="Reconciliation" value={resolution} onChange={e => setResolution(e.target.value)}><option value="not_delivered">Verified not delivered</option><option value="abandon">Abandon assessment</option><option value="completed">Record recovered response</option></select></label>
      {resolution === 'completed' && <label className="block">Recovered response JSON<textarea aria-label="Recovered response JSON" className="w-full border bg-background p-2" value={recovered} onChange={e => setRecovered(e.target.value)} /></label>}
      <button className={button} disabled={busy || !requestId || !retryNote} onClick={() => action(async () => setReport(await researchApi(`/judges/${requestId}/reconcile`, jsonPost({note: retryNote, resolution, ...(resolution === 'completed' ? {parsed_response: JSON.parse(recovered)} : {})}))))}>Save reconciliation</button>
    </details>
    <section><h2 className="mb-3 text-lg font-semibold">Media and original prompts</h2><div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{assets?.map(a => {
      const trial = detail?.records.find(r => r.id === a.trial_id); const prompt = detail?.records.find(r => r.id === trial?.prompt_id);
      return <article key={a.id} className="rounded border p-3 space-y-2"><p>{String(prompt?.text || 'Reference asset')}</p>{a.media.modality === 'video' ? <video className="max-h-56 w-full" controls preload="metadata" src={`${base}/assets/${a.id}/media`} /> : <img className="max-h-56 w-full object-contain" src={`${base}/assets/${a.id}/media`} alt={String(prompt?.text || 'Reference')} />}<p className="text-xs">{a.original_filename} · {a.media.width} × {a.media.height}</p><details><summary className="text-xs">Provenance</summary><pre className="overflow-auto text-xs">{JSON.stringify(a, null, 2)}</pre></details></article>;
    })}</div></section>
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded border p-4 space-y-3"><h2 className="text-lg font-semibold">Blinded human review</h2><p className="text-sm">Independent ratings are retained. Explicit labels are hidden in the review view; recognizable styles can still reveal identity.</p>
        <label className="block">Pseudonymous rater <input className="border bg-background p-2" aria-label="Rater ID" value={rater} onChange={e => setRater(e.target.value)} /></label>
        <label className="block">Review mode <select className="border bg-background p-2" value={mode} onChange={e => setMode(e.target.value)}><option value="pointwise">Pointwise criteria</option><option value="pairwise">Pairwise preference</option></select></label>
        <label className="block">Versioned rubric<textarea aria-label="Rubric" className="w-full border bg-background p-2 font-mono text-xs" rows={5} value={rubricText} onChange={e => setRubricText(e.target.value)} /></label>
        <button className={button} disabled={!detail?.experiment.config.judges} onClick={() => { const configured = detail?.experiment.config.judges as {rubric: Rubric; mode?: string}[]; if (configured?.length) { setRubricText(JSON.stringify(configured[0].rubric, null, 2)); setMode(configured[0].mode || 'pointwise'); } }}>Use first judge rubric</button>
        <button className={button} disabled={!selected || busy} onClick={() => action(async () => { await researchApi(`/experiments/${selected}/assign`, jsonPost({ rater_id: rater, rubric: JSON.parse(rubricText), mode, seed: 0 })); setNotice('Assignments saved. Each rater can resume their own review.'); })}>Create review assignments</button>{' '}
        <Link className={button} to={`/research/review?rater=${encodeURIComponent(rater)}`}>Open blinded review</Link>
      </section>
      <section className="rounded border p-4 space-y-3"><h2 className="text-lg font-semibold">Export and replay</h2>
        <label className="block"><input type="checkbox" checked={includeMedia} onChange={e => setIncludeMedia(e.target.checked)} /> Include media in bundle</label>
        {selected && <a className={button} href={`${base}/experiments/${selected}/export?media=${includeMedia ? '1' : '0'}`}>Export experiment</a>}
        <label className="block">Reload bundle <input aria-label="Reload bundle" type="file" accept=".zip" onChange={e => { const file = e.target.files?.[0]; if (file) action(async () => { const form = new FormData(); form.append('file', file); const data = await researchApi<{ experiment_id: string }>('/import-bundle', { method: 'POST', body: form }); setSelected(data.experiment_id); setNotice('Bundle verified and imported. Analyze to reproduce the saved results.'); }); }} /></label>
        <label className="block">Import historical human rankings <input aria-label="Import historical human rankings" type="file" accept=".csv,.json" onChange={e => { const file = e.target.files?.[0]; if (file) action(async () => { const form = new FormData(); form.append('file', file); const exp = await researchApi<Experiment>('/import-rankings', {method: 'POST', body: form}); setSelected(exp.id); setNotice('Historical rankings imported with unresolved asset links and original labels retained.'); }); }} /></label>
        {selected && <div className="flex flex-wrap gap-3"><a href={`${base}/experiments/${selected}/annotations?format=jsonl&blinded=1`}>Blinded annotation export</a><a href={`${base}/experiments/${selected}/comparison-rows?label_view=${labelView}`}>Joined comparison rows</a></div>}
        <p className="text-sm text-muted-foreground">JSONL and CSV retain nulls, statuses and evaluator versions. Advanced paired, agreement and selection analyses are available through <code>python -m research statistics --help</code>.</p>
        {selected && <div className="flex gap-3"><a href={`${base}/experiments/${selected}/annotations?format=jsonl`}>Annotation JSONL</a><a href={`${base}/experiments/${selected}/annotations?format=csv`}>Annotation CSV</a></div>}
      </section>
    </div>
  </main>;
}
