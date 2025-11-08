import React from 'react';
import { createBrowserRouter } from '@tanstack/react-router';
import App from './App';
// Import SRP UI pages
import Dashboard from './pages/Dashboard';
import Search from './pages/Search';
import Results from './pages/Results';
import Analyze from './pages/Analyze';
import Extraction from './pages/Extraction';
import Quality from './pages/Quality';
import Screening from './pages/Screening';
import Review from './pages/Review';
import Meta from './pages/Meta';
import Prisma from './pages/Prisma';

/*
 * Application routes for the SRP React front‑end.  The root route renders
 * ``App`` which defines the layout (header, footer and Outlet).  Nested
 * routes correspond to functional pages such as search, analysis,
 * extraction, quality assessment, screening, review, meta‑analysis and
 * PRISMA diagram generation.  This router uses TanStack Router to
 * declaratively define the navigation structure.
 */

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: '/',
        element: <Dashboard />, // Landing page
      },
      {
        path: '/search',
        element: <Search />, // Phase 1 search
      },
      {
        path: '/results',
        element: <Results />, // Results browser
      },
      {
        path: '/analyze',
        element: <Analyze />, // Phase 2 analysis
      },
      {
        path: '/extraction',
        element: <Extraction />, // Data extraction
      },
      {
        path: '/quality',
        element: <Quality />, // Risk‑of‑bias assessment
      },
      {
        path: '/screening',
        element: <Screening />, // AI‑assisted screening
      },
      {
        path: '/review',
        element: <Review />, // Human review queue
      },
      {
        path: '/meta',
        element: <Meta />, // Meta‑analysis configuration
      },
      {
        path: '/prisma',
        element: <Prisma />, // PRISMA diagram generation
      },
    ],
  },
]);