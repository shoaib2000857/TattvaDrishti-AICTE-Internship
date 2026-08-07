const nodes = [
  [50, 7, 2.1], [75, 17, 1.6], [91, 39, 1.8], [86, 68, 1.5],
  [65, 86, 2], [37, 90, 1.4], [14, 71, 1.8], [8, 42, 1.5],
  [25, 18, 1.7], [50, 24, 1.4], [71, 43, 1.5], [62, 68, 1.5],
  [35, 67, 1.3], [27, 43, 1.6],
];

export default function SignalOrb() {
  return (
    <div className="signal-orb" aria-hidden="true">
      <div className="orb-glow" />
      <svg viewBox="0 0 100 100">
        <defs>
          <radialGradient id="orbCore">
            <stop offset="0" stopColor="#fff" />
            <stop offset=".2" stopColor="#a4f4ee" />
            <stop offset="1" stopColor="#4fbdbd" stopOpacity=".05" />
          </radialGradient>
          <linearGradient id="orbLine" x1="0" x2="1">
            <stop stopColor="#65d4ce" stopOpacity=".1" />
            <stop offset=".5" stopColor="#9ce7e0" stopOpacity=".9" />
            <stop offset="1" stopColor="#65d4ce" stopOpacity=".1" />
          </linearGradient>
        </defs>
        <ellipse cx="50" cy="49" rx="43" ry="25" className="orb-eye" />
        <circle cx="50" cy="49" r="23" className="orb-ring ring-one" />
        <circle cx="50" cy="49" r="15" className="orb-ring ring-two" />
        <circle cx="50" cy="49" r="7" fill="url(#orbCore)" />
        <path d="M50 7 50 93M7 49h86M19 19l62 62M81 19 19 81" className="orb-axis" />
        {nodes.map(([x, y, r], index) => (
          <g key={index}>
            <line x1="50" y1="49" x2={x} y2={y} className="node-line" />
            <circle cx={x} cy={y} r={r} className="orb-node" />
          </g>
        ))}
      </svg>
      <div className="orbit-tag tag-one">AI origin</div>
      <div className="orbit-tag tag-two">Semantic risk</div>
      <div className="orbit-tag tag-three">Provenance</div>
    </div>
  );
}
