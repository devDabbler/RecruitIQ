import { LoginForm } from "@/components/login-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = { title: "Sign in · RecruitIQ" };

/** Only a same-origin path may be a post-login destination. */
function safeNext(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

/**
 * Administrator sign-in. Visitors never need this page: the proxy signs them in
 * as the read-only demo user automatically. Signing in here unlocks writes,
 * like saving a parsed resume as a candidate, and the admin-only screens.
 */
export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const next = safeNext((await searchParams).next);

  return (
    <div className="mx-auto max-w-sm pt-12">
      <Card>
        <CardHeader>
          <CardTitle>Administrator sign-in</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-500">
            Visitors browse as the read-only demo automatically. Sign in to save
            candidates and change data.
          </p>
          <LoginForm next={next} />
        </CardContent>
      </Card>
    </div>
  );
}
