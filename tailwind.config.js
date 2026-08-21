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
          200: '#aed8cf',
          300: '#7fbcb0',
          400: '#4a9c8c',
          500: '#16665a',
          600: '#115248',
          700: '#0d423a',
          800: '#09312b',
          900: '#06211d',
          DEFAULT: '#16665a',
        },
        ink: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        accent: {
          amber: '#d97706',
          soft: '#fef3c7',
        },
      },
      fontFamily: {
        sans: ['"Fira Sans"', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"Fira Code"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)',
        'card-hover': '0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04)',
        fab: '0 8px 24px rgba(22, 102, 90, 0.35)',
        nav: '0 -1px 0 rgba(15, 23, 42, 0.05), 0 -4px 16px rgba(15, 23, 42, 0.03)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'scale-in': {
          '0%': { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        'sheet-up': {
          '0%': { transform: 'translateY(100%)' },
          '100%': { transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.45s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 0.3s ease both',
        'scale-in': 'scale-in 0.3s cubic-bezier(0.22, 1, 0.36, 1) both',
        'sheet-up': 'sheet-up 0.28s cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  safelist: ['opacity-60', 'hidden'],
  plugins: [],
}
