import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: "primary" | "secondary" | "ghost";
};

const tones = {
  ghost: "border-transparent text-muted hover:text-ink",
  primary: "border-live bg-live text-black hover:bg-live/90",
  secondary: "border-border bg-raised text-ink hover:border-live/60"
};

export function Button({ className, tone = "secondary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex h-9 items-center justify-center gap-2 rounded-ui border px-3 text-sm transition disabled:cursor-not-allowed disabled:opacity-50",
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
