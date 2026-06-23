import React from "react";
import ReactDOM from "react-dom/client";
import { GooeyToaster, gooeyToast } from "goey-toast";
import "goey-toast/styles.css";

window.goeyToast = gooeyToast;

const el = document.getElementById("goey-toast-root");
if (el) {
  ReactDOM.createRoot(el).render(
    <React.StrictMode>
      <GooeyToaster position="top-right" showProgress preset="smooth" />
    </React.StrictMode>
  );
} else {
  // Prevent React error #299 on pages that don't include the mount div
  console.warn("goey-toast: mount div #goey-toast-root not found on this page");
}