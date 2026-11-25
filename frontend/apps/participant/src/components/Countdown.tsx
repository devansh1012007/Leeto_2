/** Countdown (spec 1.3): server-deadline driven; announces 10/5/1 min via polite live region;
 * NEVER decides lateness — on zero the app refetches /state (hard rule). */
import React, { useEffect, useRef, useState } from "react";

export function useCountdown(deadline: string | null): {
  secondsLeft: number;
  label: string;
  announce: string | null;
} {
  const [now, setNow] = useState(() => Date.now());
  const [announce, setAnnounce] = useState<string | null>(null);
  const lastThreshold = useRef<number>(Infinity);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const deadlineMs = deadline ? Date.parse(deadline) : null;
  const secondsLeft = deadlineMs === null ? Infinity : Math.max(0, Math.floor((deadlineMs - now) / 1000));

  useEffect(() => {
    for (const threshold of [600, 300, 60]) {
      if (secondsLeft <= threshold && lastThreshold.current > threshold) {
        lastThreshold.current = threshold;
        setAnnounce(threshold === 600 ? "10 minutes left" : threshold === 300 ? "5 minutes left" : "1 minute left");
        break;
      }
    }
    // at zero the SERVER decides; the client refetches state (TIM-01)
    if (secondsLeft === 0 && lastThreshold.current > 0) {
      lastThreshold.current = 0;
      window.dispatchEvent(new CustomEvent("bhctf:deadline-zero"));
    }
  }, [secondsLeft]);

  const label = secondsLeft === Infinity
    ? "--:--"
    : secondsLeft >= 3600
      ? `${Math.floor(secondsLeft / 3600)}:${String(Math.floor((secondsLeft % 3600) / 60)).padStart(2, "0")}:${String(secondsLeft % 60).padStart(2, "0")}`
      : `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;

  return { secondsLeft, label, announce };
}

export function Countdown({ deadline }: { deadline: string | null }): React.JSX.Element {
  const { label, announce } = useCountdown(deadline);
  const cls = announce === "1 minute left" ? "countdown critical" : announce ? "countdown warn" : "countdown";
  return (
    <>
      <span className={cls} role="timer" aria-live="off" data-testid="countdown">
        {label}
      </span>
      <span className="sr-only" role="status" aria-live="polite">
        {announce ?? ""}
      </span>
    </>
  );
}
