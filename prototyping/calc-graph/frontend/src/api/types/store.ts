// Revision-store endpoints (/api/store/*, backend/calcgraph/store_api.py). Bundles are typed by the
// generated schema (src/types/schema.ts); the project row is not part of the schema.
export interface StoreProject {
  id: number;
  name: string;
  created_at: string;
  kind: "ifc" | "drawing-set";
  slug: string | null;
  head_model_rev: number | null;
  head_calc_rev: number | null;
  heads: Record<string, number>;
}
