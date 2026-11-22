# Blender hero asset (`.glb`)

The 3D scene on the Landing and Dashboard screens (`components/visual/ForensicScene.tsx`) is procedural by default.
If a glTF binary exists at **`/models/hero.glb`** (put it in `frontend/public/models/`) it is loaded with Three.js's
`GLTFLoader` and replaces the centre node. If it is absent or fails to load, nothing changes. Override the path with `VITE_HERO_GLB`;
set it to an empty string to disable loading.

**No asset ships in this repository.** Making one needs a 3D artist or someone who knows Blender; the code path is untested
against a real `.glb` (no browser or asset was available when it was written). Test it with your model before relying on it.

## Export checklist (Blender → glTF)
* File → Export → glTF 2.0 (`.glb`), **Apply Modifiers** on, **+Y Up** on, Compression: **Draco** only if you also add
  a Draco decoder to the loader (this loader does not configure one, so leave compression off).
* Keep it under ~1.5 MB and ~50k triangles; this renders on every landing visit, on phones.
* Use PBR materials (Principled BSDF). Baked lighting is not needed; the scene provides an ambient and a point light.
* One object, centred roughly at the origin. The loader rescales it to fit and recentres it.
* Do not embed anything identifying, copyrighted or licensed without a licence that permits redistribution.
* No animation is played. Rotation comes from the scene.

## Behaviour to know
* Respects the OS reduced-motion setting (renders one still frame).
* The scene is decorative (`aria-hidden`). Nothing the app reports depends on it.
