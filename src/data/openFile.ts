// A plain calc-graph export JSON opened from disk: read-only view data, fed through the same two
// adapters and the same merge as a stored project (its topology comes from the export itself).
import type { Export } from '@unloaded/calc-mapper/types';
import { elementGraphToBim } from '../loaders/elementGraphToBim';
import type { ProjectViewModel } from '../types/bim';
import { exportToElementGraph, toCalcData } from './loadProject';
import { mergeProject } from './mergeProject';

export function exportFileView(exp: Export): ProjectViewModel {
  return mergeProject(elementGraphToBim(exportToElementGraph(exp)), toCalcData(exp), { source: 'file', projectId: null, modelFileUrl: null });
}
