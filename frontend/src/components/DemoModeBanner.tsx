import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { api, Health } from "../lib/api";

/**
 * Honest status line for demos: shown only when the real detector is not loaded or the server is
 * running in offline demo mode. It never claims a model is connected when it is not.
 */
export default function DemoModeBanner() {
  const [health, setHealth] = useState<Health | null>(null);
  useEffect(() => {
    let cancelled = false;
    api.health().then((h) => { if (!cancelled) setHealth(h); }).catch(() => { if (!cancelled) setHealth(null); });
    return () => { cancelled = true; };
  }, []);

  if (!health) return null;
  const offline = health.offline_demo === true;
  const modelMissing = !health.detector.loaded;
  if (!offline && !modelMissing) return null;

  return (
    <div role="status" className="mx-4 sm:mx-6 lg:mx-8 mt-4 rounded-xl bg-amber text-[#78571A] px-4 py-2.5 flex items-start gap-2.5 text-[12.5px]">
      <WifiOff size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
      <p>
        <span className="font-semibold">{offline ? "Offline demo mode." : "Detector model not loaded."}</span>{" "}
        {modelMissing
          ? "Detections will use the labelled pixel-heuristic fallback, which is not a trained deepfake classifier, until the model is available."
          : "Running without network access using cached models."}
      </p>
    </div>
  );
}
