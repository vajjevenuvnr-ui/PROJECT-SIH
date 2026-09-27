// Re-mounts on every navigation, giving each screen a short fade-in.
export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="animate-fade-up">{children}</div>;
}
