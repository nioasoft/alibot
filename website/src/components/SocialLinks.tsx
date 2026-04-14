import { SOCIAL_LINKS } from "@/lib/social-links";

function TelegramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-7 w-7 fill-current">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  );
}

function PlatformIcon({ platform }: { platform: string }) {
  switch (platform) {
    case "telegram":
      return <TelegramIcon />;
    case "whatsapp":
      return <WhatsAppIcon />;
    case "facebook":
      return <FacebookIcon />;
    default:
      return null;
  }
}

const PLATFORM_META = {
  telegram: {
    title: "טלגרם",
    description: "ערוץ מרכזי לעדכונים שוטפים ודילים חמים.",
    panel: "from-[#ecf8ff] to-white",
    badge: "bg-[#0088cc] text-white",
    border: "border-[#0088cc]/15",
    icon: "text-[#0088cc]",
  },
  whatsapp: {
    title: "וואטסאפ",
    description: "קבוצות ייעודיות לפי נושא כדי לקבל רק מה שרלוונטי לכם.",
    panel: "from-[#eefdf4] to-white",
    badge: "bg-[#1fa855] text-white",
    border: "border-[#1fa855]/15",
    icon: "text-[#1fa855]",
  },
  facebook: {
    title: "פייסבוק",
    description: "דף וקבוצה למי שמעדיף לראות את הדילים גם בפייסבוק.",
    panel: "from-[#eef4ff] to-white",
    badge: "bg-[#1877F2] text-white",
    border: "border-[#1877F2]/15",
    icon: "text-[#1877F2]",
  },
} as const;

export function SocialLinks() {
  const sections = (["telegram", "whatsapp", "facebook"] as const).map(
    (platform) => ({
      platform,
      links: SOCIAL_LINKS.filter((link) => link.platform === platform),
      meta: PLATFORM_META[platform],
    })
  );

  return (
    <section
      id="groups"
      aria-labelledby="groups-title"
      className="bg-white py-12 md:py-16"
    >
      <div className="mx-auto max-w-6xl px-4">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-black uppercase tracking-[0.22em] text-brand-orange">
            קבוצות והזמנות
          </p>
          <h2
            id="groups-title"
            className="mt-3 text-3xl font-extrabold text-brand-navy md:text-4xl"
          >
            בחרו את הפלטפורמה שלכם והצטרפו בלחיצה אחת
          </h2>
          <p className="mt-4 text-base leading-8 text-brand-navy/70">
            כל הלינקים מרוכזים כאן. אפשר להצטרף לערוץ הטלגרם, לקבוצות הוואטסאפ
            לפי נושא, או לעמוד ולקבוצה בפייסבוק.
          </p>
        </div>

        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {sections.map(({ platform, links, meta }) => (
            <article
              key={platform}
              className={`rounded-[2rem] border ${meta.border} bg-gradient-to-b ${meta.panel} p-6 shadow-[0_24px_60px_rgba(30,42,74,0.08)]`}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <span
                    className={`inline-flex rounded-full px-3 py-1 text-xs font-black ${meta.badge}`}
                  >
                    {meta.title}
                  </span>
                  <h3 className="mt-4 text-2xl font-extrabold text-brand-navy">
                    {meta.title}
                  </h3>
                  <p className="mt-2 text-sm leading-7 text-brand-navy/70">
                    {meta.description}
                  </p>
                </div>
                <div className={`${meta.icon}`} aria-hidden="true">
                  <PlatformIcon platform={platform} />
                </div>
              </div>

              <div className="mt-6 space-y-3">
                {links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center justify-between rounded-2xl border border-brand-navy/10 bg-white/90 px-4 py-4 transition hover:-translate-y-0.5 hover:border-brand-orange/30 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-orange"
                    aria-label={`הצטרפות אל ${link.label}`}
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-navy text-white shadow-sm ${meta.icon}`}
                      >
                        <PlatformIcon platform={platform} />
                      </span>
                      <div>
                        <p className="text-sm font-extrabold text-brand-navy">
                          {link.label}
                        </p>
                        <p className="text-xs text-brand-navy/55">
                          קישור ישיר להצטרפות
                        </p>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-brand-orange transition group-hover:translate-x-[-2px]">
                      כניסה
                    </span>
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
