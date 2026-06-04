import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "HookFlow AI - Transform Long Videos into Viral Shorts",
  description: "Find the top viral moments in your YouTube videos, crop automatically to vertical 9:16 format, and burn engaging hook titles. Styled in the dark aesthetics of Artlist.io.",
  keywords: ["viral clips", "youtube shorts generator", "tiktok editor", "AI video trimmer", "reels creator", "auto crop", "hook titles"],
  openGraph: {
    title: "HookFlow AI - Transform Long Videos into Viral Shorts",
    description: "AI-powered automated YouTube Shorts clipping, vertical reframing, and styled hook subtitle burning in one sleek Artlist-cloned Studio Workspace.",
    type: "website",
  }
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} dark h-full`}>
      <body className="min-h-full font-sans bg-brand-bg text-gray-100 antialiased flex flex-col">
        {children}
      </body>
    </html>
  );
}
