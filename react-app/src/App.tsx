import React from 'react';
import { Outlet, Link } from '@tanstack/react-router';

/**
 * Root layout for the React demo app.  This component renders a
 * navigation bar and an ``Outlet`` where nested routes are rendered.
 */
const App: React.FC = () => {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <header className="bg-blue-600 text-white p-4">
        <div className="container mx-auto flex items-center justify-between">
          <h1 className="text-xl font-bold">React Demo</h1>
          <nav className="space-x-4 text-sm">
            <Link to="/" className="hover:underline">
              Home
            </Link>
            <Link to="/search" className="hover:underline">
              Search
            </Link>
            <Link to="/results" className="hover:underline">
              Results
            </Link>
            <Link to="/analyze" className="hover:underline">
              Analyze
            </Link>
            <Link to="/extraction" className="hover:underline">
              Extract
            </Link>
            <Link to="/quality" className="hover:underline">
              Quality
            </Link>
            <Link to="/screening" className="hover:underline">
              Screening
            </Link>
            <Link to="/review" className="hover:underline">
              Review
            </Link>
            <Link to="/meta" className="hover:underline">
              Meta
            </Link>
            <Link to="/prisma" className="hover:underline">
              PRISMA
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1 container mx-auto p-6">
        {/* Render child routes */}
        <Outlet />
      </main>
      <footer className="bg-gray-200 text-center p-4">
        <p className="text-sm text-gray-600">© {new Date().getFullYear()} SRP Demo</p>
      </footer>
    </div>
  );
};

export default App;