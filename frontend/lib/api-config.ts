/**
 * Resolves the backend API base URL dynamically.
 *
 * 1. If running in a browser on Render (e.g. changepilot-frontend.onrender.com),
 *    automatically routes to the paired backend (e.g. changepilot-api.onrender.com).
 * 2. Uses NEXT_PUBLIC_API_BASE_URL if explicitly configured.
 * 3. Defaults to http://localhost:8000 for local development.
 */
export function getApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const host = window.location.host;
    // If running on Render: changepilot-frontend.onrender.com -> changepilot-api.onrender.com
    if (host.includes("-frontend.onrender.com")) {
      return `https://${host.replace("-frontend.onrender.com", "-api.onrender.com")}`;
    }
    if (host.includes("onrender.com") && !host.includes("-api.")) {
      return "https://changepilot-api.onrender.com";
    }
  }

  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (envUrl && !envUrl.includes("localhost")) {
    return envUrl.replace(/\/+$/, "");
  }

  return (envUrl || "http://localhost:8000").replace(/\/+$/, "");
}
