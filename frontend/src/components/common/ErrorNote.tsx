interface Props {
  message: string;
  title?: string;
}

export function ErrorNote({ message, title = '操作未通过校验' }: Props) {
  if (!message) return null;
  return (
    <div className="error-note">
      <strong>{title}</strong>
      <div>{message}</div>
    </div>
  );
}
