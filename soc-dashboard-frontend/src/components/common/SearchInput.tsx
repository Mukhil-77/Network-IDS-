interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchInput({ value, onChange, placeholder = "Search…" }: SearchInputProps) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-md border border-border bg-surface-raised px-3 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-signal focus:outline-none focus:ring-1 focus:ring-signal"
    />
  );
}
