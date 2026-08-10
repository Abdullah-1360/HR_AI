// components/ui/Card.tsx
import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  hoverable = false,
  ...props
}) => {
  return (
    <div
      className={`glass-card p-6 ${
        hoverable ? "glass-card-hover cursor-pointer" : ""
      } ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
