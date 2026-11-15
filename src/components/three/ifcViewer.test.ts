import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import { IfcViewer, type MeshStyle } from './ifcViewer';

const selected: MeshStyle = { color: '#00aeef', opacity: 1, visible: true, glow: '#00aeef' };
const dimmed: MeshStyle = { ...selected, opacity: 0.06, glow: null };

function fixture(transparent: boolean) {
  // Exercise the real style method and Three.js material lifecycle without constructing WebGL.
  // One element can own multiple meshes, each with its own cached shader program.
  const meshes = [0, 1].map(() => new THREE.Mesh(
    new THREE.BufferGeometry(),
    new THREE.MeshLambertMaterial({ transparent }),
  ));
  const viewer: IfcViewer = Object.create(IfcViewer.prototype);
  viewer.meshes = new Map([['beam', meshes]]);
  return { viewer, meshes };
}

describe('IfcViewer selection styling', () => {
  it('invalidates opaque shaders when a previously highlighted element dims', () => {
    const { viewer, meshes } = fixture(false);
    viewer.style('beam', selected);
    const versions = meshes.map((m) => m.material.version);

    viewer.style('beam', dimmed);

    meshes.forEach((mesh, i) => {
      expect(mesh.material.opacity).toBe(0.06);
      expect(mesh.material.transparent).toBe(true);
      // Without a version bump, the cached OPAQUE shader forces alpha to 1 despite opacity.
      expect(mesh.material.version).toBeGreaterThan(versions[i]);
      expect(mesh.material.depthWrite).toBe(false);
      expect(mesh.material.emissiveIntensity).toBe(0);
    });
  });

  it('updates shaders in both directions across repeated selection changes', () => {
    const { viewer, meshes } = fixture(true);
    for (const style of [selected, dimmed, selected, dimmed]) {
      const versions = meshes.map((m) => m.material.version);
      viewer.style('beam', style);
      meshes.forEach((mesh, i) => {
        expect(mesh.material.version).toBeGreaterThan(versions[i]);
        expect(mesh.material.transparent).toBe(style.opacity < 1);
        expect(mesh.material.opacity).toBe(style.opacity);
      });
    }
  });

  it('keeps cached shaders when only opacity, color, or glow changes within the same mode', () => {
    const { viewer, meshes } = fixture(true);
    const versions = meshes.map((m) => m.material.version);
    const translucent: MeshStyle = { color: '#ff1493', opacity: 0.42, visible: true, glow: '#ff1493' };

    viewer.style('beam', dimmed);
    viewer.style('beam', translucent);

    meshes.forEach((mesh, i) => {
      expect(mesh.material.version).toBe(versions[i]);
      expect(mesh.material.opacity).toBe(0.42);
      expect(mesh.material.color.getHexString()).toBe('ff1493');
      expect(mesh.material.emissive.getHexString()).toBe('ff1493');
    });
  });
});
