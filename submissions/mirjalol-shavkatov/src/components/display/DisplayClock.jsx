import { useState, useEffect } from "react";

export default function DisplayClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const timeStr = time.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });

  const dateStr = time.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric"
  });

  return (
    <div className="absolute top-6 right-8 text-right z-10 pointer-events-none">
      <div
        className="text-white/90 font-display text-4xl font-light tracking-tight"
        style={{ textShadow: "0 2px 20px rgba(0,0,0,0.8)" }}
      >
        {timeStr}
      </div>
      <div
        className="text-white/50 font-body text-sm tracking-wide mt-0.5"
        style={{ textShadow: "0 1px 10px rgba(0,0,0,0.8)" }}
      >
        {dateStr}
      </div>
    </div>
  );
}