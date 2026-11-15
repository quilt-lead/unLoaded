import type { BimNode } from '../types/bim';

export interface GraphPoint {
  x: number;
  y: number;
}

export function selectNodesInBox(
  nodes: readonly Pick<BimNode, 'id' | 'x' | 'y' | 'r'>[],
  start: GraphPoint,
  end: GraphPoint,
): string[] {
  const left = Math.min(start.x, end.x);
  const right = Math.max(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);
  const crossing = end.x < start.x;

  return nodes
    .filter((node) => {
      const radius = Math.max(node.r, 0);
      if (!crossing) {
        return (
          node.x - radius >= left &&
          node.x + radius <= right &&
          node.y - radius >= top &&
          node.y + radius <= bottom
        );
      }

      const nearestX = Math.max(left, Math.min(node.x, right));
      const nearestY = Math.max(top, Math.min(node.y, bottom));
      return Math.hypot(node.x - nearestX, node.y - nearestY) <= radius;
    })
    .map((node) => node.id);
}
