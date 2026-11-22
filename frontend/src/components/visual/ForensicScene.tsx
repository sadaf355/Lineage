import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function ForensicScene({ compact = false }: { compact?: boolean }) {
  const mount = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = mount.current;
    if (!el) return;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, el.clientWidth / Math.max(1, el.clientHeight), 0.1, 100);
    camera.position.set(0, 0, compact ? 8.5 : 9.5);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);
    const nodes: THREE.Mesh[] = [];
    const nodePositions = compact
      ? [[0,0,0],[-2.1,1.0,0],[2.0,1.2,0],[-1.6,-1.25,0],[1.7,-1.05,0],[0,.15,-1.3]]
      : [[0,0,0],[-2.6,1.4,0],[2.6,1.55,0],[-2.25,-1.5,0],[2.25,-1.35,0],[0,.3,-1.8],[-.1,2.45,-.2]];
    const material = new THREE.MeshStandardMaterial({ color: 0x9ff0c4, emissive: 0x163d2b, emissiveIntensity: 1.7, metalness: .45, roughness: .28 });
    const centerMat = new THREE.MeshStandardMaterial({ color: 0xf4fff7, emissive: 0x5ce49b, emissiveIntensity: 2.4, metalness: .2, roughness: .18 });
    nodePositions.forEach((p, i) => {
      const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(i === 0 ? .42 : .22, 2), i === 0 ? centerMat : material);
      mesh.position.set(p[0], p[1], p[2]);
      group.add(mesh); nodes.push(mesh);
    });
    const lineMat = new THREE.LineBasicMaterial({ color: 0x5ee2a0, transparent: true, opacity: .35 });
    const edges = [[0,1],[0,2],[0,3],[0,4],[0,5],[5,2],[5,1],[6,1],[6,2]];
    edges.forEach(([a,b]) => {
      if (!nodes[a] || !nodes[b]) return;
      const geo = new THREE.BufferGeometry().setFromPoints([nodes[a].position, nodes[b].position]);
      group.add(new THREE.Line(geo, lineMat));
    });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(compact ? 2.8 : 3.5, .012, 12, 160), new THREE.MeshBasicMaterial({color:0x69e7aa, transparent:true, opacity:.16}));
    ring.rotation.x = Math.PI / 2.2;
    group.add(ring);
    const particles = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ color:0x9ff0c4, size:.025, transparent:true, opacity:.45 }));
    const positions = new Float32Array(240 * 3);
    for (let i=0;i<240;i++){ positions[i*3]=(Math.random()-.5)*8; positions[i*3+1]=(Math.random()-.5)*6; positions[i*3+2]=(Math.random()-.5)*4; }
    particles.geometry.setAttribute('position', new THREE.BufferAttribute(positions,3)); scene.add(particles);
    const ambient = new THREE.AmbientLight(0xbaf7d3, 1.3); scene.add(ambient);
    const light = new THREE.PointLight(0x62e7a2, 18, 14); light.position.set(2,3,4); scene.add(light);
    // Respect the OS "reduce motion" setting: draw one still frame instead of looping.
    const reduceMotion = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame=0; let raf=0;
    const animate=()=>{ frame += .008; group.rotation.y = Math.sin(frame*.55)*.16; group.rotation.x = Math.sin(frame*.35)*.06; ring.rotation.z += .002; nodes.forEach((n,i)=>n.position.y += Math.sin(frame*1.5+i)*.0007); particles.rotation.y += .00045; renderer.render(scene,camera); if(!reduceMotion) raf=requestAnimationFrame(animate); };
    animate();
    const onResize=()=>{ if(!el) return; camera.aspect=el.clientWidth/Math.max(1,el.clientHeight); camera.updateProjectionMatrix(); renderer.setSize(el.clientWidth,el.clientHeight); };
    window.addEventListener('resize',onResize);

    // Optional Blender hero asset. If /models/hero.glb (or VITE_HERO_GLB) exists it replaces the centre node; if it is
    // missing or fails to load, the procedural scene above stays exactly as it is. See docs/HERO_ASSET.md.
    let disposed = false;
    const heroUrl = (import.meta.env.VITE_HERO_GLB as string | undefined) ?? "/models/hero.glb";
    if (heroUrl) {
      fetch(heroUrl, { method: "HEAD" })
        .then((r) => (r.ok && !/text\/html/.test(r.headers.get("content-type") ?? "") ? import("three/examples/jsm/loaders/GLTFLoader.js") : null))
        .then((mod) => (mod && !disposed ? new mod.GLTFLoader().loadAsync(heroUrl) : null))
        .then((gltf) => {
          if (!gltf || disposed) return;
          const model = gltf.scene;
          const box = new THREE.Box3().setFromObject(model);
          const size = box.getSize(new THREE.Vector3()); const center = box.getCenter(new THREE.Vector3());
          const fit = (compact ? 2.2 : 2.8) / Math.max(size.x, size.y, size.z, 1e-6);
          model.scale.setScalar(fit); model.position.copy(center.multiplyScalar(-fit));
          const holder = new THREE.Group(); holder.add(model); group.add(holder);
          if (nodes[0]) nodes[0].visible = false;
          if (reduceMotion) renderer.render(scene, camera);
        })
        .catch(() => { /* no asset or unsupported: keep the procedural scene */ });
    }
    return ()=>{ disposed = true; cancelAnimationFrame(raf); window.removeEventListener('resize',onResize); renderer.dispose(); el.removeChild(renderer.domElement); scene.traverse(o=>{ const m=o as THREE.Mesh; if(m.geometry) m.geometry.dispose(); if(m.material) { const mat=m.material as THREE.Material; mat.dispose(); }}); };
  }, [compact]);
  return <div ref={mount} className="forensic-scene" aria-hidden="true" />;
}
