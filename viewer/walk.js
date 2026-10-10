// Walking with arrow keys and collisions. Written by Codex for experiments/realism, here the world comes from the layout.
import {createWorld, advance} from './navigation.mjs';
export function createWalkController({camera,controls,canvas,data,requestRender,stage}) {
  let world=createWorld(data);const keys=new Set();
  let active=false,yaw=0,pitch=0,raf=0,last=0,drag=null;
  const codes=new Set(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight','KeyW','KeyA','KeyS','KeyD','ShiftLeft','ShiftRight']);
  canvas.tabIndex=0;canvas.setAttribute('aria-label','3D zahrada. Šipky pro pohyb, Shift pro běh, myš pro rozhlížení.');
  function syncAngles(){const v=new THREE.Vector3();camera.getWorldDirection(v);yaw=Math.atan2(-v.x,-v.z);pitch=Math.asin(v.y);}
  function aim(){camera.rotation.order='YXZ';camera.rotation.set(pitch,yaw,0);}
  function stop(){keys.clear();if(raf)cancelAnimationFrame(raf);raf=0;last=0;drag=null;}
  function record(){stage.dataset.cameraX=camera.position.x.toFixed(3);stage.dataset.cameraZ=camera.position.z.toFixed(3);stage.dataset.yaw=yaw.toFixed(3);}
  function step(now){raf=0;if(!active||!keys.size||document.getElementById('model').hidden){stop();return;}
    const dt=last?(now-last)/1000:1/60;last=now;
    const input={forward:Number(keys.has('ArrowUp')||keys.has('KeyW'))-Number(keys.has('ArrowDown')||keys.has('KeyS')),side:Number(keys.has('KeyD'))-Number(keys.has('KeyA')),turn:Number(keys.has('ArrowLeft'))-Number(keys.has('ArrowRight')),run:keys.has('ShiftLeft')||keys.has('ShiftRight')};
    const next=advance({x:camera.position.x,z:camera.position.z},yaw,input,dt,world);yaw=next.yaw;
    camera.position.x=next.position.x;camera.position.z=next.position.z;
    camera.position.y+=(world.ground(next.position)+1.7-camera.position.y)*Math.min(1,dt*14);
    aim();record();requestRender();raf=requestAnimationFrame(step);
  }
  function press(code){if(!active||!codes.has(code))return;const fresh=!keys.has(code);keys.add(code);if(!raf)step(performance.now());else if(fresh&&!code.startsWith('Shift')){cancelAnimationFrame(raf);raf=0;last=0;step(performance.now());}}
  function release(code){keys.delete(code);if(!keys.size)stop();}
  function setActive(value,focus=false,keepTarget=false){
    stop();active=value;controls.enabled=!active;
    if(active){if(!world.canStand(camera.position)||camera.position.y>3){camera.position.set(.8,1.73,19.5);camera.lookAt(-4.2,1.2,9);}camera.position.y=world.ground(camera.position)+1.7;syncAngles();aim();}
    else if(!keepTarget) {const direction=new THREE.Vector3();camera.getWorldDirection(direction);controls.target.copy(camera.position).addScaledVector(direction,6);controls.update();}
    document.querySelectorAll('[data-navigation]').forEach(b=>b.setAttribute('aria-pressed',(b.dataset.navigation==='walk')===active));
    document.getElementById('move-pad').hidden=!active;stage.dataset.navigation=active?'walk':'orbit';record();requestRender();if(focus)canvas.focus({preventScroll:true});
  }
  canvas.addEventListener('keydown',e=>{if(active&&codes.has(e.code)){e.preventDefault();press(e.code);}if(e.code==='Escape'){stop();if(document.fullscreenElement)document.exitFullscreen().catch(()=>{});}});
  window.addEventListener('keyup',e=>release(e.code));window.addEventListener('blur',stop);canvas.addEventListener('blur',stop);
  document.addEventListener('visibilitychange',stop);document.querySelectorAll('[role=tab]').forEach(b=>b.addEventListener('click',stop));
  canvas.addEventListener('pointerdown',e=>{if(!active)return;canvas.focus({preventScroll:true});drag={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!active||!drag)return;yaw-=(e.clientX-drag.x)*.004;pitch=Math.max(-1.2,Math.min(1.2,pitch-(e.clientY-drag.y)*.004));drag={x:e.clientX,y:e.clientY};aim();record();requestRender();});
  canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',stop);
  for(const button of document.querySelectorAll('[data-navigation]'))button.onclick=()=>setActive(button.dataset.navigation==='walk',true);
  for(const button of document.querySelectorAll('[data-move]')){
    button.onpointerdown=e=>{e.preventDefault();canvas.focus({preventScroll:true});button.setPointerCapture(e.pointerId);press(button.dataset.move);};
    button.onpointerup=button.onpointercancel=()=>release(button.dataset.move);
    button.onlostpointercapture=()=>release(button.dataset.move);
  }
  document.getElementById('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await stage.requestFullscreen();canvas.focus({preventScroll:true});}catch{document.getElementById('walk-hint').textContent='Celá obrazovka není v tomto prohlížeči dostupná; šipky fungují i v panelu.';}};
  document.getElementById('exit-fullscreen').onclick=()=>document.exitFullscreen().catch(()=>{});
  setActive(true,true);
  return {setActive,stop,syncView(walking){setActive(walking,false,true);},setData(d){world=createWorld(d);},get world(){return world;},get active(){return active;}};
}
