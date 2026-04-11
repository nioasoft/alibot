import Image from "next/image";

export function Header() {
  return (
    <header className="w-full">
      <Image
        src="/header.webp"
        alt="קהילת מכורי הדילים והמבצעים"
        width={1200}
        height={457}
        className="w-full h-auto"
        priority
      />
    </header>
  );
}
