"use client";

import { useEffect, useMemo, useRef, useState } from "react";


export default function HopTraceMap({ sharePackage = null }) {
  // Parse share package to extract hop_trace if available
  const packageHops = useMemo(() => {
    if (!sharePackage) return null;
    try {
      const parsed = typeof sharePackage === 'string' ? JSON.parse(sharePackage) : sharePackage;
      return parsed.hop_trace || null;
    } catch {
      return null;
    }
  }, [sharePackage]);

  const [hops, setHops] = useState(() => packageHops || []);
  const [totalLatency, setTotalLatency] = useState(() =>
    (packageHops || []).reduce((acc, hop) => acc + hop.latency, 0)
  );
  const [lastTraceAt, setLastTraceAt] = useState(packageHops ? new Date() : null);
  
  // Update hops when sharePackage changes
  useEffect(() => {
    if (packageHops) {
      setHops(packageHops);
      setTotalLatency(packageHops.reduce((acc, hop) => acc + hop.latency, 0));
      setLastTraceAt(new Date());
    }
  }, [packageHops]);

  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const leafletRef = useRef(null);
  const markersRef = useRef([]);
  const polylineRef = useRef(null);
  const startIconRef = useRef(null);
  const endIconRef = useRef(null);

  useEffect(() => {
    let cleanup = () => {};
    let frameId;

    const initMap = async () => {
      if (mapRef.current) return;
      const container = containerRef.current;
      if (!container) return;
      const L = (await import("leaflet")).default;
      leafletRef.current = L;
      await import("leaflet.heat");
      const existingCss = document.querySelector(
        'link[href*="leaflet@1.9.4/dist/leaflet.css"]'
      );
      if (!existingCss) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href =
          "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(link);
      }
      L.Icon.Default.mergeOptions({
        iconRetinaUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl:
          "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      const buildSvgIcon = (fill, glow) => {
        const svg = `<?xml version="1.0" encoding="UTF-8"?>
          <svg width="40" height="60" viewBox="0 0 24 36" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="${glow}" flood-opacity="0.7" />
              </filter>
            </defs>
            <path filter="url(#shadow)" fill="${fill}" stroke="white" stroke-width="1.2" d="M12 0C6.48 0 2 4.48 2 10.02C2 17.54 11.05 24.87 11.43 25.17C11.6 25.3 11.8 25.37 12 25.37C12.2 25.37 12.4 25.3 12.57 25.17C12.95 24.87 22 17.54 22 10.02C22 4.48 17.52 0 12 0ZM12 14.37C9.59 14.37 7.63 12.41 7.63 10C7.63 7.59 9.59 5.63 12 5.63C14.41 5.63 16.37 7.59 16.37 10C16.37 12.41 14.41 14.37 12 14.37Z" />
          </svg>`;
        return L.icon({
          iconUrl: `data:image/svg+xml,${encodeURIComponent(svg)}`,
          iconSize: [40, 60],
          iconAnchor: [20, 56],
          popupAnchor: [0, -50],
          className: "hop-marker-pin",
        });
      };

      startIconRef.current = buildSvgIcon("#22c55e", "#22c55e");
      endIconRef.current = buildSvgIcon("#f87171", "#f472b6");

      const map = L.map(container, {
        center: [30, 5],
        zoom: 2.5,
        worldCopyJump: true,
        zoomControl: true,
      });
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }
      ).addTo(map);
      mapRef.current = map;

      cleanup = () => {
        map.remove();
        mapRef.current = null;
        markersRef.current = [];
        polylineRef.current = null;
      };
    };

    frameId = requestAnimationFrame(() => {
      initMap().catch(() => {});
    });
    return () => {
      if (frameId) cancelAnimationFrame(frameId);
      cleanup();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const L = leafletRef.current;
    if (!map || !L) return;

    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }
    if (!hops.length) return;

    const latlngs = hops.map((hop) => hop.coords);
    const markers = hops.map((hop, index) => {
      const isStart = index === 0;
      const isEnd = index === hops.length - 1;
      if (isStart || isEnd) {
        const icon = isStart ? startIconRef.current : endIconRef.current;
        const marker = L.marker(hop.coords, { icon })
          .addTo(map)
          .bindTooltip(
            `<strong>Hop ${index + 1}</strong><br/>${hop.name}<br/>${hop.city}`,
            { permanent: false }
          );
        marker.bindPopup(
          `<div style="font-weight:600">${hop.name}</div>
           <div style="font-size:12px">${hop.city}</div>
           <div style="font-size:12px;margin-top:4px;">Latency: ${hop.latency} ms</div>`
        );
        return marker;
      }
      const marker = L.circleMarker(hop.coords, {
        radius: 8,
        color: "#22d3ee",
        weight: 2,
        fillColor: "#22d3ee",
        fillOpacity: 0.9,
      })
        .addTo(map)
        .bindTooltip(
          `<strong>Hop ${index + 1}</strong><br/>${hop.name}<br/>${hop.city}`,
          { permanent: false }
        );
      marker.bindPopup(
        `<div style="font-weight:600">${hop.name}</div>
         <div style="font-size:12px">${hop.city}</div>
         <div style="font-size:12px;margin-top:4px;">Latency: ${hop.latency} ms</div>`
      );
      return marker;
    });
    markersRef.current = markers;

    const polyline = L.polyline(latlngs, {
      color: "#22c55e",
      weight: 4,
      opacity: 0.9,
      dashArray: "4, 6",
    }).addTo(map);
    polylineRef.current = polyline;
    try {
      map.fitBounds(polyline.getBounds(), { padding: [30, 30] });
    } catch {
      // ignore
    }
  }, [hops]);

  if (!hops || hops.length === 0) {
    return null;
  }

  return (
    <section className="min-w-0 max-w-full overflow-hidden rounded-3xl border border-white/10 bg-slate-900/80 p-4 shadow-2xl shadow-black/40 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] uppercase tracking-[0.4em] text-emerald-300">
            Intelligence sharing route
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            Package hop trace
          </h2>
          <p className="text-sm text-slate-400">
            Visualise the relay path this intelligence package takes through the mesh before reaching the destination SOC.
          </p>
        </div>
        {lastTraceAt && (
          <div className="rounded-2xl border border-white/10 bg-slate-900/70 px-4 py-3 text-xs text-slate-400">
            <p className="uppercase tracking-[0.3em] text-slate-500">Generated</p>
            <p className="mt-2 font-mono text-[11px] text-emerald-200">
              {lastTraceAt.toLocaleTimeString()}
            </p>
          </div>
        )}
      </div>

      <div className="mt-6 grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(16rem,0.85fr)]">
        <div
          ref={containerRef}
          style={{ height: 420, borderRadius: 18, overflow: "hidden" }}
          className="min-w-0 w-full bg-white"
        />

        <div className="min-w-0 space-y-3">
          <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-sm text-slate-300">
            Estimated travel time:{" "}
            <span className="font-semibold text-white">
              ~{totalLatency} ms
            </span>
          </div>
          {hops.map((hop, index) => (
            <article
              key={hop.id}
              className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-4"
            >
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Hop {index + 1}</span>
                <span className="font-semibold text-emerald-200">
                  {hop.latency} ms
                </span>
              </div>
              <p className="mt-2 text-base font-semibold text-white">
                {hop.name}
              </p>
              <p className="break-words text-sm text-slate-300">
                {hop.city} · {hop.ip}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {hop.provider}
              </p>
              <p className="mt-2 text-xs text-slate-400">{hop.note}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
