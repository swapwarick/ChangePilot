import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium", {
  variants: {
    variant: {
      default: "bg-primary/12 text-primary",
      secondary: "bg-muted text-muted-foreground",
      success: "bg-success/12 text-success",
      warning: "bg-warning/14 text-amber-700 dark:text-amber-300",
      destructive: "bg-destructive/12 text-destructive",
      outline: "border border-border bg-surface text-muted-foreground"
    }
  },
  defaultVariants: {
    variant: "default"
  }
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

