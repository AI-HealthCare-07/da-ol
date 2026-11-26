import * as THREE from "three";

// 홈 회전 약통 3D 장면 (시안 v16을 옮긴 것).
// 화면에 그리는 일만 합니다. 어떤 칸을 먹었는지, 지금 어느 칸인지는 React(HomePage)가 정해서 알려 줍니다.
//
// 구조: 뚜껑(고정, 앞쪽 창 하나, 가운데 흙) + 몸통(돌아감, 회차 칸 n개 + 다 먹은 날용 빈 판 1개)

export interface PillBoxState {
  slotDone: boolean[]; // 칸마다 다 먹었는지
  current: number; // 창 아래 칸. slotDone.length 이면 빈 판
  rotate: "advance" | "nearest"; // advance = 다음 칸으로 한 방향 회전, nearest = 가까운 쪽으로
}

export interface PillBoxScene {
  setState: (s: PillBoxState) => void;
  onPress: (cb: () => void) => void;
  dispose: () => void;
}

// ---- 치수 ----
const R = 2.2;
const RIB = 0.16;
const R_HUB = 0.98;
const R_CELL = R - 0.02;
const WALL = 0.08;
const FLOOR_H = 0.14, BASE_H = 0.6, LID_H = 0.2, GAP = 0.03;
const FRONT = -Math.PI / 2;

const clay = (color: number) => new THREE.MeshStandardMaterial({ color, roughness: 1, metalness: 0 });

export function createPillBoxScene(container: HTMLElement, slotCount: number): PillBoxScene {
  const N = slotCount + 1;
  const DONE_INDEX = slotCount;
  const S = (Math.PI * 2) / N;
  const PETALS = N * Math.max(1, Math.round(11 / N)); // 칸 수의 배수 → 멈추면 뚜껑·몸통 꽃잎이 딱 맞음
  const centerOf = (k: number) => FRONT + k * S;
  const toXZ = (a: number, r: number): [number, number] => [Math.cos(a) * r, -Math.sin(a) * r];

  const disposables: { dispose: () => void }[] = [];
  const track = <T extends { dispose: () => void }>(x: T) => (disposables.push(x), x);
  const mat = (c: number) => track(clay(c));

  // ---- 장면 ----
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.VSMShadowMap;
  renderer.domElement.style.display = "block";
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.touchAction = "manipulation";
  renderer.domElement.style.cursor = "pointer";
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
  camera.position.set(0, 7.8, 6.8);
  camera.lookAt(0, 0.7, 0.25);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xf3e3c6, 1.7));
  const sun = new THREE.DirectionalLight(0xfff6e8, 1.25);
  sun.position.set(-3, 8, 4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -4, right: 4, top: 4, bottom: -4 });
  sun.shadow.bias = -0.0005;
  sun.shadow.radius = 8;
  sun.shadow.blurSamples = 16;
  scene.add(sun);
  const ground = new THREE.Mesh(track(new THREE.CircleGeometry(7, 48)), track(new THREE.ShadowMaterial({ opacity: 0.12 })));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // ---- 도형 도우미 ----
  function petalShape(r: number) {
    const s = new THREE.Shape();
    const steps = PETALS * 8;
    for (let i = 0; i <= steps; i++) {
      const a = (i / steps) * Math.PI * 2;
      const rr = r + RIB * Math.sqrt(Math.abs(Math.cos((PETALS * a) / 2)));
      const x = Math.cos(a) * rr, y = Math.sin(a) * rr;
      if (i === 0) s.moveTo(x, y);
      else s.lineTo(x, y);
    }
    return s;
  }
  function cellPoints(center: number, rIn = R_HUB, rOut = R_CELL, wall = WALL) {
    const pts: THREE.Vector2[] = [];
    const a0 = center - S / 2, a1 = center + S / 2;
    const dOut = wall / 2 / rOut, dIn = wall / 2 / rIn;
    for (let i = 0; i <= 24; i++) {
      const a = a0 + dOut + ((a1 - dOut - (a0 + dOut)) * i) / 24;
      pts.push(new THREE.Vector2(Math.cos(a) * rOut, Math.sin(a) * rOut));
    }
    for (let i = 0; i <= 8; i++) {
      const a = a1 - dIn - ((a1 - dIn - (a0 + dIn)) * i) / 8;
      pts.push(new THREE.Vector2(Math.cos(a) * rIn, Math.sin(a) * rIn));
    }
    return pts;
  }
  const circlePath = (r: number) => new THREE.Path().absarc(0, 0, r, 0, Math.PI * 2, true);
  function extrude(shape: THREE.Shape, depth: number, bevel = 0.02, size = bevel) {
    const g = new THREE.ExtrudeGeometry(shape, {
      depth, bevelEnabled: bevel > 0, bevelThickness: bevel, bevelSize: size, bevelSegments: 6, curveSegments: 24,
    });
    g.rotateX(-Math.PI / 2);
    return track(g);
  }

  const shell = mat(0xf0dcbb);
  const lidMat = mat(0xfdf4e3);
  const inside = mat(0xefdcbc);

  // ---- 몸통 (돌아감) ----
  const base = new THREE.Group();
  scene.add(base);
  const floor = new THREE.Mesh(extrude(petalShape(R), FLOOR_H), shell);
  floor.castShadow = floor.receiveShadow = true;
  const floorTop = new THREE.Mesh(extrude(new THREE.Shape(circlePath(R - 0.1).getPoints(96)), 0.005, 0), inside);
  floorTop.position.y = FLOOR_H + 0.01;
  floorTop.receiveShadow = true;
  const wallShape = petalShape(R);
  for (let k = 0; k < N; k++) wallShape.holes.push(new THREE.Path(cellPoints(centerOf(k))));
  wallShape.holes.push(circlePath(R_HUB - 0.07));
  const walls = new THREE.Mesh(extrude(wallShape, BASE_H - FLOOR_H), shell);
  walls.position.y = FLOOR_H;
  walls.castShadow = walls.receiveShadow = true;
  const plate = new THREE.Mesh(
    extrude(new THREE.Shape(cellPoints(centerOf(DONE_INDEX), R_HUB + 0.02, R_CELL - 0.02, WALL + 0.04)), BASE_H - FLOOR_H - 0.12),
    shell,
  ); // 다 먹은 날 창을 막는 빈 판
  plate.position.y = FLOOR_H;
  plate.castShadow = plate.receiveShadow = true;
  base.add(floor, floorTop, walls, plate);

  // 칸마다 캡슐 하나 (웜그린·웜옐로우)
  const capGeo = track(new THREE.CapsuleGeometry(0.17, 0.3, 8, 20));
  const green = mat(0x8dbb78), yellow = mat(0xf4c24d);
  const pills = Array.from({ length: slotCount }, (_, k) => {
    const a = centerOf(k);
    const [x, z] = toXZ(a, (R_HUB + R_CELL) / 2 - 0.2);
    const m = new THREE.Group();
    const h1 = new THREE.Mesh(capGeo, green); h1.scale.set(1, 0.5, 1); h1.position.y = -0.1;
    const h2 = new THREE.Mesh(capGeo, yellow); h2.scale.set(1, 0.5, 1); h2.position.y = 0.1;
    m.add(h1, h2);
    m.rotation.set(Math.PI / 2, 0, -a + 0.55);
    m.traverse((o) => (o.castShadow = true));
    const holder = new THREE.Group();
    holder.position.set(x, FLOOR_H + 0.19, z);
    holder.add(m);
    base.add(holder);
    return holder;
  });

  // ---- 뚜껑 (고정) ----
  const lidShape = petalShape(R);
  lidShape.holes.push(new THREE.Path(cellPoints(FRONT, R_HUB + 0.01, R_CELL - 0.03, WALL + 0.02)));
  lidShape.holes.push(circlePath(R_HUB - 0.07));
  const lid = new THREE.Mesh(extrude(lidShape, LID_H, 0.06, 0.02), lidMat);
  lid.position.y = BASE_H + GAP;
  lid.castShadow = lid.receiveShadow = true;
  scene.add(lid);

  // ---- 가운데 흙 + 새싹·꽃 (고정) ----
  const SOIL_Y = FLOOR_H + 0.42;
  const soil = new THREE.Mesh(track(new THREE.CylinderGeometry(R_HUB - 0.08, R_HUB - 0.08, 0.06, 48)), mat(0x9c7354));
  soil.position.y = SOIL_Y;
  soil.receiveShadow = true;
  scene.add(soil);
  const lumpGeo = track(new THREE.SphereGeometry(1, 10, 8));
  const lumpA = mat(0x8a6447), lumpB = mat(0xad8463);
  for (let i = 0; i < 22; i++) {
    const a = Math.random() * Math.PI * 2, r = Math.random() * (R_HUB - 0.2);
    const [x, z] = toXZ(a, r);
    const lump = new THREE.Mesh(lumpGeo, i % 3 ? lumpA : lumpB);
    const size = 0.035 + Math.random() * 0.035;
    lump.scale.set(size, size * 0.6, size);
    lump.position.set(x, SOIL_Y + 0.035, z);
    scene.add(lump);
  }

  const plant = new THREE.Group();
  plant.position.set(0, SOIL_Y + 0.01, 0);
  plant.scale.setScalar(2.2);
  scene.add(plant);
  const leafGeo = track(new THREE.SphereGeometry(1, 20, 12));
  const leafMat = mat(0x8cc474);
  const sprout = new THREE.Group();
  const stem = new THREE.Mesh(track(new THREE.CylinderGeometry(0.04, 0.05, 0.38, 12)), leafMat);
  stem.position.y = 0.19;
  const leafL = new THREE.Mesh(leafGeo, leafMat);
  leafL.scale.set(0.19, 0.07, 0.12); leafL.position.set(-0.14, 0.34, 0); leafL.rotation.z = 0.45;
  const leafR = leafL.clone(); leafR.position.x = 0.14; leafR.rotation.z = -0.45;
  sprout.add(stem, leafL, leafR);
  sprout.traverse((o) => (o.castShadow = true));
  plant.add(sprout);
  const flower = new THREE.Group();
  flower.position.y = 0.42;
  flower.add(new THREE.Mesh(track(new THREE.SphereGeometry(0.08, 20, 14)), mat(0xffd36e)));
  const petalMat = mat(0xf9b4c4);
  for (let i = 0; i < 6; i++) {
    const p = new THREE.Mesh(leafGeo, petalMat);
    const a = (i / 6) * Math.PI * 2;
    p.scale.set(0.12, 0.06, 0.08);
    p.position.set(Math.cos(a) * 0.14, 0, Math.sin(a) * 0.14);
    p.rotation.y = -a;
    flower.add(p);
  }
  flower.rotation.x = 0.55;
  flower.scale.setScalar(0.001);
  plant.add(flower);

  // ---- 상태 ----
  let state: PillBoxState = { slotDone: Array(slotCount).fill(false), current: 0, rotate: "nearest" };
  let shown = 0; // 지금 창 아래에 있는 칸
  let rotTarget = 0;
  let first = true;

  function setState(next: PillBoxState) {
    if (first) {
      rotTarget = -next.current * S;
      base.rotation.y = rotTarget;
      first = false;
    } else if (next.current !== shown) {
      if (next.rotate === "advance") {
        const steps = (next.current - shown + N) % N || N;
        rotTarget -= steps * S;
      } else {
        let t = -next.current * S;
        while (t - base.rotation.y > Math.PI) t -= Math.PI * 2;
        while (t - base.rotation.y < -Math.PI) t += Math.PI * 2;
        rotTarget = t;
      }
    }
    shown = next.current;
    state = next;
  }

  let pressCb: () => void = () => {};
  const onClick = () => pressCb();
  renderer.domElement.addEventListener("click", onClick);

  // ---- 크기 ----
  const resize = () => {
    const w = container.clientWidth;
    const h = Math.round(w * 0.9);
    renderer.setSize(w, h, false);
    renderer.domElement.style.height = `${h}px`;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();

  // ---- 그리기 (화면에 안 보이면 멈춤) ----
  let raf = 0;
  const t0 = performance.now();
  const tick = () => {
    const t = (performance.now() - t0) / 1000;
    const allDone = state.slotDone.every(Boolean);
    base.rotation.y += (rotTarget - base.rotation.y) * 0.08;
    pills.forEach((h, k) => {
      const target = state.slotDone[k] ? 0.001 : 1;
      const s = h.scale.x + (target - h.scale.x) * 0.18;
      h.scale.setScalar(s);
      h.position.y = FLOOR_H + 0.19 + (1 - s) * 0.4; // 사라질 때 살짝 떠오름
    });
    const fs = flower.scale.x + ((allDone ? 0.95 : 0.001) - flower.scale.x) * 0.1;
    flower.scale.setScalar(fs);
    flower.rotation.y = t * 0.4;
    sprout.rotation.z = Math.sin(t * 1.5) * 0.04;
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);

  return {
    setState,
    onPress: (cb) => {
      pressCb = cb;
    },
    dispose: () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.domElement.removeEventListener("click", onClick);
      disposables.forEach((d) => d.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}
