/*
 * Tailwind configuration for the React demo app.  The ``content`` array
 * determines which files Tailwind scans for class names.  It includes
 * all TypeScript/TSX and HTML files in the ``src`` directory.  You can
 * extend the configuration to customise your design system.
 */

module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};