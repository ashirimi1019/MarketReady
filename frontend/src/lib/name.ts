export function formatDisplayName(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";

  return trimmed
    .split(/\s+/)
    .map((token) =>
      token
        .split(/([_'-])/)
        .map((segment) => {
          if (!segment || /^[_'-]$/.test(segment)) return segment;
          return segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase();
        })
        .join("")
    )
    .join(" ");
}
