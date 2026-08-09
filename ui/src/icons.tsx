/**
 * The icon system, in one file so a second stroke weight cannot creep in.
 *
 * Lucide supplies everything generic. The two vehicle marks below are drawn here
 * rather than borrowed, because Lucide's `car` is a hatchback silhouette and using
 * it for a rental van or a ranked recommendation would be forcing a generic glyph
 * to mean something it does not. They are original outlines on the same 24 unit
 * grid and the same stroke weight, so they sit in a row with the Lucide set without
 * reading as a different family.
 *
 * Two sizes only: 20px in navigation and buttons, 40px where an icon heads a card.
 */

import {
  ArrowRight,
  Check,
  ClipboardList,
  Cpu,
  Languages,
  LayoutGrid,
  Moon,
  Receipt,
  RotateCcw,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  type LucideIcon,
} from "lucide-react";

export const NAV_GROESSE = 20;
export const KARTE_GROESSE = 40;
export const STRICH = 1.5;

export {
  ArrowRight,
  Check,
  ClipboardList,
  Cpu,
  Languages,
  LayoutGrid,
  Moon,
  Receipt,
  RotateCcw,
  Send,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  type LucideIcon,
};

type MarkeProps = { size?: number; className?: string };

/**
 * The brand mark, as used in the header.
 *
 * Same geometry as the favicon in `public/favicon.svg`, with two differences that
 * matter. There is no disc: a favicon needs its own ground because it lands on a tab
 * strip we do not control, whereas in the header the mark sits on the page and
 * should take the page's ink. And the colours are variables rather than literals, so
 * the mark inverts with the theme instead of needing a second file.
 *
 * The viewBox is cropped to the mark's own bounds so it sits tight against the
 * wordmark. Keeping the favicon's square would padd it away from the lettering.
 */
export function FahrbereitMarke({ size = 26, className = "marke-zeichen" }: MarkeProps) {
  return (
    <svg
      width={(size * 35) / 38}
      height={size}
      viewBox="7 5 35 38"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <g transform="translate(4.5 0) skewX(-12)">
        <rect x="12" y="6" width="9" height="36" fill="currentColor" />
        <rect x="21" y="6" width="17" height="9" fill="currentColor" />
        <rect x="21" y="21" width="13" height="9" fill="currentColor" />
        <rect x="25" y="33" width="9" height="9" fill="var(--accent)" />
      </g>
    </svg>
  );
}

/** An estate car in outline. Used for the purchase path and the ranked catalogue. */
export function AutoMarke({ size = NAV_GROESSE, className = "ikone" }: MarkeProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={STRICH}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path d="M3 16v-3.2a2 2 0 0 1 .35-1.13l2.2-3.2A2 2 0 0 1 7.2 7.6h9.6a2 2 0 0 1 1.65.87l2.2 3.2A2 2 0 0 1 21 12.8V16" />
      <path d="M3 16h18" />
      <path d="M5.5 11.6h13" />
      <path d="M12 7.6v4" />
      <circle cx="7.2" cy="16.4" r="1.9" />
      <circle cx="16.8" cy="16.4" r="1.9" />
    </svg>
  );
}

/** A panel van in outline. Used wherever the rental path is being shown. */
export function MietwagenMarke({ size = NAV_GROESSE, className = "ikone" }: MarkeProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={STRICH}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path d="M2.5 16.5V8a1.5 1.5 0 0 1 1.5-1.5h9.5a1.5 1.5 0 0 1 1.5 1.5v8.5" />
      <path d="M15 10.5h2.9a1.5 1.5 0 0 1 1.24.66l1.86 2.76a1.5 1.5 0 0 1 .25.83v1.75" />
      <path d="M2.5 16.5h19" />
      <path d="M9 6.5v10" />
      <circle cx="7" cy="16.9" r="1.8" />
      <circle cx="17" cy="16.9" r="1.8" />
    </svg>
  );
}

/** A rosette. Marks the top recommendation and nothing else. */
export function EmpfehlungMarke({ size = NAV_GROESSE, className = "ikone" }: MarkeProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={STRICH}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="9" r="5.5" />
      <path d="m8.4 13.7-1.4 6.3 5-2.4 5 2.4-1.4-6.3" />
      <path d="m12 6.4 1 2.1 2.2.3-1.6 1.6.4 2.2-2-1.1-2 1.1.4-2.2-1.6-1.6 2.2-.3z" />
    </svg>
  );
}
