/**
 * Analyse component for Phase 2 of the SRP web UI.
 *
 * This Alpine.js component exposes a form for running Phase 2 analysis
 * and polls the backend for job progress.  When the analysis
 * completes or fails, polling is stopped.
 */
export function analyzeApp() {
  return {
    form: {
      phase1_dir: '',
      citation_max_papers: 200,
      refs_per_paper: 100,
      fuzzy_threshold: 0.85,
      skip_citations: false,
    },
    loading: false,
    jobId: null as string | null,
    currentPhase: null as string | null,
    async submitAnalysis() {
      this.loading = true;
      try {
        const response = await fetch('/api/analyze/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.form),
        });
        const data = await response.json();
        this.jobId = data.job_id;
        this.pollProgress();
        const htmx = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (error: any) {
        alert('Error starting analysis: ' + error.message);
      } finally {
        this.loading = false;
      }
    },
    pollProgress() {
      const interval = setInterval(async () => {
        if (!this.jobId) return;
        try {
          const response = await fetch(`/api/jobs/${this.jobId}`);
          const job = await response.json();
          this.currentPhase = job.phase;
          if (job.status === 'completed' || job.status === 'failed') {
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Polling error:', error);
        }
      }, 2000);
    },
    phaseComplete(phase: string) {
      const phases = ['loading', 'deduplicating', 'fetching_citations', 'computing_influence'];
      const currentIndex = phases.indexOf(this.currentPhase || '');
      const checkIndex = phases.indexOf(phase);
      return currentIndex > checkIndex;
    },
  };
}