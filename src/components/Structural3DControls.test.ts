import { afterEach, describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { Structural3DControls, type CameraPose } from './Structural3DControls';

// Exercise the real event handlers without a browser or a WebGL context.
class Viewport extends EventTarget {
  clientWidth = 800;
  clientHeight = 600;
  ownerDocument = { defaultView: new EventTarget() };
  private capturedPointers = new Set<number>();

  setPointerCapture(id: number) { this.capturedPointers.add(id); }
  releasePointerCapture(id: number) { this.capturedPointers.delete(id); }
  hasPointerCapture(id: number) { return this.capturedPointers.has(id); }
  getBoundingClientRect() {
    return { left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600 };
  }
}

const initialPose: CameraPose = {
  theta: 0.76,
  phi: 1.08,
  radius: 335,
  target: { x: 0, y: 78, z: 0 },
};
const liveControls: Structural3DControls[] = [];

function dispatch(target: EventTarget, type: string, properties: object = {}) {
  const event = new Event(type, { cancelable: true });
  Object.assign(event, properties);
  target.dispatchEvent(event);
}

function setup() {
  const viewport = new Viewport();
  const camera = new THREE.PerspectiveCamera(40, 800 / 600, 1, 4500);
  const onClick = vi.fn();
  const onChange = vi.fn();
  const controls = new Structural3DControls(camera, viewport as unknown as HTMLElement, initialPose, onChange, onClick);
  liveControls.push(controls);
  const pointer = (type: string, overrides: Partial<PointerEvent> = {}) => dispatch(
    type === 'pointerdown' || type === 'lostpointercapture' ? viewport : viewport.ownerDocument.defaultView,
    type,
    { pointerId: 1, isPrimary: true, pointerType: 'mouse', button: 0, buttons: 1, clientX: 200, clientY: 200, ...overrides },
  );
  const wheel = (overrides: Partial<WheelEvent> = {}) => dispatch(viewport, 'wheel', {
    deltaX: 0, deltaY: 0, deltaMode: 0, shiftKey: false, ...overrides,
  });
  return { controls, viewport, camera, pointer, wheel, onClick, onChange };
}

afterEach(() => {
  liveControls.splice(0).forEach((controls) => controls.dispose());
  vi.restoreAllMocks();
});

describe('manual 3D navigation', () => {
  it('follows orbit movement and reversal immediately, then stays still after release', () => {
    const { controls, camera, pointer, onClick, onChange } = setup();
    const startPosition = camera.position.clone();
    pointer('pointerdown');
    pointer('pointermove', { clientX: 220, clientY: 210 });
    expect(controls.getPose().theta).toBeCloseTo(initialPose.theta - 0.12);
    expect(controls.getPose().phi).toBeCloseTo(initialPose.phi - 0.06);
    expect(camera.position.equals(startPosition)).toBe(false);
    expect(onChange).toHaveBeenCalled();

    pointer('pointermove');
    expect(controls.getPose().theta).toBeCloseTo(initialPose.theta);
    expect(controls.getPose().phi).toBeCloseTo(initialPose.phi);
    pointer('pointerup');
    const stopped = controls.getPose();
    controls.update(performance.now() + 2000);
    expect(controls.getPose()).toEqual(stopped);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('pans by the requested screen distance and does not coast after release', () => {
    const { controls, camera, pointer } = setup();
    const modelPoint = new THREE.Vector3(initialPose.target.x, initialPose.target.y, initialPose.target.z);
    const startPosition = camera.position.clone();
    pointer('pointerdown', { button: 1, buttons: 4 });
    pointer('pointermove', { button: 1, buttons: 4, clientX: 230, clientY: 220 });
    const pose = controls.getPose();
    expect(pose.theta).toBe(initialPose.theta);
    expect(pose.phi).toBe(initialPose.phi);
    expect(pose.radius).toBe(initialPose.radius);
    const cameraShift = camera.position.clone().sub(startPosition);
    const targetShift = new THREE.Vector3(pose.target.x, pose.target.y, pose.target.z).sub(modelPoint);
    expect(cameraShift.distanceTo(targetShift)).toBeLessThan(1e-10);
    camera.updateMatrixWorld(true);
    const screenPosition = modelPoint.clone().project(camera);
    expect(screenPosition.x * 800 / 2).toBeCloseTo(30);
    expect(-screenPosition.y * 600 / 2).toBeCloseTo(20);

    pointer('pointerup', { button: 1, buttons: 0, clientX: 230, clientY: 220 });
    controls.update(performance.now() + 2000);
    expect(controls.getPose()).toEqual(pose);
  });

  it('applies drag zoom immediately and stops when the gesture ends', () => {
    const { controls, pointer } = setup();
    pointer('pointerdown', { button: 2, buttons: 2, ctrlKey: true });
    pointer('pointermove', { button: 2, buttons: 2, ctrlKey: true, clientY: 215 });
    expect(controls.getPose().radius).toBeCloseTo(initialPose.radius * Math.exp(15 * 0.008));
    pointer('pointerup', { button: 2, buttons: 0, ctrlKey: true, clientY: 215 });
    const stopped = controls.getPose();
    controls.update(performance.now() + 2000);
    expect(controls.getPose()).toEqual(stopped);
  });

  it('recognizes a slow drag made of one-pixel events without selecting on release', () => {
    const { controls, pointer, onClick } = setup();
    pointer('pointerdown');
    for (let x = 201; x <= 230; x += 1) pointer('pointermove', { clientX: x });
    expect(controls.getPose().theta).toBeCloseTo(initialPose.theta - 30 * 0.006);
    pointer('pointerup', { clientX: 230 });
    expect(onClick).not.toHaveBeenCalled();
  });

  it('allows a click with slight pointer jitter without moving the camera', () => {
    const { controls, pointer, onClick } = setup();
    pointer('pointerdown');
    pointer('pointermove', { clientX: 202, clientY: 201 });
    pointer('pointerup', { clientX: 202, clientY: 201 });
    expect(controls.getPose()).toEqual(initialPose);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it.each(['zoom', 'pan'] as const)('normalizes pixel, line, and page wheel units for %s', (mode) => {
    const poses = [
      { deltaMode: 0, deltaY: 96 },
      { deltaMode: 1, deltaY: 6 },
      { deltaMode: 2, deltaY: 96 / 600 },
    ].map((delta) => {
      const { controls, wheel } = setup();
      wheel({ ...delta, shiftKey: mode === 'pan' });
      const pose = controls.getPose();
      controls.update(performance.now() + 2000);
      expect(controls.getPose()).toEqual(pose);
      expect(pose).not.toEqual(initialPose);
      return pose;
    });
    expect(poses[1]).toEqual(poses[0]);
    expect(poses[2]).toEqual(poses[0]);
  });
});

describe('camera transitions', () => {
  const destination: CameraPose = { theta: 1.4, phi: 0.7, radius: 120, target: { x: 20, y: 40, z: -15 } };

  it('uses elapsed time across different frame rates and finishes at the exact requested pose', () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);
    const intermediate = [30, 60, 144].map((fps) => {
      const { controls } = setup();
      controls.moveTo(destination);
      for (let time = 1000 + 1000 / fps; time < 1120; time += 1000 / fps) controls.update(time);
      controls.update(1120);
      const pose = controls.getPose();
      expect(pose).not.toEqual(initialPose);
      expect(pose).not.toEqual(destination);
      controls.update(1300);
      expect(controls.getPose()).toEqual(destination);
      controls.update(5000);
      expect(controls.getPose()).toEqual(destination);
      return pose;
    });
    expect(intermediate[1]).toEqual(intermediate[0]);
    expect(intermediate[2]).toEqual(intermediate[0]);
  });

  it('lets a new drag take over at the currently displayed pose without a jump', () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);
    const { controls, pointer } = setup();
    controls.moveTo(destination);
    controls.update(1100);
    const displayed = controls.getPose();
    pointer('pointerdown');
    controls.update(2000);
    expect(controls.getPose()).toEqual(displayed);
    pointer('pointermove', { clientX: 210 });
    expect(controls.getPose().theta).toBeCloseTo(displayed.theta - 0.06);
    expect(controls.getPose().radius).toBe(displayed.radius);
    expect(controls.getPose().target).toEqual(displayed.target);
  });

  it('applies wheel zoom from the displayed radius and cancels an unfinished fit', () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);
    const { controls, wheel } = setup();
    controls.moveTo(destination);
    controls.update(1100);
    const displayed = controls.getPose();
    wheel({ deltaY: 50 });
    const zoomed = controls.getPose();
    expect(zoomed.radius).toBeCloseTo(displayed.radius * Math.exp(50 * 0.0014));
    expect(zoomed.target).toEqual(displayed.target);
    expect(zoomed.theta).toBe(displayed.theta);
    expect(zoomed.phi).toBe(displayed.phi);
    controls.update(2000);
    expect(controls.getPose()).toEqual(zoomed);
  });

  it('can complete a camera move immediately without leaving an animation running', () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);
    const { controls } = setup();
    controls.moveTo({ radius: 200 });
    controls.update(1100);
    controls.moveTo(destination, false);
    expect(controls.getPose()).toEqual(destination);
    controls.update(2000);
    expect(controls.getPose()).toEqual(destination);
  });

  it('resets by the shortest arc after several manual revolutions', () => {
    vi.spyOn(performance, 'now').mockReturnValue(1000);
    const { controls, camera, pointer } = setup();
    pointer('pointerdown');
    // Three full turns plus a small offset should reset through just that offset.
    const turnAngle = 6 * Math.PI + 0.4;
    const clientX = 200 + turnAngle / 0.006;
    pointer('pointermove', { clientX });
    pointer('pointerup', { clientX });
    const startTheta = controls.getPose().theta;
    controls.moveTo(initialPose);
    controls.update(1150);
    expect(controls.getPose().theta - startTheta).toBeCloseTo(0.2);
    const nearlyFinishedTime = 1299.999;
    controls.update(nearlyFinishedTime);
    const nearlyFinishedPosition = camera.position.clone();
    controls.update(1300);
    expect(controls.getPose()).toEqual(initialPose);
    // Canonicalizing the stored angle at the end must not jump the actual camera.
    expect(camera.position.distanceTo(nearlyFinishedPosition)).toBeLessThan(1e-6);
  });
});

describe('interrupted pointer gestures', () => {
  it.each(['pointercancel', 'lostpointercapture', 'blur'])('stops navigation after %s without selecting', (eventName) => {
    const { controls, viewport, pointer, onClick } = setup();
    pointer('pointerdown');
    pointer('pointermove', { clientX: 220 });
    if (eventName === 'blur') dispatch(viewport.ownerDocument.defaultView, 'blur');
    else pointer(eventName);
    const stopped = controls.getPose();
    pointer('pointermove', { clientX: 260 });
    pointer('pointerup', { clientX: 260 });
    expect(controls.getPose()).toEqual(stopped);
    expect(onClick).not.toHaveBeenCalled();
    pointer('pointerdown');
    pointer('pointermove', { clientX: 210 });
    expect(controls.getPose().theta).toBeCloseTo(stopped.theta - 0.06);
  });

  it('ignores a second pointer without ending or redirecting the active gesture', () => {
    const { controls, pointer, onClick } = setup();
    pointer('pointerdown');
    pointer('pointerdown', { pointerId: 2, isPrimary: false, clientX: 500 });
    pointer('pointermove', { pointerId: 2, isPrimary: false, clientX: 550 });
    pointer('pointerup', { pointerId: 2, isPrimary: false, clientX: 550 });
    expect(controls.getPose()).toEqual(initialPose);
    pointer('pointermove', { clientX: 210 });
    expect(controls.getPose().theta).toBeCloseTo(initialPose.theta - 0.06);
    pointer('pointerup', { clientX: 210 });
    expect(onClick).not.toHaveBeenCalled();
  });
});
