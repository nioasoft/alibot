import type { Metadata, Viewport } from "next";
import { Heebo } from "next/font/google";
import { PageView } from "@/components/PageView";
import "./globals.css";

const heebo = Heebo({
  variable: "--font-heebo",
  subsets: ["latin", "hebrew"],
  weight: ["400", "700", "800"],
});

const SITE_NAME = "מכורים לדילים ומבצעים";
const SITE_DESCRIPTION =
  "קהילת מכורי הדילים והמבצעים - דילים חמים מ-AliExpress, Amazon ועוד. הצטרפו לטלגרם, וואטסאפ ופייסבוק!";

export const viewport: Viewport = {
  themeColor: "#FF6B00",
  width: "device-width",
  initialScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ??
      (process.env.VERCEL_PROJECT_PRODUCTION_URL
        ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
        : "https://alibot.vercel.app")
  ),
  title: {
    default: `${SITE_NAME} | הדילים הכי טובים מכל הרשת`,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESCRIPTION,
  manifest: "/site.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  openGraph: {
    title: SITE_NAME,
    description: "הדילים הכי טובים, הכי מהר, הכי קל - בקבוצה שלנו!",
    images: [
      {
        url: "/og-image.jpg",
        width: 1200,
        height: 630,
        alt: SITE_NAME,
      },
    ],
    locale: "he_IL",
    type: "website",
    siteName: SITE_NAME,
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_NAME,
    description: "הדילים הכי טובים, הכי מהר, הכי קל - בקבוצה שלנו!",
    images: ["/og-image.jpg"],
  },
  robots: {
    index: true,
    follow: true,
  },
  other: {
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "default",
    "apple-mobile-web-app-title": SITE_NAME,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="he" dir="rtl" className={`${heebo.variable} antialiased`}>
      <body className="font-sans">
        <PageView />
        {children}
      </body>
    </html>
  );
}
