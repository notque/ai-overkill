# Performance Reference — Phaser Gamedev

Object pooling, GC optimization, camera culling, texture atlases, and mobile performance for Phaser 3.60+.

---

To drive frame rate to a stated target rather than apply fixes blind, run the
`hill-climb` skill: it baselines p1-low FPS, profiles, and accepts or reverts one
change at a time. Playbook: `skills/meta/hill-climb/references/domain-playbooks.md`.

---

## Object Pooling

Creating and destroying game objects per-frame is the fastest path to garbage collection pauses and frame drops. The solution is **pooling**: pre-create objects, hide/show them instead of destroy/create.

**Phaser's built-in pool: `physics.add.group` with `maxSize`**

```typescript
// In GameScene.create():

// Bullet pool — pre-allocates up to 20 bullets
this.bullets = this.physics.add.group({
  classType: Phaser.Physics.Arcade.Image,
  maxSize: 20,          // return null from get() when all 20 are active
  runChildUpdate: true, // calls each child's update() each frame
});

// Explosion pool — Image objects (no physics needed)
this.explosions = this.add.group({
  classType: Phaser.GameObjects.Sprite,
  maxSize: 10,
});
```

**Firing a bullet from the pool:**

```typescript
fireBullet(x: number, y: number, velocityX: number): void {
  const bullet = this.bullets.get(x, y, 'bullet') as Phaser.Physics.Arcade.Image | null;
  if (!bullet) return; // pool exhausted — silent drop, never throw

  bullet.setActive(true).setVisible(true);
  bullet.body.reset(x, y);            // reposition the physics body
  bullet.body.setAllowGravity(false);
  bullet.setVelocityX(velocityX);
}
```

**Returning a bullet to the pool:**

```typescript
// In update() — recycle off-screen bullets
this.bullets.getChildren().forEach((child) => {
  const b = child as Phaser.Physics.Arcade.Image;
  if (!b.active) return;

  const offscreen =
    b.x < -50 || b.x > this.scale.width + 50 ||
    b.y < -50 || b.y > this.scale.height + 50;

  if (offscreen) {
    this.bullets.killAndHide(b);
    b.body.reset(0, 0); // move body out of physics world bounds
  }
});

// On collision — return to pool
private bulletHitWall(bullet: Phaser.Types.Physics.Arcade.GameObjectWithBody): void {
  this.bullets.killAndHide(bullet as Phaser.Physics.Arcade.Image);
  (bullet as Phaser.Physics.Arcade.Image).body.reset(0, 0);
}
```

**Enemy pool pattern:**

```typescript
// Pool with a custom class
class EnemyPool {
  private group: Phaser.Physics.Arcade.Group;

  constructor(scene: Phaser.Scene) {
    this.group = scene.physics.add.group({ maxSize: 30, runChildUpdate: true });
  }

  spawn(x: number, y: number): Phaser.Physics.Arcade.Sprite | null {
    const e = this.group.get(x, y, 'enemy') as Phaser.Physics.Arcade.Sprite | null;
    if (!e) return null;
    e.setActive(true).setVisible(true);
    e.body.reset(x, y);
    e.setData('hp', 3);
    e.play('enemy-walk');
    return e;
  }

  kill(enemy: Phaser.Physics.Arcade.Sprite): void {
    this.group.killAndHide(enemy);
    enemy.body.reset(0, 0);
  }
}
```

---

## GC Optimization — Keep `update()` Allocation-Free

Every object created in `update()` becomes garbage. Garbage collection pauses manifest as micro-stutters.

**Patterns to eliminate from `update()`:**

```typescript
// BAD — allocates a new Vector2 every frame (60 allocs/sec)
update(): void {
  const dir = new Phaser.Math.Vector2(this.target.x - this.x, this.target.y - this.y);
  dir.normalize();
}

// GOOD — reuse a pre-allocated vector
private _dir = new Phaser.Math.Vector2();

update(): void {
  this._dir.set(this.target.x - this.x, this.target.y - this.y);
  this._dir.normalize();
}

// BAD — creates new array every frame
update(): void {
  const nearby = this.enemies.getChildren().filter(e => dist(e, player) < 200);
}

// GOOD — pre-allocate array, reuse each frame
private _nearby: Phaser.GameObjects.GameObject[] = [];

update(): void {
  this._nearby.length = 0; // clear without reallocating
  this.enemies.getChildren().forEach(e => {
    if (dist(e as Phaser.GameObjects.Sprite, this.player) < 200) {
      this._nearby.push(e);
    }
  });
}
```

**Rule of thumb**: if you see `new` inside `update()`, pre-allocate in `create()` and reuse.

---

## Camera Culling

Phaser automatically skips rendering objects outside the camera viewport. You still pay the `update()` cost for off-screen objects unless you add distance checks.

```typescript
// Cheap distance check to skip update logic for off-screen enemies
update(): void {
  const cam = this.cameras.main;
  const inView = (obj: Phaser.GameObjects.Sprite) =>
    Math.abs(obj.x - cam.scrollX - cam.width / 2) < cam.width / 2 + 100 &&
    Math.abs(obj.y - cam.scrollY - cam.height / 2) < cam.height / 2 + 100;

  this.enemies.getChildren().forEach((child) => {
    const enemy = child as Phaser.Physics.Arcade.Sprite;
    if (!enemy.active) return;

    if (inView(enemy)) {
      this.updateEnemy(enemy); // full AI update
    } else {
      enemy.body.setVelocity(0, 0); // freeze off-screen enemies
    }
  });
}
```

**Deactivate very distant objects** (large open-world games):

```typescript
const DESPAWN_DIST = 1200; // pixels from player

this.enemies.getChildren().forEach((child) => {
  const enemy = child as Phaser.Physics.Arcade.Sprite;
  const dist = Phaser.Math.Distance.Between(player.x, player.y, enemy.x, enemy.y);
  if (dist > DESPAWN_DIST && enemy.active) {
    this.enemyPool.kill(enemy);
  }
});
```

---

## Texture Atlas vs Individual Images

Individual image load calls:
- N images = N draw calls per frame = significant overhead at 50+ objects
- Each `this.load.image()` creates a separate WebGL texture

Texture atlas:
- 1 atlas = 1 draw call for all objects using that atlas
- TexturePacker, Shoebox, or free.texture-packer.com generate atlases

```typescript
// BEFORE — individual images (bad for performance)
this.load.image('coin', 'assets/coin.png');
this.load.image('gem', 'assets/gem.png');
this.load.image('key', 'assets/key.png');
this.load.image('heart', 'assets/heart.png');

// AFTER — single atlas (1 draw call for all)
this.load.atlas('items', 'assets/items.png', 'assets/items.json');
const coin = this.add.image(x, y, 'items', 'coin.png');
const gem  = this.add.image(x, y, 'items', 'gem.png');
```

**Rule**: if you have more than 5-6 small images used together (UI, collectibles, particles), pack them into an atlas.

---

## Mobile Performance Guidelines

Mobile GPUs are significantly weaker than desktop. Budget accordingly:

| Element | Desktop limit | Mobile limit |
|---------|-------------|--------------|
| Active physics bodies | 500 | 100-150 |
| Particle emitters (active) | 10 | 3-5 |
| Particles per emitter | 200 | 30-50 |
| Tiled layers | 8 | 4 |
| Draw calls per frame | 100+ | 30-50 |

**Responsive resolution** — reduce render resolution on mobile:

```typescript
const isMobile = /Android|iPhone|iPad/.test(navigator.userAgent);

const config: Phaser.Types.Core.GameConfig = {
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
    width: 800,
    height: 600,
  },
  resolution: isMobile ? 1 : window.devicePixelRatio, // skip HiDPI on mobile
};
```

**Particle count reduction on mobile:**

```typescript
const particleCount = isMobile ? 10 : 30;

const emitter = this.add.particles(x, y, 'spark', {
  quantity: particleCount,
  lifespan: 500,
  speed: { min: 50, max: 150 },
  emitting: false,
});
```

**Measure FPS in development:**

```typescript
// In create():
if (process.env.NODE_ENV === 'development') {
  this.fpsText = this.add.text(10, 10, '', {
    fontSize: '12px', color: '#00ff00',
  }).setScrollFactor(0).setDepth(100);
}

// In update():
if (this.fpsText) {
  this.fpsText.setText(`FPS: ${Math.round(this.game.loop.actualFps)}`);
}
```

**Target**: maintain 60 FPS on a mid-range Android device (2020 era). If you drop below 45 FPS: reduce particle counts first, then physics body counts, then layer count.
