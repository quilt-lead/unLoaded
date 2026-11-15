// Response types of the synthetic-v2 router (/api/v2/*, backend/calcgraph/move_api.py). Only the
// fields the shared components read are typed; R3 extends these as it builds the v2 UI.

export interface V2Summary {
  elements: Record<string, number>;
  records: Record<string, number>;
  relations: Record<string, number>;
  calcs: { id: string; section: string; software: string; table: string; title: string }[];
  documents: Record<"calcs" | "drawings" | "specs", boolean>;
  occurrences: number;
}

export type V2DocId = "calcs" | "drawings" | "specs";

/** One place an element appears. PDF occurrences carry doc + page + bbox (PDF points, top-left origin). */
export interface V2Occurrence {
  ref: string;
  doc: V2DocId | "ifc" | "etabs" | string;
  how: string;
  page?: number;
  bbox?: [number, number, number, number];
  sheet?: string;
  text?: string;
  text_layer?: boolean;
  global_id?: string;
  /** doc "etabs": the object label; PDF docs: the label read from the document (a schedule row's row header) */
  label?: string;
  label_error?: string;
  /** how "governing-spec": the spec article that governs this element, and which links brought it in (type, material, frame) */
  article?: string;
  via?: string[];
  story?: string;
  object_type?: string;
  error?: string;
  // doc "platforms": a construction-platform record naming this element
  platform?: string;
  platform_label?: string;
  record_type?: string;
  id?: string;
  record_ref?: string;
  number?: string;
  title?: string;
  status?: string;
  link?: string | null;
  source?: "live" | "mock" | string;
  source_label?: string | null;
}

export interface V2DesignElement {
  id: string;
  type: string;
  global_id?: string;
  size?: string;
  grid?: string;
  [k: string]: unknown;
}

export interface V2Record {
  id: string;
  kind: string;
  calc: string;
  calc_title?: string;
  sheet?: string;
  page?: number;
  bbox?: [number, number, number, number];
  elements: string[];
  inputs: string[];
  uc?: number;
  check?: string;
  software?: string;
  [k: string]: unknown;
}

export interface V2RecordPage extends V2Record {
  fed_by: string[];
  feeds: string[];
}

export interface V2Relation {
  src: string;
  dst: string;
  kind: string;
  [k: string]: unknown;
}

export interface V2ElementPage {
  id: string;
  /** which registry collection the id is in */
  kind: "element" | "type" | "record" | "spec_article" | "detail";
  /** the entity itself, whatever its kind */
  entity: Record<string, unknown>;
  element: V2DesignElement | null;
  record: V2Record | null;
  relations_out: V2Relation[];
  relations_in: V2Relation[];
  designed_by: V2Record[];
  occurrences: V2Occurrence[];
}

export interface V2Design {
  elements: V2DesignElement[];
  records: V2Record[];
  relations: V2Relation[];
  [k: string]: unknown;
}
