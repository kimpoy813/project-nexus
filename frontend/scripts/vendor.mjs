// Checked-in runtime assets keep Python-only deployments independent of CDNs/Node.
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
const destination = resolve('../static/vendor');
mkdirSync(destination, { recursive: true });
const assets = {
  'alpinejs/dist/cdn.min.js': 'alpine.min.js',
  'aos/dist/aos.js': 'aos.js', 'aos/dist/aos.css': 'aos.css',
  'chart.js/dist/chart.umd.js': 'chart.umd.js',
  'sortablejs/Sortable.min.js': 'sortable.min.js',
};
for (const [source, target] of Object.entries(assets)) {
  const text = readFileSync(resolve('node_modules', source), 'utf8').replace(/\/\/# sourceMappingURL=.*$/gm, '');
  writeFileSync(resolve(destination, target), text);
}
const licenses = ['## alpinejs\n\n' + readFileSync(resolve('licenses/alpinejs.txt'), 'utf8')];
for (const [pkg, file] of [['aos','LICENSE'], ['chart.js','LICENSE.md'], ['sortablejs','LICENSE'], ['@fontsource/inter','LICENSE']]) {
  licenses.push(`\n## ${pkg}\n\n${readFileSync(resolve('node_modules', pkg, file), 'utf8')}`);
}
writeFileSync(resolve(destination, 'LICENSES.txt'), licenses.join('\n'));
let fonts = '';
for (const weight of [400, 500, 600, 700, 800, 900]) {
  const name = `inter-latin-${weight}-normal.woff2`;
  copyFileSync(resolve('node_modules/@fontsource/inter/files', name), resolve(destination, name));
  fonts += `@font-face{font-family:Inter;font-style:normal;font-weight:${weight};font-display:swap;src:url('./${name}') format('woff2')}\n`;
}
writeFileSync(resolve(destination, 'fonts.css'), fonts);
