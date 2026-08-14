import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Sign in — ChangePilot",
  description: "Sign in to your ChangePilot account",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-layout">
      {children}
    </div>
  );
}
