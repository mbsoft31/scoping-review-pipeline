/**
 * PRISMA flow diagram component for the SRP web UI.
 *
 * Provides controls for selecting the Phase 1 search directory
 * and optional screening/deduplication directories and triggers
 * a PRISMA job via the API.  Progress and resulting counts are
 * polled and displayed.  This module implements the logic from
 * the inline ``prismaApp`` script.
 */
export function prismaApp() {
  return {
    form: {
      phase1_dir: '',
      screening_dir: '',
      dedup_dir: '',
    } as Record<string, string>,
    loading: false,
    jobId: null as string | null,
    diagramReady: false,
    counts: null as any,
    async startPrisma() {
      if (!this.form.phase1_dir) return;
      this.loading = true;
      this.diagramReady = false;
      try {
        const payload = {
          phase1_dir: this.form.phase1_dir,
          screening_dir: this.form.screening_dir || null,
          dedup_dir: this.form.dedup_dir || null,
        };
        const resp = await fetch('/api/prisma/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        this.jobId = data.job_id;
        this.pollProgress();
        // Trigger HTMX processing to update progress placeholders
        const htmx: any = (window as any).htmx;
        if (htmx) {
          htmx.process(document.body);
        }
      } catch (err: any) {
        alert('PRISMA generation failed: ' + err.message);
      } finally {
        this.loading = false;
      }
    },
    pollProgress() {
      const interval = setInterval(async () => {
        if (!this.jobId) return;
        try {
          const res = await fetch(`/api/jobs/${this.jobId}`);
          const job = await res.json();
          if (job.status === 'completed') {
            clearInterval(interval);
            this.diagramReady = true;
            this.counts = job.counts || null;
          } else if (job.status === 'failed') {
            clearInterval(interval);
            alert('PRISMA generation failed: ' + job.error);
          }
        } catch (err: any) {
          console.error('Error polling PRISMA job:', err);
        }
      }, 2000);
    },
  };
}