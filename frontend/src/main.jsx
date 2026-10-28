import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import CodingPage from "./Coding.jsx";
import CodingHistory from "./CodingHistory.jsx";
import ErrorBoundary from "./ErrorBoundary.jsx";
import "./styles.css";
import "./resume.css";
import "./insights.css";
import "./product.css";
import "./live.css";

// /coding and /coding/history are their own pages; everything else is the main app.
const path = window.location.pathname;
const Root = path.startsWith("/coding/history") ? CodingHistory : path.startsWith("/coding") ? CodingPage : App;

createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <Root />
  </ErrorBoundary>
);

// Installable app + offline shell. Only in the production build, so development stays simple.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}