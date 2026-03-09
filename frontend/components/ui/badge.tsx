import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-[0.18em] transition-colors",
  {
    variants: {
      variant: {
        default: "border-border bg-secondary text-secondary-foreground",
        outline: "border-border/80 bg-background/60 text-foreground",
        danger: "border-rose-500/40 bg-rose-500/10 text-rose-200",
        warning: "border-amber-400/40 bg-amber-400/10 text-amber-100",
        success: "border-emerald-400/40 bg-emerald-400/10 text-emerald-100",
        info: "border-sky-400/40 bg-sky-400/10 text-sky-100",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
