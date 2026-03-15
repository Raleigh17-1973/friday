"use client";

import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

type ModalSize = "sm" | "md" | "lg";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  size?: ModalSize;
  children: React.ReactNode;
}

const SIZE_WIDTHS: Record<ModalSize, string> = {
  sm: "380px",
  md: "540px",
  lg: "760px",
};

export function Modal({ open, onClose, title, size = "md", children }: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => { document.body.style.overflow = ""; };
  }, [open]);

  if (!open) return null;

  const content = (
    <div
      className="modal-overlay"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      aria-modal="true"
      role="dialog"
      aria-label={title}
    >
      <div
        ref={panelRef}
        className="modal-box"
        style={{ maxWidth: SIZE_WIDTHS[size] }}
      >
        {title && (
          <div className="modal-header">
            <h2 className="modal-title">{title}</h2>
            <button className="modal-close" onClick={onClose} aria-label="Close dialog">✕</button>
          </div>
        )}
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );

  return typeof window !== "undefined" ? createPortal(content, document.body) : null;
}
