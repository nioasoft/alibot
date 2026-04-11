import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-brand-navy text-white">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="flex flex-col items-center gap-4">
          <Image
            src="/logo.webp"
            alt="מכורים לדילים ומבצעים"
            width={64}
            height={64}
            className="rounded-full"
          />
          <p className="text-sm text-white/70">
            מכורים לדילים ומבצעים - הדילים הכי טובים מכל הרשת
          </p>
          <Link
            href="/terms"
            className="text-xs text-white/50 hover:text-white/80 transition-colors underline"
          >
            תקנון האתר
          </Link>
          <p className="text-xs text-white/40">
            © {new Date().getFullYear()} כל הזכויות שמורות
          </p>
        </div>
      </div>
    </footer>
  );
}
