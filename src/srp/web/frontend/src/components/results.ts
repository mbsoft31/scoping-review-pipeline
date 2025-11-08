/**
 * Results browser component for the SRP web UI.
 *
 * This Alpine.js component manages tabs for Phase 1 and Phase 2
 * directories, displays modal dialogs for viewing papers and
 * delegates navigation to citation network and seminal paper pages.
 */
export function resultsApp() {
  return {
    activeTab: 'phase1',
    phase1Dirs: [] as string[],
    phase2Dirs: [] as string[],
    showPapersModal: false,
    currentPath: null as string | null,
    init() {
      // Phase directory arrays are injected by the server-side template
    },
    viewPapers(path: string) {
      this.currentPath = path;
      this.showPapersModal = true;
      // Defer HTMX attribute updates until the next tick
      setTimeout(() => {
        const container = document.getElementById('papers-container');
        if (!container) return;
        container.setAttribute('hx-get', `/api/results/${path}/papers?page=1`);
        // Trigger HTMX processing if it is available
        const htmx = (window as any).htmx;
        if (htmx) {
          htmx.process(container);
          htmx.trigger(container, 'load');
        }
      }, 100);
    },
    viewSeminalPapers(path: string) {
      window.location.href = `/results/${path}/seminal`;
    },
    viewNetwork(path: string) {
      window.location.href = `/results/${path}/network`;
    },
    async exportBibtex(path: string, topN: number | null = null) {
      try {
        const url = `/api/export/${path}/bibtex` + (topN ? `?top_n=${topN}` : '');
        const response = await fetch(url, { method: 'POST' });
        const data = await response.json();
        alert(`BibTeX exported to: ${data.path}`);
      } catch (error: any) {
        alert('Export failed: ' + error.message);
      }
    },
  };
}