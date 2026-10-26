// All Remotion CLI commands read this file.
// See https://www.remotion.dev/docs/config
import { Config } from "@remotion/cli/config";
import { join } from "node:path";
import { existsSync } from "node:fs";

Config.setVideoImageFormat("jpeg");
Config.setOverwriteOutput(true);
// Keep the renderer polite on small machines; override per command with --concurrency.
Config.setConcurrency(2);

// Headless Chromium assembled by scripts/prepare-browser.mjs (offline-friendly
// fallback for sandboxes that cannot reach remotion.media). On a normal
// machine you can delete these four lines and run `npx remotion browser ensure`.
// Remotion evaluates this config with CWD set to the project root.
const here = process.cwd();
const browserWrapper = join(here, ".browser", "chromium", "chrome-wrapper");
if (existsSync(browserWrapper)) {
  Config.setBrowserExecutable(browserWrapper);
  // Full Chromium (not headless-shell) => --headless=new, which works here.
  Config.setChromeMode("chrome-for-testing");
  // Software GL via SwiftShader-on-ANGLE: no GPU/display libraries required.
  Config.setChromiumOpenGlRenderer("swangle");
  // --single-process deadlocks in this container; use the multi-process model.
  Config.setChromiumMultiProcessOnLinux(true);
}
