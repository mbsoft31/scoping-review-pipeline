/**
 * Entry point for the SRP frontend build.
 *
 * This module imports Alpine.js and the individual component
 * factories (dashboard, resultsApp, analyzeApp).  It attaches
 * these factories to the global `window` so that Alpine can
 * initialise them in the HTML templates.  Finally, it starts
 * Alpine.
 */
import Alpine from 'alpinejs';

// Import global styles.  The Tailwind directives in ``styles.css`` are
// processed by PostCSS during the build, producing a compiled CSS
// bundle.  Without this import, Tailwind styles will not be applied
// to your templates.  See ``styles.css`` for details.
import './styles.css';
import { dashboard } from './components/dashboard';
import { resultsApp } from './components/results';
import { analyzeApp } from './components/analyze';
import { extractionApp } from './components/extraction';
import { qualityApp } from './components/quality';
import { screeningApp } from './components/screening';
import { reviewApp } from './components/review';
import { metaApp } from './components/meta';
import { prismaApp } from './components/prisma';

// Import htmx and Chart.js from npm to replace CDN imports.  Importing
// htmx attaches the global `htmx` object to ``window``; Chart.js
// exports a factory that registers itself on import.  These imports
// ensure that the Vite build includes the libraries and that they
// become available globally at runtime.
import 'htmx.org';
import Chart from 'chart.js/auto';

// Expose Chart on the window so legacy code can access ``window.Chart``.
(window as any).Chart = Chart;

// Expose component factories globally for Alpine
// Expose component factories globally for Alpine
(window as any).dashboard = dashboard;
(window as any).resultsApp = resultsApp;
(window as any).analyzeApp = analyzeApp;
(window as any).extractionApp = extractionApp;
(window as any).qualityApp = qualityApp;
(window as any).screeningApp = screeningApp;
(window as any).reviewApp = reviewApp;
(window as any).metaApp = metaApp;
(window as any).prismaApp = prismaApp;

// Start Alpine.js
Alpine.start();