export interface SocialLink {
  url: string;
  label: string;
  platform: "telegram" | "whatsapp" | "facebook";
}

export const SOCIAL_LINKS: SocialLink[] = [
  {
    url: "https://t.me/+SAsvKgvm9KQzOWNk",
    label: "ערוץ הטלגרם",
    platform: "telegram",
  },
  {
    url: "https://chat.whatsapp.com/KqoWT8r700HByoFZitayKS",
    label: "קבוצת גאדג׳טים",
    platform: "whatsapp",
  },
  {
    url: "https://chat.whatsapp.com/CuINDtG7yOcIVQNCYAseR0",
    label: "קבוצת מוצרי בית ומשרד",
    platform: "whatsapp",
  },
  {
    url: "https://chat.whatsapp.com/FuK2MELgPWjBNPUr2SPhM8",
    label: "קבוצת אופנה וספורט",
    platform: "whatsapp",
  },
  {
    url: "https://chat.whatsapp.com/Gqi5mvfUz0nCQewylU5BsD",
    label: "קבוצת מוצרי יופי ובריאות",
    platform: "whatsapp",
  },
  {
    url: "https://www.facebook.com/grandDeal",
    label: "דף פייסבוק",
    platform: "facebook",
  },
  {
    url: "https://www.facebook.com/groups/354824431284295",
    label: "קבוצת פייסבוק",
    platform: "facebook",
  },
];
