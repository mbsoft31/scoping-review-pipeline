/*
 * PostCSS configuration for the SRP web frontend.
 *
 * This file enables Tailwind CSS and autoprefixer to run during the Vite
 * build. The configuration exports an object that PostCSS understands,
 * instructing it to invoke both plugins. See the Tailwind documentation
 * for more information on configuring PostCSS: https://tailwindcss.com/docs/installation
 */

module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};