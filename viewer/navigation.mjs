// Collision and movement math, independent of WebGL so it can be tested directly.
export function inside(point, polygon) {
  let hit = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const a = polygon[i], b = polygon[j];
    if ((a[1] > point.z) !== (b[1] > point.z) &&
        point.x < (b[0] - a[0]) * (point.z - a[1]) / (b[1] - a[1]) + a[0]) hit = !hit;
  }
  return hit;
}
export function distanceToEdge(p, a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const t = Math.max(0, Math.min(1, ((p.x - a[0]) * dx + (p.z - a[1]) * dz) / (dx * dx + dz * dz)));
  return Math.hypot(p.x - a[0] - t * dx, p.z - a[1] - t * dz);
}
export function createWorld(data, radius = .22) {
  const obstacles = data.OBSTACLES ? [...data.OBSTACLES] : [data.HOUSE, data.GARAGE, data.POOL];   // from the layout when given
  for (const f of data.FURNITURE || []) {
    if (['playhouse', 'woodshed'].includes(f.type)) obstacles.push([
      [f.x-f.w/2,f.z-f.d/2],[f.x+f.w/2,f.z-f.d/2],
      [f.x+f.w/2,f.z+f.d/2],[f.x-f.w/2,f.z+f.d/2]
    ]);
  }
  const nearEdge = (p, poly) => poly.some((a,i) => distanceToEdge(p,a,poly[(i+1)%poly.length]) < radius);
  return {
    canStand(p) {
      return inside(p,data.P) && !nearEdge(p,data.P) &&
        obstacles.every(poly => !inside(p,poly) && !nearEdge(p,poly));
    },
    ground(p) {
      if (inside(p,data.DECK_EDGE)) return .15;
      if (inside(p,data.RAMP)) return -.9 * Math.max(0,Math.min(1,(p.z-23.2)/(31.07-23.2)));
      return .03;
    }
  };
}
export function advance(position, yaw, input, seconds, world) {
  const dt = Math.max(0,Math.min(.1,seconds));
  yaw += input.turn * 1.65 * dt;
  const speed = input.run ? 4.2 : 1.65;
  const length = Math.hypot(input.forward,input.side) || 1;
  const f = input.forward / Math.max(1,length), s = input.side / Math.max(1,length);
  const dx = (-Math.sin(yaw)*f + Math.cos(yaw)*s)*speed*dt;
  const dz = (-Math.cos(yaw)*f - Math.sin(yaw)*s)*speed*dt;
  const steps = Math.max(1,Math.ceil(Math.hypot(dx,dz)/.06));
  const p = {...position};
  for (let i=0;i<steps;i++) {
    if(world.canStand({x:p.x+dx/steps,z:p.z})) p.x+=dx/steps;
    if(world.canStand({x:p.x,z:p.z+dz/steps})) p.z+=dz/steps;
  }
  return {position:p,yaw};
}
