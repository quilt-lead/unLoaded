import * as THREE from 'three';

export interface CameraPose {
  theta: number;
  phi: number;
  radius: number;
  target: { x: number; y: number; z: number };
}

const TRANSITION_MS = 300;
const DRAG_THRESHOLD_PX = 3;

/** Direct manipulation for navigation; only explicit Fit/Reset moves are animated. */
export class Structural3DControls {
  private pose: CameraPose;
  private transition: { from: CameraPose; to: CameraPose; start: number } | null = null;
  private drag: {
    pointerId: number;
    button: number;
    mode: 'orbit' | 'pan' | 'zoom';
    startX: number;
    startY: number;
    prevX: number;
    prevY: number;
    moved: boolean;
  } | null = null;
  private readonly eventWindow: Window;
  private readonly forward = new THREE.Vector3();
  private readonly right = new THREE.Vector3();
  private readonly up = new THREE.Vector3();

  constructor(
    private readonly camera: THREE.PerspectiveCamera,
    private readonly element: HTMLElement,
    initialPose: CameraPose,
    private readonly onChange: () => void,
    private readonly onClick: (event: PointerEvent) => void,
  ) {
    this.pose = { ...initialPose, target: { ...initialPose.target } };
    this.eventWindow = element.ownerDocument.defaultView!;
    this.updateCamera();
    element.addEventListener('pointerdown', this.onPointerDown);
    element.addEventListener('lostpointercapture', this.onPointerCancel);
    element.addEventListener('wheel', this.onWheel, { passive: false });
    element.addEventListener('contextmenu', this.onContextMenu);
    this.eventWindow.addEventListener('pointermove', this.onPointerMove);
    this.eventWindow.addEventListener('pointerup', this.onPointerUp);
    this.eventWindow.addEventListener('pointercancel', this.onPointerCancel);
    this.eventWindow.addEventListener('blur', this.cancelDrag);
  }

  getPose(): CameraPose {
    return { ...this.pose, target: { ...this.pose.target } };
  }

  moveTo(destination: Partial<CameraPose>, animate = true): void {
    const to = { ...this.pose, ...destination, target: { ...(destination.target ?? this.pose.target) } };
    if (animate) {
      this.transition = { from: this.getPose(), to, start: performance.now() };
    } else {
      this.transition = null;
      this.pose = to;
      this.updateCamera();
    }
  }

  update(now: number): void {
    if (!this.transition) return;
    const { from, to, start } = this.transition;
    const progress = Math.max(0, Math.min(1, (now - start) / TRANSITION_MS));
    // Elapsed time, rather than a fraction per frame, keeps Fit/Reset consistent
    // at different refresh rates and gives them an exact end instead of a tail.
    const ease = progress * progress * (3 - 2 * progress);
    // Orbit angles accumulate. Reset must take the short path even after many turns.
    const thetaDelta = THREE.MathUtils.euclideanModulo(to.theta - from.theta + Math.PI, Math.PI * 2) - Math.PI;
    this.pose.theta = from.theta + thetaDelta * ease;
    this.pose.phi = THREE.MathUtils.lerp(from.phi, to.phi, ease);
    this.pose.radius = THREE.MathUtils.lerp(from.radius, to.radius, ease);
    this.pose.target.x = THREE.MathUtils.lerp(from.target.x, to.target.x, ease);
    this.pose.target.y = THREE.MathUtils.lerp(from.target.y, to.target.y, ease);
    this.pose.target.z = THREE.MathUtils.lerp(from.target.z, to.target.z, ease);
    if (progress === 1) {
      this.pose = to;
      this.transition = null;
    }
    this.updateCamera();
  }

  dispose(): void {
    this.cancelDrag();
    this.transition = null;
    this.element.removeEventListener('pointerdown', this.onPointerDown);
    this.element.removeEventListener('lostpointercapture', this.onPointerCancel);
    this.element.removeEventListener('wheel', this.onWheel);
    this.element.removeEventListener('contextmenu', this.onContextMenu);
    this.eventWindow.removeEventListener('pointermove', this.onPointerMove);
    this.eventWindow.removeEventListener('pointerup', this.onPointerUp);
    this.eventWindow.removeEventListener('pointercancel', this.onPointerCancel);
    this.eventWindow.removeEventListener('blur', this.cancelDrag);
  }

  private updateCamera(): void {
    const { theta, phi, radius, target } = this.pose;
    this.camera.position.set(
      target.x + radius * Math.sin(phi) * Math.sin(theta),
      target.y + radius * Math.cos(phi),
      target.z + radius * Math.sin(phi) * Math.cos(theta),
    );
    this.camera.lookAt(target.x, target.y, target.z);
    this.camera.updateMatrixWorld();
    this.onChange();
  }

  private panByPixels(dx: number, dy: number): void {
    const height = Math.max(this.element.clientHeight, 1);
    const unitsPerPixel = (2 * this.pose.radius * Math.tan(THREE.MathUtils.degToRad(this.camera.fov) / 2)) / height;
    this.camera.getWorldDirection(this.forward);
    this.right.crossVectors(this.forward, this.camera.up).normalize();
    this.up.crossVectors(this.right, this.forward).normalize();
    this.pose.target.x += (-dx * this.right.x + dy * this.up.x) * unitsPerPixel;
    this.pose.target.y += (-dx * this.right.y + dy * this.up.y) * unitsPerPixel;
    this.pose.target.z += (-dx * this.right.z + dy * this.up.z) * unitsPerPixel;
  }

  private onPointerDown = (event: PointerEvent): void => {
    if (this.drag || event.button < 0 || event.button > 2 || event.isPrimary === false) return;
    event.preventDefault();
    event.stopPropagation();
    // Take over at the displayed pose, never at a pending animation destination.
    this.transition = null;
    this.drag = {
      pointerId: event.pointerId,
      button: event.button,
      mode: event.button === 1 || (event.shiftKey && event.button === 2)
        ? 'pan'
        : event.ctrlKey && event.button === 2 ? 'zoom' : 'orbit',
      startX: event.clientX,
      startY: event.clientY,
      prevX: event.clientX,
      prevY: event.clientY,
      moved: false,
    };
    this.element.setPointerCapture(event.pointerId);
  };

  private onPointerMove = (event: PointerEvent): void => {
    const drag = this.drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    if (event.buttons === 0) {
      this.cancelDrag();
      return;
    }
    if (!drag.moved) {
      // Measure the whole gesture: many small samples are still a drag.
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) <= DRAG_THRESHOLD_PX) return;
      drag.moved = true;
    }
    const dx = event.clientX - drag.prevX;
    const dy = event.clientY - drag.prevY;
    this.transition = null;
    if (drag.mode === 'pan') {
      this.panByPixels(dx, dy);
    } else if (drag.mode === 'zoom') {
      this.pose.radius = Math.max(0.5, this.pose.radius * Math.exp(dy * 0.008));
    } else {
      this.pose.theta -= dx * 0.006;
      this.pose.phi = THREE.MathUtils.clamp(this.pose.phi - dy * 0.006, 0.22, Math.PI * 0.48);
    }
    drag.prevX = event.clientX;
    drag.prevY = event.clientY;
    this.updateCamera();
  };

  private onPointerUp = (event: PointerEvent): void => {
    const drag = this.drag;
    if (!drag || event.pointerId !== drag.pointerId) return;
    const isClick = drag.button === 0 && !drag.moved
      && Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) <= DRAG_THRESHOLD_PX;
    this.cancelDrag();
    if (isClick) this.onClick(event);
  };

  private onPointerCancel = (event: PointerEvent): void => {
    if (event.pointerId === this.drag?.pointerId) this.cancelDrag();
  };

  private cancelDrag = (): void => {
    const drag = this.drag;
    this.drag = null;
    if (drag && this.element.hasPointerCapture(drag.pointerId)) {
      this.element.releasePointerCapture(drag.pointerId);
    }
  };

  private onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    event.stopPropagation();
    this.transition = null;
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? Math.max(this.element.clientHeight, 1) : 1;
    if (event.shiftKey) {
      this.panByPixels(-(event.deltaX || event.deltaY) * unit, 0);
    } else {
      this.pose.radius = Math.max(0.5, this.pose.radius * Math.exp(event.deltaY * unit * 0.0014));
    }
    this.updateCamera();
  };

  private onContextMenu = (event: MouseEvent): void => event.preventDefault();
}
