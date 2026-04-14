import { redirect } from "next/navigation";

export const revalidate = 300;

export default async function CategoryPage() {
  redirect("/");
}
