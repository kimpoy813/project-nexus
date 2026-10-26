import { AbsoluteFill, staticFile } from "remotion";

// Inter ships with @fontsource/inter; scripts/sync-fonts.mjs copies the
// woff2 files into public/fonts. Declaring them here keeps rendering
// completely offline (no fonts.googleapis.com request).
const faces = [400, 500, 600, 700, 800]
  .map(
    (w) => `
  @font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: ${w};
    font-display: block;
    src: url('${staticFile(`fonts/inter-latin-${w}-normal.woff2`)}') format('woff2');
  }`
  )
  .join("\n");

export const Fonts = () => (
  <AbsoluteFill>
    <style>{faces}</style>
  </AbsoluteFill>
);
