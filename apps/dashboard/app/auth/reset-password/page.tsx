import Link from "next/link";

import { AuthPanel } from "@/components/auth-panel";
import { Button } from "@/components/ui/button";

import { resetPassword } from "../actions";

export default function ResetPasswordPage() {
  return (
    <AuthPanel title="Reset Password" footer={<Link href="/auth/login" className="text-live">Back to login</Link>}>
      <form action={resetPassword} className="space-y-3">
        <input className="h-10 w-full rounded-ui border border-border bg-obsidian px-3 outline-none focus:border-live" name="email" type="email" placeholder="email" required />
        <Button type="submit" tone="primary" className="w-full">Send Link</Button>
      </form>
    </AuthPanel>
  );
}
