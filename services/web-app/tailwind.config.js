/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'dd-purple': '#632CA6',
        'hippo-gold': '#F5A623',
      },
    },
  },
  plugins: [],
};
