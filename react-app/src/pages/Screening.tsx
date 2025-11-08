import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Screening page.  Allows users to configure and run AI‑assisted
 * screening on a Phase 1 directory.  Users can specify the model,
 * thresholds and inclusion/exclusion criteria.  Progress is shown
 * while the job runs, and the user is redirected to the review queue
 * or results upon completion.
 */
const Screening: React.FC = () => {
  const navigate = useNavigate();
  const [phaseDir, setPhaseDir] = useState('');
  const [mode, setMode] = useState<'auto' | 'semi_auto' | 'hitl'>('auto');
  const [autoThreshold, setAutoThreshold] = useState(0.75);
  const [maybeThreshold, setMaybeThreshold] = useState(0.5);
  const [model, setModel] = useState('all-MiniLM-L6-v2');
  const [inclusion, setInclusion] = useState<{ name: string; keywords: string }[]>([]);
  const [exclusion, setExclusion] = useState<{ name: string; keywords: string }[]>([]);
  const [newCriterion, setNewCriterion] = useState<{ type: 'include' | 'exclude'; name: string; keywords: string }>({ type: 'include', name: '', keywords: '' });
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [total, setTotal] = useState<number | null>(null);
  const [phase, setPhase] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [outputDir, setOutputDir] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;
    let interval: number;
    const poll = async () => {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          const data = await res.json();
          setPhase(String(data.phase || ''));
          setProgress(data.progress ?? 0);
          setTotal(data.total ?? null);
          if (data.status === 'completed') {
            setOutputDir(data.output_dir);
            clearInterval(interval);
          }
          if (data.status === 'failed') {
            clearInterval(interval);
            setError(data.error || 'Screening failed.');
          }
        }
      } catch (err) {
        console.error(err);
      }
    };
    poll();
    interval = window.setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [jobId]);

  useEffect(() => {
    if (outputDir) {
      // After screening, a phase1.5 directory is created.  Redirect to results or review.
      navigate({ to: '/results', search: { dir: outputDir } });
    }
  }, [outputDir, navigate]);

  const addCriterion = () => {
    if (!newCriterion.name || !newCriterion.keywords) return;
    const criterionObj = {
      name: newCriterion.name,
      keywords: newCriterion.keywords,
    };
    if (newCriterion.type === 'include') {
      setInclusion((prev) => [...prev, criterionObj]);
    } else {
      setExclusion((prev) => [...prev, criterionObj]);
    }
    setNewCriterion({ type: 'include', name: '', keywords: '' });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload: any = {
        phase1_dir: phaseDir,
        mode,
        auto_threshold: autoThreshold,
        maybe_threshold: maybeThreshold,
        model,
        inclusion_criteria: inclusion.map((c) => ({ name: c.name, keywords: c.keywords.split(',').map((k) => k.trim()) })),
        exclusion_criteria: exclusion.map((c) => ({ name: c.name, keywords: c.keywords.split(',').map((k) => k.trim()) })),
      };
      const res = await fetch('/api/screening/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        throw new Error(`Error: ${res.status}`);
      }
      const data = await res.json();
      setJobId(data.job_id);
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">AI‑Assisted Screening</h2>
      <p className="text-gray-600">
        Configure the screening task.  Provide a Phase 1 directory and set
        thresholds.  You can define inclusion and exclusion criteria; each
        criterion consists of a name and a comma‑separated list of keywords.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phase 1 Directory</label>
          <input
            type="text"
            required
            value={phaseDir}
            onChange={(e) => setPhaseDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1_20240101_120000"
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Mode</label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as any)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="auto">Auto</option>
              <option value="semi_auto">Semi‑Auto</option>
              <option value="hitl">HITL (human‑in‑the‑loop)</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Auto Threshold</label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={autoThreshold}
              onChange={(e) => setAutoThreshold(parseFloat(e.target.value))}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Maybe Threshold</label>
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={maybeThreshold}
              onChange={(e) => setMaybeThreshold(parseFloat(e.target.value))}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
          <input
            type="text"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">Sentence transformer model (e.g. all-MiniLM-L6-v2).</p>
        </div>
        <div>
          <h3 className="text-md font-semibold mb-1">Criteria</h3>
          <div className="flex space-x-2 mb-2">
            <select
              value={newCriterion.type}
              onChange={(e) => setNewCriterion((c) => ({ ...c, type: e.target.value as any }))}
              className="px-3 py-2 border rounded-lg text-sm"
            >
              <option value="include">Include</option>
              <option value="exclude">Exclude</option>
            </select>
            <input
              type="text"
              value={newCriterion.name}
              onChange={(e) => setNewCriterion((c) => ({ ...c, name: e.target.value }))}
              placeholder="Criterion name"
              className="flex-1 px-3 py-2 border rounded-lg text-sm"
            />
            <input
              type="text"
              value={newCriterion.keywords}
              onChange={(e) => setNewCriterion((c) => ({ ...c, keywords: e.target.value }))}
              placeholder="keywords (comma separated)"
              className="flex-1 px-3 py-2 border rounded-lg text-sm"
            />
            <button
              type="button"
              onClick={addCriterion}
              className="bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded-lg text-sm"
            >
              Add
            </button>
          </div>
          <div className="space-y-1">
            {inclusion.map((c, idx) => (
              <div key={`inc-${idx}`} className="text-sm text-green-700">
                Include: {c.name} ({c.keywords})
              </div>
            ))}
            {exclusion.map((c, idx) => (
              <div key={`exc-${idx}`} className="text-sm text-red-700">
                Exclude: {c.name} ({c.keywords})
              </div>
            ))}
          </div>
        </div>
        <button
          type="submit"
          disabled={!!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Screening…' : '🧠 Start Screening'}
        </button>
      </form>
      {jobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Screening Progress</h3>
          <div className="text-gray-700 capitalize">Phase: {phase || 'initialising'}</div>
          <div className="text-gray-700">Processed {progress} papers{total ? ` / ${total}` : ''}</div>
          <div className="relative h-4 mt-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="bg-blue-600 h-full rounded-full transition-all"
              style={{ width: total && total > 0 ? `${(progress / total) * 100}%` : '0%' }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default Screening;