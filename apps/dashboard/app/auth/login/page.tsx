import Link from "next/link";

import { AuthPanel } from "@/components/auth-panel";
import { Button } from "@/components/ui/button";

import { signIn } from "../actions";

export default function LoginPage() {
  return (
    <AuthPanel
      title="Login"
      footer={
        <>
          <Link href="/auth/signup" className="text-live">
            Create account
          </Link>{" "}
          ·{" "}
          <Link href="/auth/reset-password" className="text-live">
            Reset password
          </Link>
        </>
      }
    >
      <form action={signIn} className="space-y-3">
        <input className="h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="email" type="email" placeholder="email" required />
        <input className="h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="password" type="password" placeholder="password" required />
        <Button type="submit" tone="primary" className="w-full">Login</Button>
      </form>
    </AuthPanel>
  );
}
