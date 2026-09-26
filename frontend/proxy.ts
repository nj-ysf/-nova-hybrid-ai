import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function proxy(request: NextRequest) {
  const sessionCookie = request.cookies.get("sessionid");
  const djangoApiUrl = process.env.DJANGO_API_URL || "http://127.0.0.1:8000";

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/login/", request.url));
  }

  try {
    const response = await fetch(`${djangoApiUrl.replace(/\/$/, "")}/api/projects/?limit=1`, {
      headers: { cookie: `sessionid=${sessionCookie.value}` },
      cache: "no-store",
    });

    if (!response.ok) {
      return NextResponse.redirect(new URL("/login/", request.url));
    }
  } catch {
    return NextResponse.redirect(new URL("/login/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/"],
};
