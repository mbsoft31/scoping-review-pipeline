import React, { useState, useEffect } from 'react';

/**
 * Review page.  Provides a simple human review interface for screening
 * results.  The user specifies the screening directory, fetches the
 * next paper for review, chooses a decision (include/exclude/maybe)
 * and can add optional notes.  Basic review statistics are displayed.
 */
interface ReviewPaper {
  paper_id: string;
  title: string;
  abstract: string;
  decision?: string;
}

const Review: React.FC = () => {
  const [screeningDir, setScreeningDir] = useState('');
  const [currentPaper, setCurrentPaper] = useState<ReviewPaper | null>(null);
  const [decision, setDecision] = useState<'include' | 'exclude' | 'maybe'>('include');
  const [notes, setNotes] = useState('');
  const [stats, setStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!screeningDir) return;
    // Fetch review statistics when directory changes
    const fetchStats = async () => {
      try {
        const res = await fetch(`/api/review/${encodeURIComponent(screeningDir)}/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchStats();
  }, [screeningDir]);

  const fetchNext = async () => {
    if (!screeningDir) return;
    setError(null);
    try {
      const res = await fetch(`/api/review/${encodeURIComponent(screeningDir)}/next?n=1`);
      if (!res.ok) {
        throw new Error('Failed to fetch next paper');
      }
      const data = await res.json();
      setCurrentPaper(data[0] || null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const submitReview = async () => {
    if (!screeningDir || !currentPaper) return;
    setError(null);
    try {
      const payload = {
        paper_id: currentPaper.paper_id,
        decision,
        reviewer: 'anonymous',
        notes: notes || undefined,
      };
      const res = await fetch(`/api/review/${encodeURIComponent(screeningDir)}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to submit review');
      // Clear current paper and fetch next
      setCurrentPaper(null);
      setNotes('');
      await fetchNext();
      // Refresh stats
      const statsRes = await fetch(`/api/review/${encodeURIComponent(screeningDir)}/stats`);
      if (statsRes.ok) {
        setStats(await statsRes.json());
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h2 className="text-2xl font-bold">Review Queue</h2>
      <p className="text-gray-600">Review uncertain papers and decide whether to include or exclude them.</p>
      <div className="bg-white shadow rounded-lg p-6 space-y-4">
        {error && <div className="text-red-600">{error}</div>}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Screening Directory</label>
          <input
            type="text"
            value={screeningDir}
            onChange={(e) => setScreeningDir(e.target.value)}
            className="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            placeholder="output/phase1.5_20240101_120000"
          />
          <button
            type="button"
            onClick={fetchNext}
            disabled={!screeningDir}
            className="mt-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded-lg"
          >
            Fetch Next Paper
          </button>
        </div>
        {currentPaper && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">{currentPaper.title}</h3>
            <p className="whitespace-pre-wrap text-gray-700">{currentPaper.abstract}</p>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Decision</label>
              <div className="flex space-x-4">
                {['include', 'exclude', 'maybe'].map((d) => (
                  <label key={d} className="flex items-center space-x-2">
                    <input
                      type="radio"
                      name="decision"
                      value={d}
                      checked={decision === d}
                      onChange={() => setDecision(d as any)}
                    />
                    <span className="capitalize">{d}</span>
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                rows={3}
              />
            </div>
            <button
              type="button"
              onClick={submitReview}
              className="bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded-lg"
            >
              Submit Review
            </button>
          </div>
        )}
        {stats && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h4 className="font-semibold mb-2">Review Statistics</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
              {Object.entries(stats).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="capitalize text-gray-600">{key.replace('_', ' ')}</span>
                  <span className="font-medium text-gray-800">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Review;