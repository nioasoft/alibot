import { SOCIAL_LINKS } from "@/lib/social-links";

function TelegramIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-8 h-8 md:w-10 md:h-10 fill-current">
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  );
}

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-8 h-8 md:w-10 md:h-10 fill-current">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

function FacebookIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-8 h-8 md:w-10 md:h-10 fill-current">
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

const PLATFORM_STYLES: Record<
  string,
  { bg: string; border: string; shadow: string }
> = {
  telegram: {
    bg: "bg-gradient-to-bl from-[#0088cc] to-[#0077b5]",
    border: "border-[#0099dd]",
    shadow: "shadow-[0_4px_15px_rgba(0,136,204,0.4)]",
  },
  whatsapp: {
    bg: "bg-gradient-to-bl from-[#25D366] to-[#128C7E]",
    border: "border-[#34eb77]",
    shadow: "shadow-[0_4px_15px_rgba(37,211,102,0.4)]",
  },
  facebook: {
    bg: "bg-gradient-to-bl from-[#1877F2] to-[#0d5bbf]",
    border: "border-[#4293f5]",
    shadow: "shadow-[0_4px_15px_rgba(24,119,242,0.4)]",
  },
};

export function SocialLinks() {
  const telegram = SOCIAL_LINKS.filter((l) => l.platform === "telegram");
  const whatsapp = SOCIAL_LINKS.filter((l) => l.platform === "whatsapp");
  const facebook = SOCIAL_LINKS.filter((l) => l.platform === "facebook");

  return (
    <section
      className="py-8 md:py-10 border-b border-gray-100"
      style={{ background: "linear-gradient(to bottom, #e8e8e8, #ffffff 40%)" }}
    >
      <div className="mx-auto max-w-4xl px-4">
        <h2 className="text-center text-xl md:text-2xl font-extrabold text-brand-navy mb-2">
          הצטרפו לקהילה שלנו
        </h2>
        <p className="text-center text-sm text-gray-500 mb-6">
          בחרו את הפלטפורמה המועדפת עליכם וקבלו דילים ישירות
        </p>

        {/* Row 1: Blue - Telegram + Facebook */}
        <div className="grid grid-cols-3 gap-3 md:gap-4 mb-3 md:mb-4">
          {telegram.map((link, i) => (
            <SocialCard key={`tg-${i}`} link={link} />
          ))}
          {facebook.map((link, i) => (
            <SocialCard key={`fb-${i}`} link={link} />
          ))}
        </div>

        {/* Row 2: Green - WhatsApp */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
          {whatsapp.map((link, i) => (
            <SocialCard key={`wa-${i}`} link={link} />
          ))}
        </div>
      </div>
    </section>
  );
}

function SocialCard({
  link,
  className = "",
}: {
  link: (typeof SOCIAL_LINKS)[number];
  className?: string;
}) {
  const style = PLATFORM_STYLES[link.platform] ?? PLATFORM_STYLES.telegram;

  return (
    <a
      href={link.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`
        group relative flex flex-col items-center justify-center gap-2
        rounded-2xl p-4 md:p-5
        ${style.bg} ${style.shadow}
        border ${style.border} border-opacity-30
        text-white
        transition-all duration-200
        hover:scale-105 hover:shadow-xl
        min-h-[80px] md:min-h-[100px]
        ${className}
      `}
    >
      <PlatformIcon platform={link.platform} />
      <span className="text-xs md:text-sm font-bold whitespace-nowrap">{link.label}</span>
      <span className="text-[10px] md:text-xs opacity-70">
        לחצו להצטרפות
      </span>
    </a>
  );
}
