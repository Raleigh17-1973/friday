"use client";

/**
 * Toast — Phase 12 shared UI component.
 *
 * Re-exports everything from toast-context so callers can import from a
 * single path and to ensure the toast.tsx file expected by the plan exists.
 *
 * Usage:
 *   import { ToastProvider, useToast } from "@/components/ui/toast";
 *
 *   // Wrap your layout:
 *   <ToastProvider>{children}</ToastProvider>
 *
 *   // Inside any component:
 *   const toast = useToast();
 *   toast.success("Saved!");
 *   toast.error("Something went wrong");
 *   toast.info("Processing…");
 */
export { ToastProvider, useToast } from "./toast-context";
export type { Toast, ToastType } from "./toast-context";
