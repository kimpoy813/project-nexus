const font = ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'Arial', 'sans-serif'];
module.exports = {
  content: ['../templates/**/*.html', '../accounts/templates/**/*.html', '../details/templates/**/*.html', '../proposals/templates/**/*.html', '../static/js/*.js', '../accounts/forms.py', '../proposals/*forms.py'],
  theme: { extend: {
    colors: {
      primary: 'rgb(var(--nexus-primary-rgb, 16 59 7) / <alpha-value>)',
      secondary: 'rgb(var(--nexus-secondary-rgb, 90 17 19) / <alpha-value>)',
      accent: 'rgb(var(--nexus-accent-rgb, 245 229 135) / <alpha-value>)',
      forest: 'rgb(var(--nexus-primary-rgb, 16 59 7) / <alpha-value>)',
      maroon: 'rgb(var(--nexus-secondary-rgb, 90 17 19) / <alpha-value>)',
      gold: '#e8c31e', cream: '#fdf9e3',
    },
    fontFamily: { sans: font, serif: font, mono: font },
    boxShadow: { nexus: '0 16px 40px rgba(15, 23, 42, 0.08)' },
  } },
};
