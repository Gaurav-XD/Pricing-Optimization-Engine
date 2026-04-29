/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#dde8ff',
          200: '#c3d4ff',
          500: '#4f75ff',
          600: '#3a5fea',
          700: '#2d4fd6',
          900: '#1a2f8f',
        },
      },
    },
  },
  plugins: [],
}

