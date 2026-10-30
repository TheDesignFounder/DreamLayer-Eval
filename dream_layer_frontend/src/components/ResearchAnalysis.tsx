interface Interval { n: number; groups: number; mean: number | null; low: number | null; high: number | null }
interface Summary {
  planned: number; generated: number; failed: number; scored: number; unavailable: number; annotations: number;
  metrics: { metric_id: string; version: string; model: string; scope: string; category: string; split: string; denominator: number; statuses: Record<string, number>; summary: Interval | null }[];
  judge_tradeoffs: { provider: string; model: string; calls: number; statuses: Record<string, number>; mean_latency_ms: number | null; cost: number | null; estimated_cost: number | null; synthetic: boolean }[];
  comparisons?: Comparisons;
}
interface Comparisons {
  judge_vs_human: { provider: string; model: string; rater_id: string; criterion: string; split: string; rows: number; matched: number; mismatched_rubric: number; synthetic: boolean; binary?: {judged_binary: number; fp: number; fn: number; coverage: number | null}; preference_agreement?: {observed_agreement: number | null; n: number} }[];
  metric_vs_human: {metric_id: string; model: string; rater_id: string; criterion: string; split: string; rows: number; score_missing: number; correlations: {n: number; spearman: number | null; kendall_tau_b: number | null}}[];
  join_policy: string;
}
const number = (n: number | null) => n === null ? '—' : n.toPrecision(4);
function ComparisonView({report}: {report: Comparisons}) {
  return <section className="space-y-3" aria-label="Metric judge human comparisons"><h3 className="font-medium">Judge and metric comparison with human labels</h3>
    <p className="text-xs">{report.join_policy}</p>
    <div className="overflow-auto"><table className="w-full text-left text-xs"><thead><tr>{['Judge / rater / criterion', 'Split', 'Matched / rows', 'Coverage', 'False accepts / rejects', 'Pair agreement'].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{report.judge_vs_human.map((j,i) => <tr key={i} className="border-t"><td className="p-2">{j.provider} / {j.model}{j.synthetic ? ' · synthetic' : ''}<br />{j.rater_id} / {j.criterion}</td><td>{j.split}</td><td>{j.matched} / {j.rows}{j.mismatched_rubric ? ` · ${j.mismatched_rubric} rubric mismatch` : ''}</td><td>{j.binary ? number(j.binary.coverage) : '—'}</td><td>{j.binary ? `${j.binary.fp} / ${j.binary.fn} (${j.binary.judged_binary} binary judgments)` : '—'}</td><td>{j.preference_agreement ? `${number(j.preference_agreement.observed_agreement)} (n=${j.preference_agreement.n})` : '—'}</td></tr>)}</tbody></table></div>
    <div className="overflow-auto"><table className="w-full text-left text-xs"><thead><tr>{['Metric / model / rater / criterion', 'Split', 'Paired n / rows', 'Spearman', 'Kendall tau-b', 'Missing scores'].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{report.metric_vs_human.map((m,i) => <tr key={i} className="border-t"><td className="p-2">{m.metric_id} / {m.model}<br />{m.rater_id} / {m.criterion}</td><td>{m.split}</td><td>{m.correlations.n} / {m.rows}</td><td>{number(m.correlations.spearman)}</td><td>{number(m.correlations.kendall_tau_b)}</td><td>{m.score_missing}</td></tr>)}</tbody></table></div>
    <p className="text-xs">Small or constant samples have no correlation estimate. Full evaluator settings, denominators and source IDs are in the downloadable joined rows.</p>
  </section>;
}
export default function ResearchAnalysis({ value }: { value: unknown }) {
  if (value && typeof value === 'object' && 'judge_vs_human' in value) return <ComparisonView report={value as Comparisons} />;
  if (!value || typeof value !== 'object' || !('planned' in value)) return null;
  const report = value as Summary;
  return <div className="space-y-4" aria-label="Analysis summary">
    <dl className="grid grid-cols-3 gap-2">{(['planned', 'generated', 'failed', 'scored', 'unavailable', 'annotations'] as const).map(k => <div className="rounded bg-muted p-2" key={k}><dt className="text-xs capitalize">{k === 'generated' ? 'Successful imports / generations' : k}</dt><dd className="text-xl font-semibold">{report[k]}</dd></div>)}</dl>
    <p className="text-xs">Means use successful observations. Intervals resample independent prompt/template groups; missing results are excluded explicitly. Dataset scores remain separate.</p>
    <div className="overflow-auto"><table className="w-full text-left text-xs"><thead><tr>{['Metric / model', 'Evaluations', 'Scored / groups', 'Mean', '95% interval', 'Statuses'].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{report.metrics.map((m, i) => <tr className="border-t" key={i}><td className="p-2">{m.metric_id} v{m.version}<br />{m.model}<br />{m.category} · {m.split}</td><td>{m.denominator}</td><td>{m.summary ? `${m.summary.n} / ${m.summary.groups}` : 'dataset'}</td><td>{m.summary ? number(m.summary.mean) : 'See dataset result'}</td><td>{m.summary?.low !== null && m.summary?.low !== undefined ? `${number(m.summary.low)} to ${number(m.summary.high)}` : 'Insufficient groups / not applicable'}</td><td>{Object.entries(m.statuses).map(([k, n]) => `${k}: ${n}`).join(', ')}</td></tr>)}</tbody></table></div>
    {!!report.judge_tradeoffs.length && <div className="overflow-auto"><h3 className="font-medium">Judge calls, latency and cost</h3><table className="w-full text-left text-xs"><thead><tr>{['Judge', 'Calls', 'Mean latency', 'Confirmed cost', 'Estimated USD', 'Outcomes'].map(h => <th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{report.judge_tradeoffs.map(j => <tr className="border-t" key={j.provider + j.model}><td className="p-2">{j.provider} / {j.model}{j.synthetic ? ' · synthetic' : ''}</td><td>{j.calls}</td><td>{j.mean_latency_ms === null ? 'Unmeasured' : j.mean_latency_ms.toFixed(1) + ' ms'}</td><td>{j.cost === null ? 'Unknown' : j.cost}</td><td>{j.estimated_cost == null ? 'No price / usage' : '$' + j.estimated_cost.toFixed(6)}</td><td>{Object.entries(j.statuses).map(([k, n]) => `${k}: ${n}`).join(', ')}</td></tr>)}</tbody></table></div>}
    {report.comparisons && <ComparisonView report={report.comparisons} />}
  </div>;
}
