import * as THREE from 'three';

const PALETTES = {
  dark: {
    background: 0x0e1729, ground: 0x09101f, base: 0x16233d,
    raised: 0x22355a, panel: 0x0b1324, ink: 0xf7f5f2,
    muted: 0x8f98aa, accent: 0xf5b335, accentSoft: 0xa16207,
    glass: 0x8ea0bd,
  },
  light: {
    background: 0xf7f5f2, ground: 0xeee9e1, base: 0xffffff,
    raised: 0xe5dfd5, panel: 0x16233d, ink: 0x0e1729,
    muted: 0x5c6470, accent: 0xa16207, accentSoft: 0xf5b335,
    glass: 0xd8cdbd,
  },
};

const SURFACES = [
  { position: [-2.72, 0.08, -1.52], kind: 'portal' },
  { position: [2.72, 0.08, -1.52], kind: 'register' },
  { position: [-2.72, 0.08, 1.52], kind: 'cms' },
  { position: [2.72, 0.08, 1.52], kind: 'admin' },
];

function standardMaterial(color, opacity = 1, options = {}) {
  return new THREE.MeshStandardMaterial({
    color,
    transparent: opacity < 1,
    opacity,
    roughness: options.roughness ?? 0.66,
    metalness: options.metalness ?? 0.22,
    emissive: options.emissive ?? 0x000000,
    emissiveIntensity: options.emissiveIntensity ?? 0,
  });
}

function basicMaterial(color, opacity = 1) {
  return new THREE.MeshBasicMaterial({ color, transparent: opacity < 1, opacity });
}

function createPath(start, end, palette) {
  const midpoint = new THREE.Vector3(
    (start[0] + end[0]) * 0.39,
    0.07,
    (start[2] + end[2]) * 0.39,
  );
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(...start), midpoint, new THREE.Vector3(...end),
  );
  return new THREE.Mesh(
    new THREE.TubeGeometry(curve, 32, 0.018, 8, false),
    standardMaterial(palette.accent, 0.62, {
      emissive: palette.accent, emissiveIntensity: 0.72, roughness: 0.32,
    }),
  );
}

function createGlassRoom(group, palette) {
  const glass = () => new THREE.MeshPhysicalMaterial({
    color: palette.glass,
    transparent: true,
    opacity: 0.13,
    transmission: 0.34,
    thickness: 0.22,
    roughness: 0.18,
    metalness: 0.02,
    side: THREE.DoubleSide,
    depthWrite: false,
  });
  const back = new THREE.Mesh(new THREE.PlaneGeometry(2.24, 1.48), glass());
  back.position.set(0, 0.76, -0.76);
  group.add(back);
  const left = new THREE.Mesh(new THREE.PlaneGeometry(1.52, 1.48), glass());
  left.rotation.y = Math.PI / 2;
  left.position.set(-1.12, 0.76, 0);
  group.add(left);
  const right = new THREE.Mesh(new THREE.PlaneGeometry(1.52, 1.48), glass());
  right.rotation.y = Math.PI / 2;
  right.position.set(1.12, 0.76, 0);
  group.add(right);
}

function createFrame(group, palette) {
  const geometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(2.24, 1.48, 1.52));
  const frameMaterial = new THREE.LineBasicMaterial({
    color: palette.accent, transparent: true, opacity: 0.62,
  });
  const frame = new THREE.LineSegments(geometry, frameMaterial);
  frame.position.y = 0.74;
  group.add(frame);
  return frameMaterial;
}

function addPanel(group, palette) {
  const panel = new THREE.Mesh(
    new THREE.BoxGeometry(1.72, 0.94, 0.055),
    standardMaterial(palette.panel, 0.96, { roughness: 0.48, metalness: 0.28 }),
  );
  panel.position.set(0, 0.8, 0.7);
  group.add(panel);
}

function addLine(group, x, y, width, palette, opacity = 0.32) {
  const line = new THREE.Mesh(
    new THREE.PlaneGeometry(width, 0.025), basicMaterial(palette.ink, opacity),
  );
  line.position.set(x, y, 0.733);
  group.add(line);
}

function loadArtwork(url, onReady) {
  if (!url) return;
  new THREE.TextureLoader().load(url, (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 4;
    onReady(texture);
  }, undefined, () => {});
}

function addArtworkTile(group, x, y, width, height, url, palette) {
  const frame = new THREE.Mesh(
    new THREE.BoxGeometry(width + 0.08, height + 0.08, 0.04),
    standardMaterial(palette.accentSoft, 1, { roughness: 0.46, metalness: 0.48 }),
  );
  frame.position.set(x, y, 0.74);
  group.add(frame);
  const artMaterial = basicMaterial(palette.raised, 1);
  const art = new THREE.Mesh(new THREE.PlaneGeometry(width, height), artMaterial);
  art.position.set(x, y, 0.765);
  group.add(art);
  loadArtwork(url, (texture) => {
    artMaterial.map = texture;
    artMaterial.color.setHex(0xffffff);
    artMaterial.needsUpdate = true;
  });
}

function addPortalInterface(group, palette, artwork) {
  const positions = [
    [-0.52, 0.98], [0, 0.98], [0.52, 0.98],
    [-0.52, 0.57], [0, 0.57], [0.52, 0.57],
  ];
  positions.forEach(([x, y], index) => {
    const tile = new THREE.Mesh(
      new THREE.PlaneGeometry(0.4, 0.28),
      standardMaterial(index === 0 ? palette.accentSoft : palette.raised, 1, { roughness: 0.7 }),
    );
    tile.position.set(x, y, 0.735);
    group.add(tile);
  });
  addArtworkTile(group, -0.52, 0.98, 0.34, 0.22, artwork, palette);
}

function addRegisterInterface(group, palette) {
  addLine(group, -0.32, 1.07, 0.76, palette, 0.82);
  for (let index = 0; index < 4; index += 1) {
    const field = new THREE.Mesh(
      new THREE.PlaneGeometry(1.18, 0.12), basicMaterial(palette.raised, 0.82),
    );
    field.position.set(-0.04, 0.86 - index * 0.18, 0.735);
    group.add(field);
    const dot = new THREE.Mesh(
      new THREE.CircleGeometry(0.035, 16),
      basicMaterial(index === 0 ? palette.accent : palette.muted, 0.88),
    );
    dot.position.set(-0.7, 0.86 - index * 0.18, 0.738);
    group.add(dot);
  }
}

function addCmsInterface(group, palette, artwork) {
  const sidebar = new THREE.Mesh(
    new THREE.PlaneGeometry(0.28, 0.72), basicMaterial(palette.raised, 0.8),
  );
  sidebar.position.set(-0.67, 0.78, 0.735);
  group.add(sidebar);
  for (let index = 0; index < 4; index += 1) {
    const avatar = new THREE.Mesh(
      new THREE.CircleGeometry(0.055, 18),
      basicMaterial(index === 1 ? palette.accent : palette.muted, 0.82),
    );
    avatar.position.set(-0.35, 1.02 - index * 0.18, 0.738);
    group.add(avatar);
    addLine(group, 0.2, 1.02 - index * 0.18, index % 2 ? 0.72 : 0.9, palette, 0.34);
  }
  addArtworkTile(group, 0.62, 0.53, 0.28, 0.24, artwork, palette);
}

function addAdminInterface(group, palette, artwork) {
  addArtworkTile(group, -0.42, 0.82, 0.64, 0.58, artwork, palette);
  [palette.accent, palette.accentSoft, palette.ink, palette.muted].forEach((color, index) => {
    const swatch = new THREE.Mesh(new THREE.CircleGeometry(0.09, 20), basicMaterial(color, 0.94));
    swatch.position.set(0.18 + index * 0.22, 1.02, 0.738);
    group.add(swatch);
  });
  addLine(group, 0.49, 0.76, 0.72, palette, 0.42);
  addLine(group, 0.42, 0.59, 0.58, palette, 0.28);
}

function addFurniture(group, palette) {
  const desk = new THREE.Mesh(
    new THREE.BoxGeometry(1.05, 0.08, 0.46),
    standardMaterial(palette.accentSoft, 1, { roughness: 0.5, metalness: 0.34 }),
  );
  desk.position.set(0, 0.18, 0.12);
  group.add(desk);
  [-0.42, 0.42].forEach((x) => {
    const leg = new THREE.Mesh(
      new THREE.BoxGeometry(0.055, 0.34, 0.055),
      standardMaterial(palette.ink, 0.78, { roughness: 0.45, metalness: 0.5 }),
    );
    leg.position.set(x, 0, 0.12);
    group.add(leg);
  });
}

function createSurface(surface, index, palette, artworks) {
  const group = new THREE.Group();
  group.position.set(...surface.position);
  const floorMaterial = standardMaterial(index % 2 ? palette.base : palette.raised, 0.93, {
    roughness: 0.56, metalness: 0.16,
  });
  const floor = new THREE.Mesh(new THREE.BoxGeometry(2.3, 0.13, 1.62), floorMaterial);
  floor.position.y = -0.065;
  floor.receiveShadow = true;
  group.add(floor);
  createGlassRoom(group, palette);
  const frameMaterial = createFrame(group, palette);
  addPanel(group, palette);
  addFurniture(group, palette);
  if (surface.kind === 'portal') addPortalInterface(group, palette, artworks[0]);
  if (surface.kind === 'register') addRegisterInterface(group, palette);
  if (surface.kind === 'cms') addCmsInterface(group, palette, artworks[1]);
  if (surface.kind === 'admin') addAdminInterface(group, palette, artworks[0]);
  const beaconMaterial = standardMaterial(palette.accent, 1, {
    emissive: palette.accent, emissiveIntensity: 0.85, roughness: 0.3,
  });
  const beacon = new THREE.Mesh(new THREE.SphereGeometry(0.07, 20, 12), beaconMaterial);
  beacon.position.set(0.86, 1.23, 0.43);
  group.add(beacon);
  const roomLight = new THREE.PointLight(palette.accent, index === 0 ? 1.6 : 1.15, 3.2, 2);
  roomLight.position.set(0, 1.15, 0.36);
  group.add(roomLight);
  group.userData = { baseY: surface.position[1], floorMaterial, frameMaterial, beaconMaterial, roomLight };
  return group;
}

function createCentralStudio(scene, palette) {
  const hub = new THREE.Group();
  const hubBase = new THREE.Mesh(
    new THREE.CylinderGeometry(1.14, 1.14, 0.18, 64),
    standardMaterial(palette.base, 0.98, { roughness: 0.5, metalness: 0.22 }),
  );
  hubBase.receiveShadow = true;
  hub.add(hubBase);
  [1.34, 1.66].forEach((radius, index) => {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, index ? 0.012 : 0.024, 10, 128),
      standardMaterial(palette.accent, index ? 0.46 : 0.88, {
        emissive: palette.accent, emissiveIntensity: index ? 0.45 : 1, roughness: 0.3,
      }),
    );
    ring.rotation.x = Math.PI / 2;
    ring.position.y = 0.06;
    hub.add(ring);
  });
  const glass = new THREE.Mesh(
    new THREE.CylinderGeometry(1.04, 1.04, 1.3, 64, 1, true),
    new THREE.MeshPhysicalMaterial({
      color: palette.glass, transparent: true, opacity: 0.15, transmission: 0.44,
      thickness: 0.3, roughness: 0.12, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  glass.position.y = 0.65;
  hub.add(glass);
  const desk = new THREE.Mesh(
    new THREE.BoxGeometry(1.02, 0.09, 0.52),
    standardMaterial(palette.accentSoft, 1, { roughness: 0.5, metalness: 0.38 }),
  );
  desk.position.set(0, 0.4, 0.04);
  desk.castShadow = true;
  hub.add(desk);
  [-0.42, 0.42].forEach((x) => {
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.45, 0.06), standardMaterial(palette.ink, 0.85));
    leg.position.set(x, 0.18, 0.04);
    hub.add(leg);
  });
  [-0.7, 0.7].forEach((x) => {
    const shelf = new THREE.Mesh(
      new THREE.BoxGeometry(0.3, 0.72, 0.22), standardMaterial(palette.panel, 0.94, { roughness: 0.58 }),
    );
    shelf.position.set(x, 0.44, -0.34);
    hub.add(shelf);
  });
  const spark = new THREE.Mesh(
    new THREE.OctahedronGeometry(0.14, 0),
    standardMaterial(palette.ink, 1, {
      emissive: palette.accent, emissiveIntensity: 0.92, roughness: 0.25,
    }),
  );
  spark.position.set(0.3, 0.64, 0.02);
  hub.add(spark);
  scene.add(hub);
  return { hub, spark };
}

function disposeObject(object) {
  object.traverse((node) => {
    if (node.geometry) node.geometry.dispose();
    if (node.material) {
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.forEach((entry) => {
        if (entry.map) entry.map.dispose();
        entry.dispose();
      });
    }
  });
}

export function initLivingSystem({ canvas, stage, theme = 'dark', assets = [], onFallback }) {
  const palette = PALETTES[theme] || PALETTES.dark;
  const renderer = new THREE.WebGLRenderer({
    canvas, alpha: true, antialias: true,
    powerPreference: 'high-performance', failIfMajorPerformanceCaveat: true,
  });
  renderer.setClearColor(palette.background, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = theme === 'light' ? 1.02 : 1.14;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 60);
  camera.position.set(0, 5.7, 9.1);
  camera.lookAt(0, 0.42, 0);
  scene.add(new THREE.HemisphereLight(theme === 'light' ? 0xffffff : palette.ink, palette.background, theme === 'light' ? 2.4 : 1.85));
  const keyLight = new THREE.DirectionalLight(theme === 'light' ? 0xffffff : palette.ink, theme === 'light' ? 2.6 : 2.1);
  keyLight.position.set(-3.5, 7, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  scene.add(keyLight);
  const warmLight = new THREE.PointLight(palette.accent, theme === 'light' ? 5 : 17, 13, 2);
  warmLight.position.set(0, 3.6, 2.4);
  scene.add(warmLight);
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(13, 10), standardMaterial(palette.ground, 0.72, { roughness: 0.86, metalness: 0.04 }),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.15;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(12, 24, palette.accent, palette.muted);
  grid.position.y = -0.135;
  grid.material.transparent = true;
  grid.material.opacity = theme === 'light' ? 0.17 : 0.25;
  scene.add(grid);

  const central = createCentralStudio(scene, palette);
  const paths = SURFACES.map((surface) => {
    const path = createPath([0, 0.02, 0], [surface.position[0], 0.02, surface.position[2]], palette);
    scene.add(path);
    return path;
  });
  const surfaces = SURFACES.map((surface, index) => {
    const group = createSurface(surface, index, palette, assets);
    scene.add(group);
    return group;
  });

  let active = 0;
  let motionDisabled = false;
  let visible = true;
  let disposed = false;
  const startedAt = performance.now();
  const resize = () => {
    if (disposed) return;
    const width = Math.max(1, stage.clientWidth);
    const height = Math.max(1, stage.clientHeight);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(ratio);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  const render = (timestamp = performance.now()) => {
    if (disposed || !visible) return;
    const elapsed = (timestamp - startedAt) / 1000;
    surfaces.forEach((group, index) => {
      const selected = index === active;
      const targetScale = selected ? 1.075 : 0.94;
      const nextScale = group.scale.x + (targetScale - group.scale.x) * 0.07;
      group.scale.setScalar(nextScale);
      const lift = selected ? 0.2 : 0;
      const drift = motionDisabled ? 0 : Math.sin(elapsed * 0.62 + index * 1.7) * 0.022;
      group.position.y += (group.userData.baseY + lift + drift - group.position.y) * 0.075;
      group.userData.frameMaterial.opacity += ((selected ? 0.98 : 0.43) - group.userData.frameMaterial.opacity) * 0.08;
      group.userData.floorMaterial.opacity += ((selected ? 1 : 0.76) - group.userData.floorMaterial.opacity) * 0.08;
      group.userData.beaconMaterial.emissiveIntensity += ((selected ? 2.8 : 0.7) - group.userData.beaconMaterial.emissiveIntensity) * 0.08;
      group.userData.roomLight.intensity += ((selected ? 2.4 : 0.9) - group.userData.roomLight.intensity) * 0.08;
      paths[index].material.opacity += ((selected ? 1 : 0.32) - paths[index].material.opacity) * 0.08;
    });
    if (!motionDisabled) {
      central.hub.rotation.y = Math.sin(elapsed * 0.18) * 0.025;
      central.spark.rotation.y = elapsed * 0.34;
      central.spark.rotation.x = elapsed * 0.2;
    }
    renderer.render(scene, camera);
  };
  const syncLoop = () => renderer.setAnimationLoop(visible && !disposed ? render : null);
  const resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(stage);
  const visibilityObserver = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting);
    syncLoop();
    if (visible && motionDisabled) render();
  }, { rootMargin: '140px' });
  visibilityObserver.observe(stage);
  const contextLost = (event) => {
    event.preventDefault();
    if (typeof onFallback === 'function') onFallback();
  };
  canvas.addEventListener('webglcontextlost', contextLost, false);
  resize();
  render();
  syncLoop();

  return {
    setActive(index) {
      active = Math.max(0, Math.min(SURFACES.length - 1, Number(index) || 0));
      if (motionDisabled) render();
    },
    setMotionDisabled(disabled) {
      motionDisabled = Boolean(disabled);
      if (motionDisabled) render();
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      resizeObserver.disconnect();
      visibilityObserver.disconnect();
      canvas.removeEventListener('webglcontextlost', contextLost, false);
      renderer.setAnimationLoop(null);
      disposeObject(scene);
      renderer.dispose();
    },
  };
}
