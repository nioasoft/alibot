export interface Deal {
  id: number;
  product_id: string;
  product_name: string;
  rewritten_text: string;
  price: number;
  original_price: number | null;
  currency: string;
  price_ils: number | null;
  category: string;
  affiliate_link: string | null;
  product_link: string;
  image_url: string | null;
  is_active: boolean;
  published_at: string;
  created_at: string;
}

export interface CategoryMeta {
  slug: string;
  name: string;
  icon: string;
  color: string;
}
