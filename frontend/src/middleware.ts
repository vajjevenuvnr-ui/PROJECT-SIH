import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { DEMO_SESSION_COOKIE, isSupabaseConfigured, supabaseAnonKey, supabaseUrl } from "@/lib/session";

// Officer pages need a Supabase session or a demo session. Everything else is public.
// /api is proxied to FastAPI, which enforces its own auth.
const PUBLIC_PATHS = ["/login", "/set-password", "/styleguide", "/f/", "/api/", "/health", "/manifest.webmanifest", "/sw.js"];

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  // Proxied API calls: no session work here (FastAPI checks officer tokens itself).
  if (pathname.startsWith("/api/") || pathname === "/health") return NextResponse.next();
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p));
  const isDemo = request.cookies.get(DEMO_SESSION_COOKIE)?.value === "demo";

  let response = NextResponse.next({ request });
  let signedIn = isDemo;

  if (!isDemo && isSupabaseConfigured()) {
    // Refreshes the Supabase auth cookie if needed.
    const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    });
    try {
      const { data } = await supabase.auth.getUser();
      signedIn = Boolean(data.user);
    } catch {
      signedIn = false;
    }
  }

  if (!isPublic && !signedIn) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = pathname === "/" ? "" : `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  if (pathname === "/login" && signedIn) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return response;
}

export const config = {
  // Skip Next internals and static files.
  matcher: ["/((?!_next/static|_next/image|brand/|tiles/|favicon|.*\\.(?:png|jpg|svg|ico|webp|json|js)$).*)"],
};
