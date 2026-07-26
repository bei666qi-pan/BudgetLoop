"use client";

import { useId } from "react";

interface BudgetLoopActivityMarkProps {
  label: string;
  compact?: boolean;
}

export function BudgetLoopActivityMark({
  label,
  compact = false,
}: BudgetLoopActivityMarkProps) {
  const filterId = `budgetloop-disturbance-${useId().replaceAll(":", "")}`;

  return (
    <span
      role="status"
      aria-label={label}
      className="inline-flex items-center gap-2.5"
      data-activity-mark="budgetloop"
      data-variant={compact ? "compact" : "full"}
    >
      <span
        aria-hidden="true"
        className={`budgetloop-activity-mark relative inline-grid shrink-0 place-items-center ${compact ? "budgetloop-activity-mark--compact h-7 w-9" : "h-14 w-[5.25rem]"}`}
      >
        <span className="budgetloop-activity-halo" />
        <svg
          viewBox="0 0 1024 512"
          className="budgetloop-loop-svg relative z-[1] h-full w-full overflow-visible"
          fill="none"
          focusable="false"
        >
          <defs>
            <filter id={filterId} x="-18%" y="-28%" width="136%" height="156%">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.012 0.034"
                numOctaves="2"
                seed="7"
                result="noise"
              />
              <feDisplacementMap
                in="SourceGraphic"
                in2="noise"
                scale={compact ? 7 : 12}
                xChannelSelector="R"
                yChannelSelector="B"
              />
            </filter>
          </defs>
          <g
            className="budgetloop-loop-disturbance"
            filter={`url(#${filterId})`}
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="74"
          >
            <path
              className="budgetloop-loop budgetloop-loop--left"
              d="M515 256C515 362 429 448 323 448C217 448 131 362 131 256C131 150 217 64 323 64C429 64 515 150 515 256Z"
            />
            <path
              className="budgetloop-loop budgetloop-loop--right"
              d="M509 256C509 150 595 64 701 64C807 64 893 150 893 256C893 362 807 448 701 448C595 448 509 362 509 256Z"
            />
          </g>
          <g className="budgetloop-loop-lens">
            <circle cx="512" cy="256" r="41" className="fill-white" />
            <circle cx="512" cy="256" r="23" fill="currentColor" />
          </g>
        </svg>
      </span>
      {compact ? <span className="text-sm font-semibold">{label}</span> : null}
    </span>
  );
}
