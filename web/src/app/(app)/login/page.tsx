import { LoginForm } from "@/components/login-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DEPLOYMENT_MODE } from "@/lib/config";
import { loginIntro, loginTitle } from "@/lib/deployment";

export const metadata = { title: "Sign in · RecruitIQ" };

/** Only a same-origin path may be a post-login destination. */
function safeNext(raw: string | string[] | undefined): string {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

/**
 * Staff sign-in. On the public demo visitors never need this page: the proxy
 * signs them in as the read-only demo user automatically, and signing in here
 * unlocks writes and the admin-only screens. On an internal install this is
 * the front door: the proxy sends every signed-out visitor here.
 */
export default async function LoginPage({ searchParams }: PageProps<"/login">) {
  const next = safeNext((await searchParams).next);

  return (
    <div className="mx-auto max-w-sm pt-12">
      <Card>
        <CardHeader>
          <CardTitle>{loginTitle(DEPLOYMENT_MODE)}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-500">{loginIntro(DEPLOYMENT_MODE)}</p>
          <LoginForm next={next} />
        </CardContent>
      </Card>
    </div>
  );
}
