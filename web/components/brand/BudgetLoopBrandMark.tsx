interface BudgetLoopBrandMarkProps {
  className?: string;
}

/** The static, cross-surface BudgetLoop interlocking-loop brand mark. */
export function BudgetLoopBrandMark({ className }: BudgetLoopBrandMarkProps) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      data-brand-mark="budgetloop"
      fill="none"
      focusable="false"
      viewBox="0 0 1024 1024"
    >
      <rect x="52" y="52" width="920" height="920" rx="224" fill="currentColor" opacity="0.1" />
      <g
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="74"
      >
        <path d="M515 512C515 618 429 704 323 704C217 704 131 618 131 512C131 406 217 320 323 320C429 320 515 406 515 512Z" />
        <path d="M509 512C509 406 595 320 701 320C807 320 893 406 893 512C893 618 807 704 701 704C595 704 509 618 509 512Z" />
      </g>
      <circle cx="512" cy="512" r="38" className="fill-white" />
      <circle cx="512" cy="512" r="23" fill="currentColor" />
    </svg>
  );
}
