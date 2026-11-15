/**
 * Pluggable model importers: file bytes -> ElementGraph (or a calc-graph export).
 *
 * Pipelines
 * - .ifc (STEP)                        -> @unloaded/ifc-parser -> ModelInput -> buildGraph -> ElementGraph
 * - .json, dispatched on content:
 *     serialized element graph         -> ElementGraph.deserialize
 *     ModelInput                       -> buildGraph -> ElementGraph
 *     legacy BIM graph ({ nodes, links }) -> legacyBimJson.ts -> ModelInput -> buildGraph -> ElementGraph
 *     calc-graph export                -> returned as-is for src/data/loadProject.ts (read-only view)
 *     calc-graph project file          -> validated (@unloaded/project-file parseProjectFile) for projectStore importProject
 *
 * A model's ElementGraph is stored with its revision in the local project store and goes through
 * src/loaders/elementGraphToBim.ts (the only ElementGraph -> view adapter).
 * New formats (Revit, Tekla, ETABS, ...) should emit a ModelInput and reuse the element-graph
 * pipeline, so connectivity inference and load paths come for free.
 */
import { buildGraph, ElementGraph, ELEMENT_GRAPH_FORMAT, type ModelInput, type SerializedElementGraph } from '@unloaded/element-graph';
import type { IfcParsePhase } from '@unloaded/ifc-parser';
import type { Export } from '@unloaded/calc-mapper/types';
import { isCalcGraphExport, normaliseExport } from '../data/loadProject';
import { isProjectFileFormat, parseProjectFile, type ProjectFile } from '@unloaded/project-file';
import { isLegacyBimJson, legacyToElementGraph } from './legacyBimJson';

export type ImportResult =
  | {
      kind: 'model';
      /** Domain graph: the single source of elements and topology. */
      elementGraph: ElementGraph;
      projectName: string;
      /** 'ifc' when the bytes were an IFC (it can then be uploaded as a model revision). */
      format: 'ifc' | 'element-graph' | 'model-input' | 'legacy-json';
      /** Parser + graph-build warnings, prefixed with their origin. */
      warnings: string[];
    }
  | { kind: 'export'; export: Export; warnings: string[] }
  | { kind: 'project-file'; project: ProjectFile; warnings: string[] };

export interface BimParserPlugin {
  id: string;
  name: string;
  extensions: string[];
  /** Cheap sniff on the file name and first bytes. */
  canParse: (fileName: string, head: Uint8Array) => boolean;
  parse: (bytes: Uint8Array, fileName: string, onProgress: (message: string) => void) => Promise<ImportResult>;
}

/** Directory containing web-ifc.wasm (copied into public/wasm by scripts/copy-assets.mjs). */
export const WASM_PATH = `${import.meta.env.BASE_URL}wasm/`;

const PHASE_LABEL: Record<IfcParsePhase, string> = {
  init: 'Starting IFC engine',
  open: 'Opening model',
  index: 'Indexing entities',
  elements: 'Reading elements',
  geometry: 'Computing geometry',
  relations: 'Reading relations',
  done: 'Parsed',
};

/** Let the browser paint progress before synchronous heavy work. */
const nextFrame = () => new Promise<void>((r) => setTimeout(r, 16));

function stripExt(fileName: string): string {
  return fileName.replace(/\.[^.]+$/, '');
}

function looksLikeJson(head: Uint8Array): boolean {
  for (const b of head) {
    if (b === 0x20 || b === 0x0a || b === 0x0d || b === 0x09 || b === 0xef || b === 0xbb || b === 0xbf) continue;
    return b === 0x7b; // "{"
  }
  return false;
}

function hasStepHeader(head: Uint8Array): boolean {
  let s = '';
  for (let i = 0; i < Math.min(head.length, 64); i++) s += String.fromCharCode(head[i]!);
  return s.replace(/^﻿|^ï»¿/, '').trimStart().startsWith('ISO-10303-21');
}

function isSerializedGraph(d: unknown): d is SerializedElementGraph {
  return typeof d === 'object' && d !== null && (d as { format?: unknown }).format === ELEMENT_GRAPH_FORMAT;
}

function isModelInput(d: unknown): d is ModelInput {
  if (typeof d !== 'object' || d === null) return false;
  const m = d as Partial<ModelInput>;
  return Array.isArray(m.elements) && typeof m.meta === 'object' && m.meta !== null;
}

function decodeJson(bytes: Uint8Array, fileName: string): unknown {
  try {
    return JSON.parse(new TextDecoder().decode(bytes).replace(/^﻿/, ''));
  } catch (e) {
    throw new Error(`${fileName}: invalid JSON (${(e as Error).message})`);
  }
}

async function fromModelInput(
  input: ModelInput,
  fileName: string,
  format: 'ifc' | 'model-input',
  onProgress: (m: string) => void
): Promise<ImportResult> {
  onProgress(`Inferring connectivity (${input.elements.length} elements)`);
  await nextFrame();
  const { graph: elementGraph, warnings } = buildGraph(input);
  return {
    kind: 'model',
    elementGraph,
    projectName: input.meta.project || stripExt(fileName),
    format,
    warnings: [...(input.warnings ?? []).map((w) => `parser: ${w}`), ...warnings.map((w) => `graph: ${w}`)],
  };
}

export const BIM_PARSERS: BimParserPlugin[] = [
  {
    id: 'ifc',
    name: 'IFC (web-ifc) → Element Graph',
    extensions: ['.ifc'],
    canParse: (fileName, head) => /\.ifc$/i.test(fileName) || hasStepHeader(head),
    parse: async (bytes, fileName, onProgress) => {
      // web-ifc (~3 MB JS + 1.2 MB wasm) is only fetched when an IFC is opened.
      const { parseIfc } = await import('@unloaded/ifc-parser');
      let lastPhase: IfcParsePhase | null = null;
      const input = await parseIfc(bytes, {
        fileName,
        wasmPath: WASM_PATH,
        onProgress(phase) {
          if (phase !== lastPhase) {
            lastPhase = phase;
            onProgress(PHASE_LABEL[phase]);
          }
        },
      });
      return fromModelInput(input, fileName, 'ifc', onProgress);
    },
  },
  {
    id: 'json',
    name: 'JSON (Element Graph / ModelInput / legacy BIM graph / calc-graph export / project file)',
    extensions: ['.json'],
    canParse: (fileName, head) => /\.json$/i.test(fileName) || looksLikeJson(head),
    parse: async (bytes, fileName, onProgress) => {
      const data = decodeJson(bytes, fileName);
      if (isSerializedGraph(data)) {
        onProgress('Loading element graph');
        await nextFrame();
        return {
          kind: 'model',
          elementGraph: ElementGraph.deserialize(data),
          projectName: data.meta?.project || stripExt(fileName),
          format: 'element-graph',
          warnings: [],
        };
      }
      if (isModelInput(data)) return fromModelInput(data, fileName, 'model-input', onProgress);
      // a file that says it is a project file is validated in full; its error names the field at fault
      if (isProjectFileFormat(data)) return { kind: 'project-file', project: parseProjectFile(data), warnings: [] };
      if (isCalcGraphExport(data)) return { kind: 'export', export: normaliseExport(data), warnings: [] };
      if (isLegacyBimJson(data)) {
        onProgress('Converting legacy BIM JSON and inferring connectivity');
        await nextFrame();
        const { graph, projectName, warnings } = legacyToElementGraph(data, fileName);
        return { kind: 'model', elementGraph: graph, projectName, format: 'legacy-json', warnings };
      }
      throw new Error(`${fileName}: JSON is not an element graph, a ModelInput, a legacy BIM graph, a calc-graph export or a project file`);
    },
  },
];

export const ACCEPTED_EXTENSIONS = Array.from(new Set(BIM_PARSERS.flatMap((p) => p.extensions)));

/** Pick the first parser that accepts the file and run it. */
export async function importModel(
  fileName: string,
  bytes: Uint8Array,
  onProgress: (message: string) => void = () => {}
): Promise<ImportResult & { parser: BimParserPlugin }> {
  const head = bytes.subarray(0, 1024);
  const parser = BIM_PARSERS.find((p) => p.canParse(fileName, head));
  if (!parser) {
    throw new Error(`${fileName}: unsupported file. Expected ${ACCEPTED_EXTENSIONS.join(' or ')}.`);
  }
  onProgress(`Reading ${fileName}`);
  await nextFrame();
  return { ...(await parser.parse(bytes, fileName, onProgress)), parser };
}
