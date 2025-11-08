import React, { useState, useEffect } from 'react';
import { useNavigate } from '@tanstack/react-router';

/**
 * Extraction page.  Allows users to perform structured data extraction
 * on a Phase 1 or Phase 2 directory.  Users can configure whether
 * to retrieve open access PDFs, query Unpaywall, and select which
 * elements to extract.  Progress is displayed while the job runs.
 */
const Extraction: React.FC = () => {
  const navigate = useNavigate();
  const [phaseDir, setPhaseDir] = useState('');
  const [useOpenAccess, setUseOpenAccess] = useState(true);
  const [useUnpaywall, setUseUnpaywall] = useState(false);
  const [unpaywallEmail, setUnpaywallEmail] = useState('');
  const [extractSample, setExtractSample] = useState(true);
  const [extractOutcomes, setExtractOutcomes] = useState(true);
  const [extractStats, setExtractStats] = useState(true);
  const [extractMethods, setExtractMethods] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [phase, setPhase] = useState<string>('');
  const [progress, setProgress] = useState<number>(0);
  const [total, setTotal] = useState<number | null>(null);
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
            setError(data.error || 'Extraction failed.');
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
      navigate({ to: '/results', search: { dir: outputDir } });
    }
  }, [outputDir, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload: any = {
        phase_dir: phaseDir,
        use_open_access: useOpenAccess,
        use_unpaywall: useUnpaywall,
        extract_sample_size: extractSample,
        extract_outcomes: extractOutcomes,
        extract_statistics: extractStats,
        extract_methods: extractMethods,
      };
      if (useUnpaywall) {
        payload.unpaywall_email = unpaywallEmail;
      }
      const res = await fetch('/api/extraction/start', {
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
      <h2 className="text-2xl font-bold">Data Extraction</h2>
      <p className="text-gray-600">
        Configure structured data extraction from a phase directory.  You can choose
        whether to pull open access PDFs, query Unpaywall and which data types
        to extract.  Note that full text retrieval is best effort and may
        require an Unpaywall email.
      </p>
      <form onSubmit={handleSubmit} className="space-y-4 bg-white shadow rounded-lg p-6">
        {error && <div className="text-red-600 mb-2">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Phase Directory</label>
          <input
            type="text"
            required
            value={phaseDir}
            onChange={(e) => setPhaseDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1.5_20240101_120000"
          />
        </div>
        <div className="flex items-center space-x-4">
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={useOpenAccess} onChange={() => setUseOpenAccess((v) => !v)} />
            <span className="text-sm">Use open access PDFs</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={useUnpaywall} onChange={() => setUseUnpaywall((v) => !v)} />
            <span className="text-sm">Use Unpaywall</span>
          </label>
        </div>
        {useUnpaywall && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Unpaywall Email</label>
            <input
              type="email"
              value={unpaywallEmail}
              onChange={(e) => setUnpaywallEmail(e.target.value)}
              className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="your.email@institution.edu"
            />
          </div>
        )}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Extraction Targets</label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={extractSample} onChange={() => setExtractSample((v) => !v)} />
            <span className="text-sm">Sample sizes</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={extractOutcomes} onChange={() => setExtractOutcomes((v) => !v)} />
            <span className="text-sm">Outcomes & effect sizes</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={extractStats} onChange={() => setExtractStats((v) => !v)} />
            <span className="text-sm">P-values & CIs</span>
          </label>
          <label className="flex items-center space-x-2">
            <input type="checkbox" checked={extractMethods} onChange={() => setExtractMethods((v) => !v)} />
            <span className="text-sm">Statistical methods</span>
          </label>
        </div>
        <button
          type="submit"
          disabled={!!jobId}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-3 rounded-lg font-semibold"
        >
          {jobId ? 'Extracting…' : '🔬 Start Extraction'}
        </button>
      </form>
      {jobId && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h3 className="text-lg font-semibold text-gray-800 mb-2">Extraction Progress</h3>
          <div className="text-gray-700 capitalize">Phase: {phase || 'initializing'}</div>
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

export default Extraction;