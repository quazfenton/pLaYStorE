import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/Navbar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "plaYstore | Discover the Open Source Universe",
  description: "A state-of-the-art app store for open-source projects.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased bg-background text-foreground`}>
        <Navbar />
        <main className="ml-20 min-h-screen">
          <div className="max-w-[1400px] mx-auto p-12">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
