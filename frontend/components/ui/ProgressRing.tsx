// components/ui/ProgressRing.tsx
import React from "react";

interface ProgressRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export const ProgressRing: React.FC<ProgressRingProps> = ({
  score,
  size = 50,
  strokeWidth = 4,
  className = "",
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (score / 100) * circumference;

  let colorClass = "text-red-500 stroke-red-500";
  if (score >= 80) {
    colorClass = "text-emerald-500 stroke-emerald-500";
  } else if (score >= 60) {
    colorClass = "text-cyan-500 stroke-cyan-500";
  } else if (score >= 40) {
    colorClass = "text-amber-500 stroke-amber-500";
  }

  return (
    <div className={`relative flex items-center justify-center ${className}`} style={{ width: size, height: size }}>
      <svg className="transform -rotate-90" width={size} height={size}>
        {/* Background Ring */}
        <circle
          className="text-white/5 stroke-white/5"
          strokeWidth={strokeWidth}
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        {/* Progress Ring */}
        <circle
          className={`transition-all duration-500 ease-out ${colorClass}`}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <span className="absolute text-xs font-bold font-sans text-slate-200">
        {score}
      </span>
    </div>
  );
};
