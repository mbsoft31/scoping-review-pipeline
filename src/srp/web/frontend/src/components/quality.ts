/**
 * Quality assessment component for the SRP web UI.
 *
 * Provides a form for selecting the phase directory and RoB tool, starts
 * the quality assessment job via the API and polls job progress via HTMX.
 */
export function qualityApp() {
  return {
    config: { tool: 'rob2' as string },
    phaseDir: '',
    loading: false,
    jobId: null as string | null,
    async startAssessment() {
      this.loading = true;
      try {
        const payload = {
          phase_dir: this.phaseDir,
          tool: this.config.tool,
        };
        const resp = await fetch('/api/quality/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        this.jobId = data.job_id;
        // Trigger HTMX processing
        const htmx: any = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (err: any) {
        alert('Quality assessment failed: ' + err.message);
      } finally {
        this.loading = false;
      }
    },
  };
}