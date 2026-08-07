export default function Logo({ compact = false }) {
  return (
    <a className="brand" href="#top" aria-label="TattvaDrishti home">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 44 44" role="img">
          <path d="M4 22s6.6-10 18-10 18 10 18 10-6.6 10-18 10S4 22 4 22Z" />
          <circle cx="22" cy="22" r="5.5" />
          <path d="M22 3v5M22 36v5M3 22h5M36 22h5" />
        </svg>
      </span>
      {!compact && (
        <span className="brand-copy">
          <strong>Tattva<span>Drishti</span></strong>
          <small>See through the signal</small>
        </span>
      )}
    </a>
  );
}
