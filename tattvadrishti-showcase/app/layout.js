import "@fontsource-variable/inter";
import "@fontsource-variable/manrope";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";

export const metadata = {
  title: "TattvaDrishti — Analyst-Centric Intelligence",
  description:
    "A multi-modal decision-support platform for AI-enabled malign information operations, developed by Team ASHTOJ.",
  keywords: [
    "TattvaDrishti",
    "NCSRC 2026",
    "cyber intelligence",
    "misinformation analysis",
    "AI detection",
    "Team ASHTOJ",
  ],
  openGraph: {
    title: "TattvaDrishti — See through the signal",
    description:
      "From suspicious content to explainable, connected and auditable intelligence.",
    type: "website",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#06111d",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
