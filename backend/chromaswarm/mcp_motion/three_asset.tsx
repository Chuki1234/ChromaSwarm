"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

type Vec3 = [number, number, number];
type MeshSpec = {
  geometry: "box" | "sphere" | "plane" | "torus" | "icosahedron";
  size?: number[]; position?: Vec3; rotation?: Vec3; scale?: Vec3;
  color?: string; metalness?: number; roughness?: number; opacity?: number; texture?: string;
};
export type SceneSpec = {
  model_url?: string; poster?: string; background?: string;
  camera?: { projection?: "perspective" | "orthographic"; position?: Vec3; target?: Vec3; fov?: number; extent?: number };
  objects?: MeshSpec[];
  lights?: Array<{ kind: "ambient" | "directional" | "point"; color?: string; intensity?: number; position?: Vec3 }>;
  tracks?: Array<{ object: number; property: "rotation" | "position" | "scale"; from: Vec3; to: Vec3; duration: number }>;
};

// Layout belongs to the measured DOM host. The renderer never invents its margin/gap/position.
export function ThreeAsset({ scene: spec, assetId, targetSelector }: { scene: SceneSpec; assetId: string; targetSelector?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const [loaded, setLoaded] = useState(!spec.model_url);
  const [external, setExternal] = useState(false);
  useEffect(() => {
    const existing = targetSelector ? document.querySelector<HTMLCanvasElement>(targetSelector) : null;
    const element = existing || host.current;
    if (!element) return;
    setExternal(!!existing);
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: existing || undefined, alpha: true, antialias: true }); }
    catch { setError(true); return; }
    let disposed = false;
    const scene = new THREE.Scene();
    if (spec.background) scene.background = new THREE.Color(spec.background);
    renderer.setPixelRatio(existing ? 1 : Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    if (!existing) {
      renderer.domElement.style.cssText = "display:block;width:100%;height:100%";
      element.appendChild(renderer.domElement);
    }
    const cameraSpec = spec.camera || {};
    const camera = cameraSpec.projection === "orthographic"
      ? new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 1000)
      : new THREE.PerspectiveCamera(cameraSpec.fov || 45, 1, 0.01, 1000);
    camera.position.fromArray(cameraSpec.position || [0, 0, 5]);
    camera.lookAt(new THREE.Vector3(...(cameraSpec.target || [0, 0, 0])));
    const objects: THREE.Object3D[] = [];
    const geometries: THREE.BufferGeometry[] = [];
    const materials: THREE.Material[] = [];
    const textures: THREE.Texture[] = [];
    const releaseObject = (object: THREE.Object3D) => object.traverse(child => {
      const mesh = child as THREE.Mesh;
      mesh.geometry?.dispose();
      for (const material of (Array.isArray(mesh.material) ? mesh.material : mesh.material ? [mesh.material] : [])) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose();
        material.dispose();
      }
    });
    for (const item of spec.objects || []) {
      const [a = 1, b = 1, c = 1] = item.size || [];
      const geometry = item.geometry === "sphere" ? new THREE.SphereGeometry(a, 32, 24)
        : item.geometry === "plane" ? new THREE.PlaneGeometry(a, b)
        : item.geometry === "torus" ? new THREE.TorusGeometry(a, b, 16, 64)
        : item.geometry === "icosahedron" ? new THREE.IcosahedronGeometry(a, 1)
        : new THREE.BoxGeometry(a, b, c);
      geometries.push(geometry);
      const material = new THREE.MeshStandardMaterial({ color: item.color || "#ffffff", metalness: item.metalness || 0,
        roughness: item.roughness ?? 0.5, opacity: item.opacity ?? 1, transparent: (item.opacity ?? 1) < 1, side: THREE.DoubleSide });
      materials.push(material);
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.fromArray(item.position || [0, 0, 0]);
      mesh.rotation.set(...(item.rotation || [0, 0, 0]));
      mesh.scale.fromArray(item.scale || [1, 1, 1]);
      if (item.texture) new THREE.TextureLoader().load(item.texture, texture => {
        if (disposed) { texture.dispose(); return; }
        textures.push(texture); texture.colorSpace = THREE.SRGBColorSpace;
        material.map = texture; material.needsUpdate = true; renderer.render(scene, camera);
      }, undefined, () => { if (!disposed) setError(true); });
      scene.add(mesh); objects.push(mesh);
    }
    const lights: NonNullable<SceneSpec["lights"]> = spec.lights || [{ kind: "ambient", intensity: 2 }];
    for (const item of lights) {
      const light = item.kind === "directional" ? new THREE.DirectionalLight(item.color || "#ffffff", item.intensity ?? 1)
        : item.kind === "point" ? new THREE.PointLight(item.color || "#ffffff", item.intensity ?? 1)
        : new THREE.AmbientLight(item.color || "#ffffff", item.intensity ?? 1);
      light.position.fromArray(item.position || [0, 2, 4]); scene.add(light);
    }
    let model: THREE.Object3D | undefined;
    let mixer: THREE.AnimationMixer | undefined;
    if (spec.model_url) new GLTFLoader().load(spec.model_url, gltf => {
      if (disposed) { releaseObject(gltf.scene); return; }
      model = gltf.scene; scene.add(model); objects.push(model);
      mixer = new THREE.AnimationMixer(model);
      gltf.animations.forEach(clip => mixer!.clipAction(clip).play());
      setLoaded(true);
      draw(performance.now());
    }, undefined, () => { if (!disposed) setError(true); });
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    let start: number | undefined;
    function draw(time: number) {
      start ??= time;
      const seconds = reduced.matches ? 0 : (time - start) / 1000;
      mixer?.setTime(seconds);
      for (const track of spec.tracks || []) {
        const object = objects[track.object];
        if (!object) continue;
        const t = (seconds % track.duration) / track.duration;
        const value = track.from.map((v, i) => v + (track.to[i] - v) * t) as Vec3;
        if (track.property === "rotation") object.rotation.set(...value);
        else object[track.property].fromArray(value);
      }
      renderer.render(scene, camera);
    }
    const resize = () => {
      const { width, height } = element.getBoundingClientRect();
      if (width < 1 || height < 1) return;
      renderer.setSize(width, height, false);
      if (camera instanceof THREE.PerspectiveCamera) camera.aspect = width / height;
      else { const extent = cameraSpec.extent || 2; camera.left = -extent * width / height; camera.right = -camera.left; camera.top = extent; camera.bottom = -extent; }
      camera.updateProjectionMatrix(); draw(performance.now());
    };
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    const motion = () => { renderer.setAnimationLoop(reduced.matches ? null : draw); draw(performance.now()); };
    reduced.addEventListener("change", motion); motion();
    return () => {
      disposed = true; renderer.setAnimationLoop(null); observer.disconnect(); reduced.removeEventListener("change", motion);
      if (model) { mixer?.stopAllAction(); mixer?.uncacheRoot(model); releaseObject(model); }
      geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose());
      renderer.dispose(); if (!existing) renderer.domElement.remove();
    };
  }, [spec, targetSelector]);
  return <div ref={host} data-three-asset={assetId} data-state={error ? "unresolved" : loaded ? "ready" : "loading"}
    style={{ display: external ? "none" : undefined, width: "100%", height: "100%", position: "relative" }}>
    {error && spec.poster && <img src={spec.poster} alt="" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain" }} />}
  </div>;
}
