/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './core/templates/**/*.html',
    './trips/templates/**/*.html',
    './expenses/templates/**/*.html',
    './ledger/templates/**/*.html',
    './authentication/templates/**/*.html',
    './customers/templates/**/*.html',
    './vehicles/templates/**/*.html',
    './labour/templates/**/*.html',
    './master_data/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef7f5',
          100: '#d5ebe6',
          500: '#16665a',
          600: '#115248',
          700: '#0d423a',
        }
      }
    },
  },
  safelist: ['opacity-60', 'hidden'],
  plugins: [],
}
