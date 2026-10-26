// NExUS brand tokens — kept in sync with accounts/ui.py BRAND_DEFAULTS
// and templates/partials/_theme.html in the Django application.
export const COLORS = {
  primary: "#103b07", // deep institutional green
  primaryBright: "#1f6b12",
  primarySoft: "rgba(31, 107, 18, 0.22)",
  primaryLine: "rgba(166, 224, 132, 0.28)",
  secondary: "#5a1113", // maroon
  accent: "#f5e587", // soft yellow
  accentDeep: "#e6cf5b",
  paper: "#f7f8f2", // light "browser window" background
  ink: "#16220f", // text on light surfaces
  muted: "#5d6b55",
  line: "#dde3d4",
  white: "#ffffff",
  rose: "#b4453f",
  blue: "#3a6ea5",
};

export const FONT = {
  stack:
    'Inter, "Segoe UI", Roboto, Helvetica, Arial, system-ui, sans-serif',
  weights: { regular: 400, medium: 500, semibold: 600, bold: 700, extra: 800 },
};

// 1920x1080 canvas, 30 fps.
export const VIDEO = { width: 1920, height: 1080, fps: 30 };
