// Session and Demo Mode cookies (readable on the server and the client).
//
// pc-session=demo   -> signed in as the built-in demo officer (no Supabase account)
// pc-demo-data=1    -> API calls send "X-Demo-Mode: 1" (cached forecast, works offline)
//
// A demo session always uses demo data. A real officer can switch Demo Mode on or off.

export const DEMO_SESSION_COOKIE = "pc-session";
export const DEMO_DATA_COOKIE = "pc-demo-data";
const YEAR = 60 * 60 * 24 * 365;

export const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export function isSupabaseConfigured(): boolean {
  return Boolean(supabaseUrl && supabaseAnonKey) && !supabaseUrl.includes("your-project");
}

export function setClientCookie(name: string, value: string | null) {
  if (value === null) {
    document.cookie = `${name}=; Path=/; Max-Age=0; SameSite=Lax`;
  } else {
    document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; Max-Age=${YEAR}; SameSite=Lax`;
  }
}

export function startDemoSession() {
  setClientCookie(DEMO_SESSION_COOKIE, "demo");
  setClientCookie(DEMO_DATA_COOKIE, "1");
}

export function endDemoSession() {
  setClientCookie(DEMO_SESSION_COOKIE, null);
  setClientCookie(DEMO_DATA_COOKIE, null);
}
