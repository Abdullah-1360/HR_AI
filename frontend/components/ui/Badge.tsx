// components/ui/Badge.tsx
import React from "react";

interface BadgeProps {
  variant?: "violet" | "cyan" | "emerald" | "amber" | "red" | "slate";
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  variant = "slate",
  children,
  className = "",
}) => {
  const variantClasses = {
    violet: "badge-violet",
    cyan: "badge-cyan",
    emerald: "badge-emerald",
    amber: "badge-amber",
    red: "badge-red",
    slate: "badge-slate",
  };

  return (
    <span className={`badge ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};
