"use client";

import { useState } from "react";

export default function ImageAnalyzer({ variant = "dark" }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const featureDefaults = {
    genai: true, // AI-generated detection (default ON)
    violence: false,
    gore: false,
    offensive: false,
    selfHarm: false,
    text: false,
    qr: false,
    properties: false,
  };

  // Feature toggles configure requested signal set
  const [features, setFeatures] = useState(() => ({ ...featureDefaults }));
  // Snapshot of features applied on the last analysis run
  const [activeFeatures, setActiveFeatures] = useState(() => ({ ...featureDefaults }));

  const toggleFeature = (key) => {
    setFeatures(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setPreview(URL.createObjectURL(file));
      setResults(null);
      setError(null);
    }
  };

  const analyzeImage = async () => {
    if (!selectedFile) return;

    setAnalyzing(true);
    setError(null);

    const enabledModels = [];
    if (features.genai) enabledModels.push("genai");
    if (features.violence) enabledModels.push("violence");
    if (features.gore) enabledModels.push("gore-2.0");
    if (features.offensive) enabledModels.push("offensive-2.0");
    if (features.selfHarm) enabledModels.push("self-harm");
    if (features.text) enabledModels.push("text-content");
    if (features.qr) enabledModels.push("qr-content");
    if (features.properties) enabledModels.push("properties");

    if (enabledModels.length === 0) {
      setError("Select at least one detection feature before analyzing.");
      setResults(null);
      setAnalyzing(false);
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("models", enabledModels.join(","));

    try {
      const response = await fetch("http://localhost:8000/api/v1/image/analyze", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const data = await response.json();
      setActiveFeatures({ ...features });
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const isSimple = variant === "simple";
  const isLight = variant === "light" || isSimple;
  const containerClass = isSimple
    ? "space-y-5"
    : isLight
    ? "rounded-[28px] border border-slate-200 bg-white px-6 py-5 shadow-xl shadow-slate-200/80"
    : "rounded-2xl border border-white/10 bg-slate-950/60 px-6 py-5";
  const headingClass = isLight
    ? "text-2xl font-semibold text-slate-900"
    : "text-2xl font-semibold text-white";
  const subHeadingClass = isLight
    ? "text-sm text-slate-600"
    : "text-sm text-slate-400";
  const chooseButtonClass = isLight
    ? "inline-flex min-h-11 cursor-pointer items-center rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 focus-within:ring-4 focus-within:ring-blue-100"
    : "cursor-pointer rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm font-semibold text-cyan-300 hover:bg-cyan-500/20";
  const togglesContainerClass = isLight
    ? "rounded-2xl border border-slate-200 bg-slate-50/80 p-4"
    : "rounded-lg border border-white/10 bg-slate-900/40 p-4";
  const toggleTitleClass = isLight
    ? "mb-3 text-sm font-semibold text-slate-800"
    : "mb-3 text-sm font-semibold text-white";
  const toggleInactiveClass = isLight
    ? "border-slate-200 bg-white text-slate-500 hover:border-slate-300"
    : "border-white/10 bg-slate-800/50 text-slate-400 hover:border-white/20";
  const featureActiveClasses = {
    genai: isLight
      ? "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700"
      : "border-fuchsia-500/50 bg-fuchsia-500/20 text-fuchsia-300",
    violence: isLight
      ? "border-amber-200 bg-amber-50 text-amber-700"
      : "border-amber-500/50 bg-amber-500/20 text-amber-300",
    gore: isLight
      ? "border-rose-200 bg-rose-50 text-rose-700"
      : "border-rose-500/50 bg-rose-500/20 text-rose-300",
    offensive: isLight
      ? "border-orange-200 bg-orange-50 text-orange-700"
      : "border-orange-500/50 bg-orange-500/20 text-orange-300",
    selfHarm: isLight
      ? "border-red-200 bg-red-50 text-red-700"
      : "border-red-500/50 bg-red-500/20 text-red-300",
    text: isLight
      ? "border-cyan-200 bg-cyan-50 text-cyan-700"
      : "border-cyan-500/50 bg-cyan-500/20 text-cyan-300",
    qr: isLight
      ? "border-blue-200 bg-blue-50 text-blue-700"
      : "border-blue-500/50 bg-blue-500/20 text-blue-300",
    properties: isLight
      ? "border-slate-200 bg-slate-50 text-slate-700"
      : "border-slate-500/50 bg-slate-500/20 text-slate-300",
  };
  const previewBorderClass = isLight ? "border border-slate-200" : "border border-white/10";
  const errorClass = isLight
    ? "rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
    : "rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300";
  const resultsContainerClass = isLight
    ? "space-y-4 rounded-2xl border border-slate-200 bg-slate-50 p-4"
    : "space-y-4 rounded-xl border border-white/10 bg-slate-900/60 p-4";
  const resultsHeadingClass = isLight
    ? "text-lg font-semibold text-slate-900"
    : "text-lg font-semibold text-white";
  const progressTrackClass = isLight ? "mt-2 h-2 overflow-hidden rounded-full bg-slate-200" : "mt-2 h-2 overflow-hidden rounded-full bg-slate-800";
  const getRiskLevel = (prob) => {
    if (prob >= 0.7) return { label: "HIGH", color: isLight ? "text-rose-600" : "text-rose-400" };
    if (prob >= 0.4) return { label: "MEDIUM", color: isLight ? "text-amber-600" : "text-amber-400" };
    return { label: "LOW", color: isLight ? "text-emerald-600" : "text-emerald-400" };
  };

  const offensiveScore = results?.offensive
    ? Math.min(
        1,
        Object.values(results.offensive)
          .filter((val) => typeof val === "number")
          .reduce((sum, val) => sum + val, 0)
      )
    : null;

  const hasPropertiesData = results
    ? results.sharpness !== undefined ||
      results.brightness !== undefined ||
      results.contrast !== undefined ||
      Boolean(results.colors?.dominant) ||
      Boolean(results.media)
    : false;

  return (
    <div className={containerClass}>
      <header className={`mb-5 ${isSimple ? "sr-only" : ""}`}>
        <h2 className={headingClass}>Image Content Analyzer</h2>
        <p className={`mt-1 ${subHeadingClass}`}>
          Detect AI-generated images, gore, violence, offensive content, and more
        </p>
      </header>

      <div className="space-y-4">
        {/* File Upload */}
        <div className={`flex items-center gap-4 ${isSimple ? "rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50 px-4 py-6" : ""}`}>
          <label
            htmlFor="image-upload"
            className={chooseButtonClass}
          >
            Choose Image
          </label>
          <input
            id="image-upload"
            type="file"
            accept="image/*"
            onChange={handleFileSelect}
            className="hidden"
          />
          {selectedFile && (
            <span className={`text-sm ${isLight ? "text-slate-600" : "text-slate-400"}`}>
              {selectedFile.name}
            </span>
          )}
        </div>

        {/* Feature Toggles */}
        <div className={togglesContainerClass}>
          <h3 className={toggleTitleClass}>Detection Features</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {/* AI Detection - Default ON */}
            <button
              onClick={() => toggleFeature("genai")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.genai ? featureActiveClasses.genai : toggleInactiveClass
              }`}
            >
              <span className="block"> AI Detection</span>
            </button>

            {/* Violence */}
            <button
              onClick={() => toggleFeature("violence")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.violence
                  ? featureActiveClasses.violence
                  : toggleInactiveClass
              }`}
            >
              <span className="block"> Violence</span>
            </button>

            {/* Gore */}
            <button
              onClick={() => toggleFeature("gore")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.gore ? featureActiveClasses.gore : toggleInactiveClass
              }`}
            >
              <span className="block"> Gore</span>
            </button>

            {/* Offensive */}
            <button
              onClick={() => toggleFeature("offensive")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.offensive
                  ? featureActiveClasses.offensive
                  : toggleInactiveClass
              }`}
            >
              <span className="block"> Offensive</span>
            </button>

            {/* Self-Harm */}
            <button
              onClick={() => toggleFeature("selfHarm")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.selfHarm
                  ? featureActiveClasses.selfHarm
                  : toggleInactiveClass
              }`}
            >
              <span className="block"> Self-Harm</span>
            </button>

            {/* Text */}
            <button
              onClick={() => toggleFeature("text")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.text ? featureActiveClasses.text : toggleInactiveClass
              }`}
            >
              <span className="block"> Text</span>
            </button>

            {/* QR Code */}
            <button
              onClick={() => toggleFeature("qr")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.qr ? featureActiveClasses.qr : toggleInactiveClass
              }`}
            >
              <span className="block"> QR Code</span>
            </button>

            {/* Properties */}
            <button
              onClick={() => toggleFeature("properties")}
              className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${
                features.properties
                  ? featureActiveClasses.properties
                  : toggleInactiveClass
              }`}
            >
              <span className="block"> Properties</span>
            </button>
          </div>
        </div>

        {/* Image Preview */}
        {preview && (
          <div className="relative">
            <img
              src={preview}
              alt="Preview"
              className={`max-h-64 rounded-lg ${previewBorderClass}`}
            />
          </div>
        )}

        {/* Analyze Button */}
        {selectedFile && (
          <button
            onClick={analyzeImage}
            disabled={analyzing}
            className={isSimple
              ? "w-full rounded-xl bg-blue-700 px-6 py-3 font-semibold text-white shadow-lg shadow-blue-900/10 transition hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-200 disabled:opacity-50"
              : "rounded-lg bg-gradient-to-r from-green-600 to-blue-600 px-6 py-2.5 font-semibold text-white hover:from-blue-700 hover:to-green-700 disabled:opacity-50"}
          >
            {analyzing ? "Analyzing..." : "Analyze Image"}
          </button>
        )}

        {/* Error */}
        {error && (
          <div className={errorClass}>
            ⚠️ {error}
          </div>
        )}

        {/* Results */}
        {results && (
          <div className={resultsContainerClass}>
            <h3 className={resultsHeadingClass}>Analysis Results</h3>

            {/* AI Generation Detection */}
            {activeFeatures.genai && results.type?.ai_generated !== undefined && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-fuchsia-200 bg-fuchsia-50"
                    : "border-fuchsia-500/30 bg-fuchsia-500/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-medium ${
                      isLight ? "text-fuchsia-700" : "text-fuchsia-300"
                    }`}
                  >
                    AI-Generated Probability
                  </span>
                  <span
                    className={`text-lg font-bold ${getRiskLevel(results.type.ai_generated).color}`}
                  >
                    {(results.type.ai_generated * 100).toFixed(1)}%
                  </span>
                </div>
                <div className={progressTrackClass}>
                  <div
                    className="h-full bg-gradient-to-r from-fuchsia-500 to-purple-500"
                    style={{ width: `${results.type.ai_generated * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Gore Detection */}
            {activeFeatures.gore && results.gore?.prob !== undefined && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-rose-200 bg-rose-50"
                    : "border-rose-500/30 bg-rose-500/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-medium ${
                      isLight ? "text-rose-700" : "text-rose-300"
                    }`}
                  >
                    Gore Content
                  </span>
                  <span className={`text-lg font-bold ${getRiskLevel(results.gore.prob).color}`}>
                    {(results.gore.prob * 100).toFixed(1)}%
                  </span>
                </div>
                <div className={progressTrackClass}>
                  <div
                    className="h-full bg-rose-500"
                    style={{ width: `${results.gore.prob * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Violence Detection */}
            {activeFeatures.violence && results.violence?.prob !== undefined && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-amber-200 bg-amber-50"
                    : "border-amber-500/30 bg-amber-500/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-medium ${
                      isLight ? "text-amber-700" : "text-amber-300"
                    }`}
                  >
                    Violence Content
                  </span>
                  <span className={`text-lg font-bold ${getRiskLevel(results.violence.prob).color}`}>
                    {(results.violence.prob * 100).toFixed(1)}%
                  </span>
                </div>
                <div className={progressTrackClass}>
                  <div
                    className="h-full bg-amber-500"
                    style={{ width: `${results.violence.prob * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Offensive Content */}
            {activeFeatures.offensive && offensiveScore !== null && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-orange-200 bg-orange-50"
                    : "border-orange-500/30 bg-orange-500/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-medium ${
                      isLight ? "text-orange-700" : "text-orange-300"
                    }`}
                  >
                    Offensive Content Score
                  </span>
                  <span className={`text-lg font-bold ${getRiskLevel(offensiveScore).color}`}>
                    {(offensiveScore * 100).toFixed(1)}%
                  </span>
                </div>
                <div className={progressTrackClass}>
                  <div
                    className="h-full bg-orange-500"
                    style={{ width: `${Math.min(offensiveScore * 100, 100)}%` }}
                  />
                </div>
              </div>
            )}

            {/* Self-Harm Detection */}
            {activeFeatures.selfHarm && results.self_harm?.prob !== undefined && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-red-200 bg-red-50"
                    : "border-red-500/30 bg-red-500/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`text-sm font-medium ${
                      isLight ? "text-red-700" : "text-red-300"
                    }`}
                  >
                    Self-Harm Content
                  </span>
                  <span className={`text-lg font-bold ${getRiskLevel(results.self_harm.prob).color}`}>
                    {(results.self_harm.prob * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            {/* Text Content */}
            {activeFeatures.text && results.text && Object.keys(results.text).length > 0 && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-cyan-200 bg-cyan-50"
                    : "border-cyan-500/30 bg-cyan-500/10"
                }`}
              >
                <span
                  className={`text-sm font-medium ${
                    isLight ? "text-cyan-700" : "text-cyan-300"
                  }`}
                >
                  Detected Text Categories
                </span>
                <div className="mt-2 space-y-1">
                  {Object.entries(results.text).map(([category, matches]) => (
                    matches.length > 0 && (
                      <div key={category} className="text-xs">
                        <span className={`font-semibold capitalize ${isLight ? "text-cyan-700" : "text-cyan-200"}`}>
                          {category}:{" "}
                        </span>
                        <span className={isLight ? "text-cyan-700/70" : "text-cyan-100/70"}>
                          {matches.map((m) => m.match || m).join(", ")}
                        </span>
                      </div>
                    )
                  ))}
                  {Object.values(results.text).every(arr => arr.length === 0) && (
                    <p className={`text-xs italic ${isLight ? "text-cyan-600/60" : "text-cyan-200/50"}`}>
                      No text issues detected
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* QR Code */}
            {activeFeatures.qr && results.qr && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-blue-200 bg-blue-50"
                    : "border-blue-500/30 bg-blue-500/10"
                }`}
              >
                <span
                  className={`text-sm font-medium ${
                    isLight ? "text-blue-700" : "text-blue-300"
                  }`}
                >
                  QR Code Analysis
                </span>
                <div className="mt-2 space-y-1">
                   {Object.entries(results.qr).map(([category, matches]) => (
                    matches.length > 0 && (
                      <div key={category} className="text-xs">
                        <span className={`font-semibold capitalize ${isLight ? "text-blue-700" : "text-blue-200"}`}>
                          {category}:{" "}
                        </span>
                        <span className={isLight ? "text-blue-700/70" : "text-blue-100/70"}>
                          {matches.map((m) => m.url || m).join(", ")}
                        </span>
                      </div>
                    )
                  ))}
                  {Object.values(results.qr).every(arr => arr.length === 0) && (
                    <p className={`text-xs italic ${isLight ? "text-blue-600/60" : "text-blue-200/50"}`}>
                      No QR codes detected
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Image Properties */}
            {activeFeatures.properties && hasPropertiesData && (
              <div
                className={`rounded-lg border p-3 ${
                  isLight
                    ? "border-slate-200 bg-white"
                    : "border-slate-500/30 bg-slate-500/10"
                }`}
              >
                <span
                  className={`text-sm font-medium ${
                    isLight ? "text-slate-800" : "text-slate-300"
                  }`}
                >
                  Image Properties
                </span>
                <div
                  className={`mt-2 grid grid-cols-2 gap-2 text-xs ${
                    isLight ? "text-slate-600" : "text-slate-400"
                  }`}
                >
                  {results.sharpness !== undefined && (
                    <div>
                      Sharpness:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {(results.sharpness * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {results.brightness !== undefined && (
                    <div>
                      Brightness:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {(results.brightness * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {results.contrast !== undefined && (
                    <div>
                      Contrast:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {(results.contrast * 100).toFixed(0)}%
                      </span>
                    </div>
                  )}
                  {results.colors?.dominant && (
                    <div className="flex items-center gap-2">
                      Dominant: 
                      <span 
                        className={`inline-block h-3 w-3 rounded-full border ${
                          isLight ? "border-slate-200" : "border-white/20"
                        }`}
                        style={{ backgroundColor: results.colors.dominant.hex }}
                      />
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {results.colors.dominant.hex}
                      </span>
                    </div>
                  )}
                  {results.media?.width && (
                    <div>
                      Width:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {results.media.width}px
                      </span>
                    </div>
                  )}
                  {results.media?.height && (
                    <div>
                      Height:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {results.media.height}px
                      </span>
                    </div>
                  )}
                  {results.media?.format && (
                    <div>
                      Format:{" "}
                      <span className={isLight ? "text-slate-800" : "text-slate-300"}>
                        {results.media.format}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

      
          </div>
        )}
      </div>
    </div>
  );
}
