import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function ScrollArea({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("max-h-[540px] overflow-y-auto pr-2 [scrollbar-width:thin]", className)}
      {...props}
    />
  );
}
