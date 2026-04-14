import inviteLinks from "@/data/invite-links.json";

export interface SocialLink {
  url: string;
  label: string;
  platform: "telegram" | "whatsapp" | "facebook";
  footerLabel: string;
}

export const SOCIAL_LINKS = inviteLinks as SocialLink[];
