/**
 * Next.js middleware — redirects unauthenticated users to /login.
 *
 * Token validation is done client-side (the access token lives in localStorage,
 * which is inaccessible to middleware). We therefore use a lightweight cookie
 * "cp_authed" that the auth client sets to "1" after a successful login and
 * clears on logout. The middleware only checks for that cookie's presence.
 *
 * This is enough to prevent a blank redirect loop — the auth context on the
 * client side will re-validate the actual JWT and redirect to /login if
 * the token is expired or invalid.
 */

import { type NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = new Set(["/login", "/register"]);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public auth pages and Next.js internals
  if (
    PUBLIC_PATHS.has(pathname) ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/favicon")
  ) {
    return NextResponse.next();
  }

  // Check lightweight auth cookie
  const authed = request.cookies.get("cp_authed")?.value;
  if (!authed) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - public folder files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
