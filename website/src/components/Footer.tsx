import Image from "next/image";
import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-brand-navy text-white">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-col items-center gap-4 text-center">
          <Image
            src="/logo.webp"
            alt="מכורים לדילים ומבצעים"
            width={64}
            height={64}
            className="rounded-full"
          />
          <p className="text-sm leading-7 text-white/75">
            מכורים לדילים ומבצעים. כל קבוצות ההצטרפות שלנו במקום אחד, עם מעבר
            מהיר לטלגרם, וואטסאפ ופייסבוק.
          </p>
          <p className="rounded-full border border-white/15 bg-white/5 px-4 py-2 text-xs font-bold text-white/85">
            dilim.net
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
