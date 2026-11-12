/** 时间格式：底稿统一 YYYY-MM-DD HH:mm。 */
export function formatTime(value: string | null | undefined): string {
  if (!value) return '—';
  const parsed = new Date(value.replace(' ', 'T'));
  if (Number.isNaN(parsed.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, '0');
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

export function formatDate(value: string | null | undefined): string {
  return formatTime(value).slice(0, 10);
}
