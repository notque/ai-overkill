---
description: InstancedMesh, BufferGeometry manipulation, draw call batching, LOD, texture compression, and memory disposal for Three.js r150+
agent: threejs-builder
category: performance
version_range: "Three.js r150+"
---

# Performance Patterns Reference

> **Scope**: Three.js-specific performance patterns — instancing, buffer manipulation, draw call budgets, LOD, and memory management. Generic JavaScript optimization is out of scope.
> **Version range**: Three.js r150+
> **Hitting a frame-rate target?** Run the `hill-climb` skill — baseline p1-low FPS, profile, then accept or revert one change per iteration (`skills/meta/hill-climb/references/domain-playbooks.md`).
> **Generated**: 2026-04-08

---

## InstancedMesh for Thousands of Objects

`InstancedMesh` renders N copies of the same geometry in a single draw call. Use it when you need more than ~50 identical objects (particles, foliage, crowds).

```javascript
const count = 5000;
const geometry = new THREE.BoxGeometry(0.1, 0.1, 0.1);
const material = new THREE.MeshStandardMaterial({ color: 0xffffff });

const instancedMesh = new THREE.InstancedMesh(geometry, material, count);
instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage); // if positions change per frame

const matrix = new THREE.Matrix4();
const position = new THREE.Vector3();
const quaternion = new THREE.Quaternion();
const scale = new THREE.Vector3(1, 1, 1);

// Set each instance's transform
for (let i = 0; i < count; i++) {
  position.set(
    (Math.random() - 0.5) * 20,
    (Math.random() - 0.5) * 20,
    (Math.random() - 0.5) * 20,
  );
  matrix.compose(position, quaternion, scale);
  instancedMesh.setMatrixAt(i, matrix);
}
instancedMesh.instanceMatrix.needsUpdate = true; // required after updates
scene.add(instancedMesh);

// Per-frame update (animating instances):
renderer.setAnimationLoop((time) => {
  for (let i = 0; i < count; i++) {
    instancedMesh.getMatrixAt(i, matrix);
    matrix.elements[13] += Math.sin(time * 0.001 + i) * 0.001; // move Y
    instancedMesh.setMatrixAt(i, matrix);
  }
  instancedMesh.instanceMatrix.needsUpdate = true;
  renderer.render(scene, camera);
});
```

### Per-Instance Color (r150+)

```javascript
// InstancedMesh supports per-instance color without a custom shader
const color = new THREE.Color();
for (let i = 0; i < count; i++) {
  color.setHSL(i / count, 0.8, 0.6);
  instancedMesh.setColorAt(i, color);
}
instancedMesh.instanceColor.needsUpdate = true; // required after updates
```

---

## BufferGeometry Manipulation

### Typed Array Access for Maximum Speed

```javascript
// Reading existing geometry attributes
const geometry = new THREE.PlaneGeometry(10, 10, 64, 64);
const positions = geometry.attributes.position; // BufferAttribute
const posArray = positions.array; // Float32Array — direct typed array access

// Modify in place (fast — no GC pressure)
for (let i = 0; i < posArray.length; i += 3) {
  posArray[i + 1] = Math.sin(posArray[i] * 0.5) * 0.5; // modify Y
}
positions.needsUpdate = true; // signal GPU upload
geometry.computeVertexNormals();  // recalculate after vertex changes
```

### Custom BufferGeometry from Scratch

```javascript
// Interleaved buffer — position + uv in one buffer (r150+ supports InterleavedBuffer)
const vertexData = new Float32Array([
  // x, y, z, u, v
  -1, -1, 0,   0, 0,
   1, -1, 0,   1, 0,
   1,  1, 0,   1, 1,
  -1,  1, 0,   0, 1,
]);

const interleavedBuffer = new THREE.InterleavedBuffer(vertexData, 5); // stride = 5 floats
const geometry = new THREE.BufferGeometry();
geometry.setAttribute('position', new THREE.InterleavedBufferAttribute(interleavedBuffer, 3, 0));
geometry.setAttribute('uv',       new THREE.InterleavedBufferAttribute(interleavedBuffer, 2, 3));
geometry.setIndex([0, 1, 2,  0, 2, 3]); // two triangles
```

---

## Draw Call Batching

A draw call is issued per unique material per object. Reducing draw calls is the highest-leverage optimization.

| Strategy | Draw Calls Saved | Tradeoff |
|----------|-----------------|----------|
| `InstancedMesh` (N same-geometry objects) | N → 1 | All instances same geometry+material |
| `BufferGeometryUtils.mergeGeometries()` | N → 1 | No individual transforms after merge |
| Texture atlas (pack multiple textures) | Avoids material splits | Atlas creation cost, UV remapping |
| `renderer.info.render.calls` | (monitoring) | Use to measure actual draw calls |

```javascript
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// Merge static scene geometry into one draw call
const geometries = staticMeshes.map(m => {
  m.geometry.applyMatrix4(m.matrixWorld); // bake transforms
  return m.geometry;
});
const merged = mergeGeometries(geometries, true); // true = preserve groups for multi-material
const mergedMesh = new THREE.Mesh(merged, materials);
scene.add(mergedMesh);

// Monitor draw calls (dev only)
console.log('Draw calls:', renderer.info.render.calls);
```

---

## LOD (Level of Detail)

```javascript
const lod = new THREE.LOD();

// High detail: 0-10 units from camera
const highGeom = new THREE.SphereGeometry(1, 64, 64);
lod.addLevel(new THREE.Mesh(highGeom, material), 0);

// Medium: 10-50 units
const medGeom = new THREE.SphereGeometry(1, 16, 16);
lod.addLevel(new THREE.Mesh(medGeom, material), 10);

// Low: 50-100 units
const lowGeom = new THREE.SphereGeometry(1, 4, 4);
lod.addLevel(new THREE.Mesh(lowGeom, material), 50);

// Nothing past 100
lod.addLevel(new THREE.Object3D(), 100); // invisible placeholder

scene.add(lod);

// LOD.update() called automatically if autoUpdate is true (r155+)
// For manual control: lod.update(camera) in animation loop
```

---

## Frustum Culling

Three.js enables frustum culling automatically (`object.frustumCulled = true` by default). For large scenes, verify nothing disables it accidentally.

```javascript
// Check frustum culling is enabled (it should be)
console.log(mesh.frustumCulled); // should be true

// Custom culling — manually skip rendering based on distance
renderer.setAnimationLoop(() => {
  const frustum = new THREE.Frustum();
  frustum.setFromProjectionMatrix(
    new THREE.Matrix4().multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
  );

  objects.forEach(obj => {
    obj.visible = frustum.containsPoint(obj.position);
  });

  renderer.render(scene, camera);
});
```

---

## Texture Atlasing and Compression

### KTX2 / Basis Texture Loading (r150+)

KTX2 textures are GPU-native compressed formats. They reduce GPU memory by 4-8x vs PNG/JPEG and eliminate the CPU decode step.

```javascript
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const ktx2Loader = new KTX2Loader()
  .setTranscoderPath('https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/libs/basis/')
  .detectSupport(renderer);

// Load compressed texture
const texture = await ktx2Loader.loadAsync('texture.ktx2');
material.map = texture;

// Convert PNGs to KTX2 via CLI (toktx from KTX-Software):
// toktx --t2 --bcmp output.ktx2 input.png
```

### Texture Atlas Pattern

```javascript
// Single atlas texture, UV offsets per sprite
const atlasTexture = new THREE.TextureLoader().load('/atlas.png');

// Define UV regions (normalized 0-1)
const spriteUVs = {
  player: { x: 0, y: 0, w: 0.25, h: 0.5 },
  enemy:  { x: 0.25, y: 0, w: 0.25, h: 0.5 },
};

function applyAtlasRegion(geometry, region) {
  const uvs = geometry.attributes.uv.array;
  for (let i = 0; i < uvs.length; i += 2) {
    uvs[i]     = region.x + uvs[i] * region.w;
    uvs[i + 1] = region.y + uvs[i + 1] * region.h;
  }
  geometry.attributes.uv.needsUpdate = true;
}
```

---

## Dispose Patterns (Prevent Memory Leaks)

Three.js requires explicit disposal of GPU resources. Forgetting to dispose causes memory growth until tab crash.

```javascript
// Dispose a mesh and all its resources
function disposeMesh(mesh) {
  mesh.geometry.dispose();

  // Material can be shared — only dispose if not reused
  if (Array.isArray(mesh.material)) {
    mesh.material.forEach(m => disposeMaterial(m));
  } else {
    disposeMaterial(mesh.material);
  }

  scene.remove(mesh);
}

function disposeMaterial(material) {
  // Dispose all texture maps on the material
  for (const key of Object.keys(material)) {
    if (material[key] instanceof THREE.Texture) {
      material[key].dispose();
    }
  }
  material.dispose();
}

// Dispose EffectComposer when unmounting
composer.dispose();
renderer.dispose();
```

---

## Pattern Catalog

### Create Geometry Once, Transform in the Loop

**Detection**:
```bash
grep -rn "new THREE\.\(Box\|Sphere\|Plane\|Cylinder\)Geometry" --include="*.js" --include="*.ts"
rg "setAnimationLoop|useFrame" --type js -A 20 | grep "new THREE\."
```

**Signal**:
```javascript
renderer.setAnimationLoop((time) => {
  // BAD: allocates new geometry every frame at 60fps
  const geo = new THREE.SphereGeometry(Math.sin(time * 0.001), 32, 32);
  mesh.geometry = geo;
  renderer.render(scene, camera);
});
```

**Why this matters**: Each new geometry allocates a GPU buffer. Old geometries are not freed without `dispose()`. At 60fps this creates 3,600 leaked GPU buffers per minute.

**Preferred action**:
```javascript
// Morph the existing geometry's buffer in place
const geo = new THREE.SphereGeometry(1, 32, 32);
const mesh = new THREE.Mesh(geo, material);
scene.add(mesh);

renderer.setAnimationLoop((time) => {
  mesh.scale.setScalar(Math.sin(time * 0.001) * 0.5 + 1.0); // transform, don't rebuild
  renderer.render(scene, camera);
});
```

---

### Allocate Scratch Objects Outside the Render Loop

**Detection**:
```bash
grep -rn "new THREE\.Vector3\|new THREE\.Color\|new THREE\.Matrix4" --include="*.js" --include="*.ts"
rg "setAnimationLoop|useFrame" --type js -A 30 | grep "new THREE\."
```

**Signal**:
```javascript
renderer.setAnimationLoop(() => {
  // BAD: 3 allocations per frame = 10,800 objects/min of GC pressure
  const pos = new THREE.Vector3(mesh.position);
  const dir = new THREE.Vector3(0, 1, 0);
  const target = new THREE.Vector3().addVectors(pos, dir);
});
```

**Why this matters**: JavaScript GC pauses correlate directly with allocation rate. At 60fps, even small allocation storms cause visible frame stutters every few seconds.

**Preferred action**:
```javascript
// Allocate once outside the loop, reuse as scratch
const _pos = new THREE.Vector3();
const _dir = new THREE.Vector3(0, 1, 0);
const _target = new THREE.Vector3();

renderer.setAnimationLoop(() => {
  _pos.copy(mesh.position);
  _target.addVectors(_pos, _dir);
});
```

---

### Use composer.render() When EffectComposer Is Active

**Detection**:
```bash
grep -rn "renderer\.render\|composer\.render" --include="*.js" --include="*.ts"
```

**Signal**:
```javascript
const composer = new EffectComposer(renderer);
// ...

renderer.setAnimationLoop(() => {
  renderer.render(scene, camera); // BAD when composer is active — skips postprocessing
});
```

**Why this matters**: `renderer.render()` writes directly to the canvas, bypassing the composer's pass chain. Postprocessing effects are invisible.

**Preferred action**: Replace `renderer.render(scene, camera)` with `composer.render()` once EffectComposer is set up.

---

## Detection Commands Reference

```bash
# Find geometry creation inside animation loops
grep -rn "new THREE\." --include="*.js" --include="*.ts" | grep -v "//\|const \|let \|var "

# Check if dispose() is called for materials
grep -rn "\.dispose()" --include="*.js" --include="*.ts"

# Monitor draw calls at runtime (add to dev mode)
grep -rn "renderer.info.render.calls" --include="*.js" --include="*.ts"

# Find InstancedMesh usage
grep -rn "InstancedMesh\|instanceMatrix" --include="*.js" --include="*.ts"
```

---

## See Also

- `references/visual-polish.md` — Material recipes and HDR environments
- `references/shader-patterns.md` — Custom GLSL shader patterns
- `references/advanced-topics.md` — GLTF loading, TypeScript patterns
