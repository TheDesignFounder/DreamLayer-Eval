// src/components/GenerateReportButton.jsx
import React, { useState } from "react";

/**
 * props:
 * - frontendSettings: object like { run_001: { prompt, seed, sampler }, ... }
 * - className: optional CSS classes (reuse your "Generate Images" classes)
 * - apiUrl: optional backend url (default http://localhost:8000/generate_report)
 */
export default function GenerateReportButton({
  frontendSettings = null,
  getFrontendSettings = null,
  className = "",
  apiUrl = "http://localhost:8000/generate_report",
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // helper to get settings either from prop or by calling a function passed from parent
  const resolveSettings = () => {
    if (typeof getFrontendSettings === "function") return getFrontendSettings();
    return frontendSettings;
  };

  const handleClick = async () => {
    setLoading(true);
    setError(null);

    try {
      const settings = resolveSettings();
      if (!settings || Object.keys(settings).length === 0) {
        throw new Error("No frontend settings provided. Pass frontendSettings or getFrontendSettings.");
      }

      const res = await fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `Server responded ${res.status}`);
      }

      // response is a zip file — download it
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "report.zip";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("GenerateReport error:", err);
      setError(err.message || "Failed to generate report");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        className={`generate-images-like-button ${className}`}
        onClick={handleClick}
        disabled={loading}
      >
        {loading ? "Generating..." : "Generate Report"}
      </button>
      {error && <div style={{ color: "crimson", marginTop: 8 }}>{error}</div>}
    </div>
  );
}
