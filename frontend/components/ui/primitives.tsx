"use client";

import { Tooltip } from "@base-ui/react/tooltip";
import { Check, CircleAlert, Loader2, Minus, X } from "lucide-react";
import type { ButtonHTMLAttributes, ReactElement, ReactNode, Ref } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ Button */

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANT: Record<Variant, string> = {
  primary: "bg-action text-white hover:bg-action-hover disabled:bg-raised disabled:text-fg-faint",
  secondary: "bg-raised text-fg border border-line hover:bg-hover hover:border-line-strong disabled:text-fg-faint",
  ghost: "text-fg-muted hover:text-fg hover:bg-hover disabled:text-fg-faint disabled:hover:bg-transparent",
  danger: "bg-critical/15 text-critical border border-critical/30 hover:bg-critical/25",
};

const SIZE: Record<Size, string> = {
  sm: "h-7 px-2.5 gap-1.5 text-sm [&_svg]:size-3.5",
  md: "h-8 px-3 gap-2 text-sm [&_svg]:size-4",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ variant = "secondary", size = "md", className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-sm font-medium whitespace-nowrap select-none",
        "transition-colors duration-(--duration-fast) [&_svg]:shrink-0",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...props}
    />
  );
}

/* ------------------------------------------------------------------ Tooltip */

export function Kbd({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <kbd
      className={cn(
        "inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[4px] border border-line-strong bg-base px-1 font-mono text-[11px] leading-none text-fg-muted",
        className,
      )}
    >
      {children}
    </kbd>
  );
}

export function Tip({
  content,
  shortcut,
  side = "bottom",
  children,
}: {
  content: ReactNode;
  shortcut?: string;
  side?: "top" | "bottom" | "left" | "right";
  children: ReactElement;
}) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger delay={350} render={children} />
      <Tooltip.Portal>
        <Tooltip.Positioner side={side} sideOffset={6} className="z-50">
          <Tooltip.Popup className="flex max-w-72 items-center gap-2 rounded-sm border border-line-strong bg-raised px-2 py-1 text-sm text-fg shadow-lg shadow-black/40">
            <span>{content}</span>
            {shortcut && <Kbd>{shortcut}</Kbd>}
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export const TooltipProvider = Tooltip.Provider;

/** Icon-only controls always carry a tooltip and an accessible name; primary actions never use one. */
export function IconButton({
  label,
  shortcut,
  pressed,
  className,
  side,
  children,
  ...props
}: Omit<ButtonProps, "children"> & { label: string; shortcut?: string; pressed?: boolean; side?: "top" | "bottom" | "left" | "right"; children: ReactNode }) {
  return (
    <Tip content={label} shortcut={shortcut} side={side}>
      <Button
        variant="ghost"
        aria-label={label}
        aria-pressed={pressed}
        className={cn("w-8 px-0", pressed && "bg-hover text-fg", className)}
        {...props}
      >
        {children}
      </Button>
    </Tip>
  );
}

/* ------------------------------------------------------------------ Tag */

type Tone = "neutral" | "optical" | "sar" | "change" | "warning" | "critical" | "success" | "accent";

const TONE: Record<Tone, string> = {
  neutral: "text-fg-muted border-line-strong",
  optical: "text-optical border-optical/40",
  sar: "text-sar border-sar/40",
  change: "text-change border-change/40",
  warning: "text-warning border-warning/40 bg-warning/10",
  critical: "text-critical border-critical/40 bg-critical/10",
  success: "text-success border-success/40",
  accent: "text-accent border-accent/40",
};

export function Tag({ tone = "neutral", mono, className, children }: { tone?: Tone; mono?: boolean; className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 shrink-0 items-center gap-1 rounded-[4px] border px-1.5 text-xs whitespace-nowrap",
        mono && "font-mono text-[11px]",
        TONE[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ Status icons */

export type StatusKind = "pass" | "warn" | "fail" | "active" | "pending" | "skipped";

export function StatusIcon({ status, className }: { status: StatusKind; className?: string }) {
  const base = cn("size-4 shrink-0", className);
  switch (status) {
    case "pass":
      return <Check aria-label="Passed" className={cn(base, "text-success")} strokeWidth={2.5} />;
    case "warn":
      return <CircleAlert aria-label="Warning" className={cn(base, "text-warning")} />;
    case "fail":
      return <X aria-label="Failed" className={cn(base, "text-critical")} strokeWidth={2.5} />;
    case "active":
      return <Loader2 aria-label="Running" className={cn(base, "animate-spin text-accent motion-reduce:animate-none")} />;
    case "skipped":
      return <Minus aria-label="Not run" className={cn(base, "text-fg-faint")} />;
    default:
      return (
        <span aria-label="Pending" className={cn(base, "grid place-items-center")}>
          <span className="size-2 rounded-full border border-fg-faint" />
        </span>
      );
  }
}

/* ------------------------------------------------------------------ Confidence meter */

export function ConfidenceMeter({ steps, className }: { steps: 0 | 1 | 2 | 3 | 4; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-[3px]", className)} aria-hidden="true">
      {[1, 2, 3, 4].map((i) => (
        <span key={i} className={cn("h-2.5 w-1.5 rounded-[1.5px]", i <= steps ? "bg-fg" : "bg-line-strong")} />
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ Section label */

export function SectionLabel({ children, className }: { children: ReactNode; className?: string }) {
  return <h2 className={cn("text-xs font-medium tracking-wide text-fg-faint uppercase", className)}>{children}</h2>;
}
