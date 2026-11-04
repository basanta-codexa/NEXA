export default function StatusBadge({ status }: { status: string }) {
  const cls = `badge badge-${status.toLowerCase()}`;
  const label =
    status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
  return <span className={cls}>{label}</span>;
}
