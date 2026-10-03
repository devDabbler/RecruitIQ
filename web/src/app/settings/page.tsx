import Link from "next/link";

import { ErrorState, PageHeader } from "@/components/page-header";
import { PasswordForm } from "@/components/password-form";
import { SettingsForm } from "@/components/settings-form";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getMyProfile } from "@/lib/data";
import { roleLabel } from "@/lib/permissions";
import { getUser } from "@/lib/session";

export const dynamic = "force-dynamic";

export const metadata = { title: "Settings · RecruitIQ" };

export default async function SettingsPage() {
  const user = await getUser();

  if (!user || user.role === "demo") {
    return (
      <>
        <PageHeader title="Settings" description="Your name, time zone, and password." />
        <Card>
          <CardContent className="p-6 text-sm text-slate-600">
            The read-only demo account has no settings to change.{" "}
            <Link href="/login" className="font-medium text-indigo-700 hover:underline">
              Sign in
            </Link>{" "}
            to set your name, time zone, and password.
          </CardContent>
        </Card>
      </>
    );
  }

  let profile;
  try {
    profile = await getMyProfile();
  } catch (error) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState
          title="Could not load your settings"
          detail={error instanceof ApiError ? error.detail : String(error)}
        />
      </>
    );
  }
  if (!profile) {
    return (
      <>
        <PageHeader title="Settings" />
        <ErrorState title="Could not load your settings" detail="Your account was not found. Sign in again." />
      </>
    );
  }

  return (
    <>
      <PageHeader title="Settings" description="Your name, time zone, and password." />
      <div className="grid gap-6 lg:grid-cols-2">
        <SettingsForm
          name={profile.name ?? ""}
          timezone={profile.timezone ?? ""}
          email={profile.email ?? user.email}
          roleText={roleLabel(profile.role)}
        />
        <PasswordForm />
      </div>
    </>
  );
}
