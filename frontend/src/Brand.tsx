import { useState } from "react";

// Shows the official company logo if public/elevance-logo.png has been
// added; otherwise falls back to the app's own FSSA Agents mark.
export function Brand({ className }: { className?: string }) {
  const [logoMissing, setLogoMissing] = useState(false);
  return (
    <div className={`brand ${className ?? ""}`}>
      <img
        src={logoMissing ? "/fssa-mark.svg" : "/elevance-logo.png"}
        alt={logoMissing ? "FSSA Agents" : "Elevance Health"}
        className={logoMissing ? "brand-mark" : "brand-logo"}
        onError={() => setLogoMissing(true)}
      />
      <span className="brand-label">FSSA Agents</span>
    </div>
  );
}
