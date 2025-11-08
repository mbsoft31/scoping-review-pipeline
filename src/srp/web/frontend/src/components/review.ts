/**
 * Human review interface component for the SRP web UI.
 *
 * This module ports the legacy JavaScript defined in ``review.html`` into
 * a TypeScript factory function compatible with Alpine.js.  It manages
 * loading review sessions, fetching the next batch of papers, tracking
 * reviewer identity and statistics, and submitting manual decisions.
 */
export function reviewApp() {
  return {
    selectedDir: '' as string,
    reviewerName: '' as string,
    tempReviewerName: '' as string,
    stats: null as any,
    papers: [] as any[],
    currentIndex: 0,
    currentPaper: null as any,
    notes: '' as string,
    sessionStats: {
      included: 0,
      maybe: 0,
      excluded: 0,
    } as Record<string, number>,
    init() {
      // Load reviewer identity from localStorage so that the reviewer does not
      // need to re‑enter their name on every page load.
      this.reviewerName = (localStorage.getItem('reviewer_name') || '') as string;
      this.tempReviewerName = this.reviewerName;
    },
    setReviewer() {
      if (this.tempReviewerName) {
        this.reviewerName = this.tempReviewerName;
        localStorage.setItem('reviewer_name', this.reviewerName);
        this.loadPapers();
      }
    },
    async loadSession() {
      // Fetch session statistics from the backend when a session is selected.
      if (!this.selectedDir) return;
      try {
        const response = await fetch(`/api/review/${this.selectedDir}/stats`);
        this.stats = await response.json();
        // Automatically load papers if the reviewer name has been set.
        if (this.reviewerName) {
          this.loadPapers();
        }
      } catch (error: any) {
        alert('Error loading session: ' + error.message);
      }
    },
    async loadPapers() {
      // Fetch the next batch of papers requiring review.
      if (!this.selectedDir) return;
      try {
        const response = await fetch(`/api/review/${this.selectedDir}/next?n=20`);
        this.papers = await response.json();
        if (this.papers.length > 0) {
          this.currentIndex = 0;
          this.currentPaper = this.papers[0];
        }
      } catch (error: any) {
        alert('Error loading papers: ' + error.message);
      }
    },
    async submitDecision(decision: string) {
      // Submit a decision (include, exclude or maybe) for the current paper.
      try {
        await fetch(`/api/review/${this.selectedDir}/submit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            paper_id: this.currentPaper.paper_id,
            decision,
            reviewer: this.reviewerName,
            notes: this.notes,
          }),
        });
        // Update local statistics
        this.sessionStats[decision] = (this.sessionStats[decision] || 0) + 1;
        // Clear notes and advance to the next paper
        this.notes = '';
        this.nextPaper();
        // Refresh session statistics
        this.loadSession();
      } catch (error: any) {
        alert('Error submitting decision: ' + error.message);
      }
    },
    nextPaper() {
      // Advance to the next paper or fetch new batch if at the end.
      if (this.currentIndex < this.papers.length - 1) {
        this.currentIndex++;
        this.currentPaper = this.papers[this.currentIndex];
      } else {
        this.loadPapers();
      }
    },
    previousPaper() {
      // Navigate backwards through the review queue.
      if (this.currentIndex > 0) {
        this.currentIndex--;
        this.currentPaper = this.papers[this.currentIndex];
      }
    },
    skipPaper() {
      // Skip the current paper without recording a decision.
      this.nextPaper();
    },
  };
}