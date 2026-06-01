"use server";

import { redirect } from "next/navigation";

import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function signIn(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    redirect("/auth/login?error=1");
  }
  redirect("/");
}

export async function signUp(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signUp({ email, password });
  if (error) {
    redirect("/auth/signup?error=1");
  }
  redirect("/onboarding");
}

export async function resetPassword(formData: FormData) {
  const supabase = await createSupabaseServerClient();
  const email = String(formData.get("email") ?? "");
  await supabase.auth.resetPasswordForEmail(email);
  redirect("/auth/login?reset=1");
}
