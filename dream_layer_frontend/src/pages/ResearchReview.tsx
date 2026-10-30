import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { BlindAssignment } from '@/types/research';
import { researchApi, jsonPost } from '@/services/researchApi';

export default function ResearchReview() {
  const [query] = useSearchParams();
  const [rater, setRater] = useState(query.get('rater') || 'rater-1');
  const [assignments, setAssignments] = useState<BlindAssignment[]>([]);
  const [selected, setSelected] = useState('');
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [comment, setComment] = useState('');
  const [intervals, setIntervals] = useState('[]');
  const [rating, setRating] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const current = assignments.find(a => a.id === selected);
  async function load() {
    try { const data = await researchApi<BlindAssignment[]>(`/review?rater=${encodeURIComponent(rater)}`); setAssignments(data); setSelected(data.find(a => !a.completed)?.id || data[0]?.id || ''); setError(''); } catch (e) { setError(String(e)); }
  }
  useEffect(() => { let active = true; researchApi<BlindAssignment[]>(`/review?rater=${encodeURIComponent(rater)}`).then(data => { if (active) { setAssignments(data); setSelected(data.find(a => !a.completed)?.id || data[0]?.id || ''); } }).catch(e => setError(String(e))); return () => { active = false; }; }, [rater]);
  useEffect(() => { setLabels({}); setComment(''); setIntervals('[]'); setRating(''); }, [selected]);
  return <main className="mx-auto max-w-5xl p-6 space-y-5"><h1 className="text-3xl font-semibold">Blinded media review</h1><p>Evaluate the complete media against the rubric. Task correctness and aesthetic preference are separate. Uncertainty is a valid response.</p>
    <label>Pseudonymous rater <input aria-label="Rater ID" className="border bg-background p-2" value={rater} onChange={e => setRater(e.target.value)} /></label>
    {error && <p role="alert" className="text-red-600">{error}</p>}{notice && <p role="status">{notice}</p>}
    <label className="block">Assignment <select aria-label="Review assignment" className="border bg-background p-2" value={selected} onChange={e => setSelected(e.target.value)}>{assignments.map((a, i) => <option key={a.id} value={a.id}>Item {i + 1}{a.completed ? ' · saved' : ''}{a.practice ? ' · practice' : ''}</option>)}</select></label>
    {!current ? <p>No assignments for this rater.</p> : <section className="space-y-5"><h2 className="text-xl">{current.prompt_text}</h2><p>Rubric version {current.rubric.version}</p>
      <div className="grid gap-5 md:grid-cols-2">{current.media.map((m, i) => <figure key={m.slot}><figcaption>Evidence {String.fromCharCode(65 + i)}</figcaption>{m.modality === 'video' ? <video data-testid="review-video" className="max-h-96 w-full" controls preload="metadata" src={m.url} onError={() => setError("This browser cannot play this video codec. Open the evidence link in a compatible player.")} onTimeUpdate={e => { e.currentTarget.nextElementSibling!.textContent = `${e.currentTarget.currentTime.toFixed(2)} seconds`; }} /> : <img className="max-h-96 w-full object-contain" src={m.url} alt={`Evidence ${String.fromCharCode(65 + i)}`} />}<p aria-live="off" className="text-sm" /><a className="text-sm underline" href={m.url} target="_blank" rel="noreferrer">Open evidence</a></figure>)}</div>
      {current.references.map((m, i) => <figure key={m.slot}><figcaption>Reference {i + 1}</figcaption>{m.modality === 'video' ? <video controls className="max-h-72" src={m.url} /> : <img className="max-h-72" src={m.url} alt="Task reference" />}</figure>)}
      {current.rubric.criteria.map(c => <label className="block" key={c.id}>{c.description}<select className="ml-3 border bg-background p-2" aria-label={`Criterion ${c.id}`} value={labels[c.id] || ''} onChange={e => setLabels({ ...labels, [c.id]: e.target.value })}><option value="">Choose a verdict</option>{(current.mode === 'pairwise' ? ['A', 'B', 'tie', 'uncertain'] : ['pass', 'fail', 'uncertain', 'not_applicable']).map(v => <option key={v}>{v}</option>)}</select></label>)}
      <label className="block">Optional aesthetics (1–5)<select aria-label="Aesthetic rating" className="ml-3 border bg-background p-2" value={rating} onChange={e => setRating(e.target.value)}><option value="">Not rated</option>{[1, 2, 3, 4, 5].map(n => <option key={n}>{n}</option>)}</select></label>
      <label className="block">Failure intervals in seconds, e.g. [[1.2, 2.0]]<input aria-label="Failure intervals" className="block w-full border bg-background p-2" value={intervals} onChange={e => setIntervals(e.target.value)} /></label>
      <label className="block">Comment<textarea aria-label="Comment" className="block w-full border bg-background p-2" value={comment} onChange={e => setComment(e.target.value)} /></label>
      <button className="rounded border px-4 py-2 disabled:opacity-40" disabled={current.completed || Object.keys(labels).length !== current.rubric.criteria.length || Object.values(labels).some(v => !v)} onClick={async () => { try { await researchApi(`/review/${current.id}`, jsonPost({ rater_id: rater, labels, comment, intervals: JSON.parse(intervals), aesthetic_rating: rating ? Number(rating) : null })); setNotice('Independent annotation saved.'); await load(); } catch (e) { setError(String(e)); } }}>Save annotation</button>
      {current.completed && <p>This independent annotation is saved. Adjudication appends a separate record through the annotation API or CLI.</p>}
    </section>}
  </main>;
}
