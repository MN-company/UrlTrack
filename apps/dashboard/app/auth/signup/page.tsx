import Link from "next/link";

import { AuthPanel } from "@/components/auth-panel";
import { Button } from "@/components/ui/button";

import { signUp } from "../actions";

export default function SignupPage() {
  return (
    <AuthPanel title="Signup" footer={<Link href="/auth/login" className="text-live">Back to login</Link>}>
      <form action={signUp} className="space-y-3">
        <input className="h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="email" type="email" placeholder="email" required />
        <input className="h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="password" type="password" placeholder="password" minLength={8} required />
        <Button type="submit" tone="primary" className="w-full">Create</Button>
      </form>
    </AuthPanel>
  );
}
