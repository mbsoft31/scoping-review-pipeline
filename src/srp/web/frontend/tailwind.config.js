/*
 * Tailwind CSS configuration for the SRP web frontend.
 *
 * Tailwind scans the template and frontend source directories to generate
 * the appropriate utility classes at build time. You can extend the
 * configuration by adding themes, plugins, or additional paths. The
 * ``content`` array below includes the Jinja templates so that class
 * names used in HTML templates are included in the compiled output.
 */

module.exports = {
  content: [
    // Vite's index.html and all TS/JS/TSX/JSX files in the frontend
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
    // Scan Jinja templates for Tailwind classes
    '../templates/**/*.html',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};