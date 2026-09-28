/* Django's Tailwind build: same palette and type as static/css/nexus-ui.css.
   Compile from frontend/ with `npm run build:django-css` after changing
   template utility classes. CSS variables keep admin-configurable branding. */
const token = (name) => ({ opacityValue } = {}) => {
  if (opacityValue === undefined) return `var(${name})`;
  // Tailwind passes a CSS custom property for an unsuffixed class and a
  // numeric string for slash opacity (e.g. bg-primary/10). Both are valid.
  const percent = /^\d*\.?\d+$/.test(opacityValue)
    ? `${Number(opacityValue) * 100}%`
    : `calc(${opacityValue} * 100%)`;
  return `color-mix(in srgb, var(${name}) ${percent}, transparent)`;
};

module.exports = {
  content: [
    '../templates/**/*.html',
    '../accounts/templates/**/*.html',
    '../details/templates/**/*.html',
    '../proposals/templates/**/*.html',
    '../static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        primary: token('--nexus-primary'),
        secondary: token('--nexus-secondary'),
        accent: token('--nexus-accent'),
        tertiary: token('--nexus-bg-2'),
        gold: '#e8c31e',
        cream: '#fdf9e3',
        maroon: token('--nexus-secondary'),
        forest: token('--nexus-primary'),
      },
      fontFamily: {
        sans: ['Public Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['Manrope', 'Public Sans', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        nexus: '0 12px 30px -20px rgba(20, 53, 28, .3)',
      },
    },
  },
  // Some chips/tabs are assembled from server-driven statuses in JS. Their
  // semantic palette must remain available even if a literal class is absent.
  safelist: [
    { pattern: /^(bg|text|border)-(primary|secondary|green|red|amber|blue|purple|gray)-(50|100|200|300|400|500|600|700|800|900)$/ },
  ],
};
