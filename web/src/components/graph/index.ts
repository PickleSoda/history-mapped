/** Shared relation-graph UI. The cytoscape engine itself is lazy-loaded by
 *  RelationGraph on mount (see cytoscape-loader), so importing this barrel
 *  doesn't pull the graph library into a chunk. */
export { RelationGraph } from './RelationGraph';
export type { RelationGraphProps } from './RelationGraph';
export { relLabel } from './GraphFilterBar';
