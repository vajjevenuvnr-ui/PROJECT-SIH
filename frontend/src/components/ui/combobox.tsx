"use client";

import * as Popover from "@radix-ui/react-popover";
import { Command } from "cmdk";
import { Check, ChevronsUpDown } from "lucide-react";
import { useId, useState } from "react";

import { cn } from "@/lib/utils";

export interface ComboOption {
  value: string;
  label: string;
  /** Extra text matched by search, e.g. Telugu name. */
  keywords?: string[];
  hint?: string;
  disabled?: boolean;
}

interface ComboboxProps {
  id?: string;
  value: string | null;
  onChange: (value: string) => void;
  options: ComboOption[];
  placeholder: string;
  searchPlaceholder: string;
  emptyText: string;
  disabled?: boolean;
  loading?: boolean;
  className?: string;
}

/** Searchable select (shadcn-style: Radix Popover + cmdk). */
export function Combobox({
  id,
  value,
  onChange,
  options,
  placeholder,
  searchPlaceholder,
  emptyText,
  disabled,
  loading,
  className,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const selected = options.find((o) => o.value === value);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild disabled={disabled}>
        <button
          id={id}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          className={cn(
            "flex h-11 w-full items-center justify-between gap-2 rounded-xl border bg-surface px-3 text-left text-sm",
            "transition-colors hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
        >
          <span className={cn("truncate", !selected && "text-muted")}>
            {loading ? "…" : selected ? selected.label : placeholder}
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 text-muted" aria-hidden />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          id={listId}
          align="start"
          sideOffset={6}
          className="z-[1100] w-[var(--radix-popover-trigger-width)] min-w-56 overflow-hidden rounded-xl border bg-surface shadow-card"
        >
          <Command>
            <Command.Input
              placeholder={searchPlaceholder}
              className="h-10 w-full border-b bg-transparent px-3 text-sm outline-none placeholder:text-muted"
            />
            <Command.List className="max-h-64 overflow-y-auto p-1">
              <Command.Empty className="px-3 py-6 text-center text-sm text-muted">{emptyText}</Command.Empty>
              {options.map((o) => (
                <Command.Item
                  key={o.value}
                  value={`${o.label} ${o.keywords?.join(" ") ?? ""} ${o.value}`}
                  disabled={o.disabled}
                  onSelect={() => {
                    if (o.disabled) return;
                    onChange(o.value);
                    setOpen(false);
                  }}
                  className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm data-[selected=true]:bg-surface-2 data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-50"
                >
                  <Check className={cn("h-4 w-4 text-primary", o.value === value ? "opacity-100" : "opacity-0")} />
                  <span className="flex-1 truncate">{o.label}</span>
                  {o.hint && <span className="text-xs text-muted">{o.hint}</span>}
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
