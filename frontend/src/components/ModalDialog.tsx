"use client";

import React, { useEffect, useRef } from "react";

interface ModalDialogProps {
  isOpen: boolean;
  onClose: () => void;
  labelledBy: string;
  maxWidthClass?: string;
  containerClassName?: string;
  children: React.ReactNode;
}

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "area[href]",
  "button:not([disabled])",
  'input:not([disabled]):not([type="hidden"])',
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

export const openModalStack: string[] = [];
let nextDialogSequence = 0;

export function pushModalDialog(id: string, stack: string[] = openModalStack): void {
  removeModalDialog(id, stack);
  stack.push(id);
}

export function removeModalDialog(id: string, stack: string[] = openModalStack): void {
  for (let i = stack.length - 1; i >= 0; i -= 1) {
    if (stack[i] === id) {
      stack.splice(i, 1);
    }
  }
}

export function isTopmostModalDialog(
  id: string,
  stack: readonly string[] = openModalStack
): boolean {
  return stack.length > 0 && stack[stack.length - 1] === id;
}

function isElementFocusable(element: HTMLElement): boolean {
  if ((element as HTMLButtonElement).disabled) return false;
  if (element.hasAttribute?.("hidden") || element.hidden) return false;
  if (element.getAttribute?.("aria-hidden") === "true") return false;
  if (typeof window !== "undefined" && typeof window.getComputedStyle === "function") {
    try {
      const style = window.getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") {
        return false;
      }
    } catch {
      // Ignore style inspection errors in non-standard DOM shims.
    }
  }
  return true;
}

export function getFocusableElements(container: HTMLElement | null): HTMLElement[] {
  if (!container || typeof container.querySelectorAll !== "function") return [];
  const candidates = Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR));
  return candidates.filter((node): node is HTMLElement => isElementFocusable(node as HTMLElement));
}

export interface DialogKeyDownOptions {
  panel: HTMLElement | null;
  dialogId: string;
  onClose: () => void;
  stack?: readonly string[];
  activeElement?: Element | null;
}

/**
 * Keyboard handler for modal dialogs supporting topmost-only Escape dismissal
 * and Tab / Shift+Tab focus trapping inside the dialog panel.
 */
export function handleDialogKeyDown(
  event: Pick<KeyboardEvent, "key" | "shiftKey" | "preventDefault">,
  {
    panel,
    dialogId,
    onClose,
    stack = openModalStack,
    activeElement = typeof document !== "undefined" ? document.activeElement : null,
  }: DialogKeyDownOptions
): boolean {
  if (!isTopmostModalDialog(dialogId, stack)) {
    return false;
  }

  if (event.key === "Escape") {
    event.preventDefault();
    onClose();
    return true;
  }

  if (event.key !== "Tab" || !panel) {
    return false;
  }

  const focusables = getFocusableElements(panel);
  if (focusables.length === 0) {
    event.preventDefault();
    panel.focus();
    return true;
  }

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const activeHtmlElement = activeElement as HTMLElement | null;
  const activeIndex = activeHtmlElement ? focusables.indexOf(activeHtmlElement) : -1;

  if (activeIndex === -1) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return true;
  }

  if (event.shiftKey) {
    if (activeHtmlElement === first) {
      event.preventDefault();
      last.focus();
      return true;
    }
    return false;
  }

  if (activeHtmlElement === last) {
    event.preventDefault();
    first.focus();
    return true;
  }

  return false;
}

/**
 * Shared WCAG-aligned modal dialog supporting Escape dismissal, backdrop click dismissal,
 * Tab/Shift+Tab focus trapping, stacked dialog ordering, and automatic focus capture /
 * restoration to the invoking control.
 */
export function ModalDialog({
  isOpen,
  onClose,
  labelledBy,
  maxWidthClass = "max-w-lg",
  containerClassName = "",
  children,
}: ModalDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const dialogIdRef = useRef<string | null>(null);
  if (dialogIdRef.current === null) {
    nextDialogSequence += 1;
    dialogIdRef.current = `modal-dialog-${nextDialogSequence}`;
  }

  useEffect(() => {
    if (!isOpen) return;

    const dialogId = dialogIdRef.current!;
    previousFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    pushModalDialog(dialogId);

    const focusTimer = window.setTimeout(() => {
      if (isTopmostModalDialog(dialogId)) {
        panelRef.current?.focus();
      }
    }, 0);

    const handleKeyDown = (event: KeyboardEvent) => {
      handleDialogKeyDown(event, {
        panel: panelRef.current,
        dialogId,
        onClose: () => onCloseRef.current(),
      });
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", handleKeyDown);
      const wasTopmost = isTopmostModalDialog(dialogId);
      removeModalDialog(dialogId);
      const previous = previousFocusRef.current;
      previousFocusRef.current = null;
      if (wasTopmost && previous && previous.isConnected !== false) {
        previous.focus();
      }
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledBy}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onCloseRef.current();
        }
      }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm animate-fadeIn"
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className={`bg-navy-900 border border-navy-700 rounded-3xl ${maxWidthClass} w-full p-6 shadow-2xl relative focus:outline-none ${containerClassName}`}
      >
        {children}
      </div>
    </div>
  );
}
