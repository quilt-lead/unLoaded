/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        calcmap: {
          DEFAULT: '#14AE5C',
        },
        'calcmap-highlight': '#D2F2DF',
      },
      fontFamily: {
        sans: ['Apercu', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
};
