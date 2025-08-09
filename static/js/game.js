// Mini Farm — фон (CSS) на весь экран, канвас рисует поле между панелями.
// Авторизация Ed25519, action-token для POST, rate-limit на сервере, без скролла/зума.

(() => {
  const tg = window.Telegram?.WebApp;
  const cfgEl = document.getElementById('app-config');
  const BG_SRC = cfgEl?.dataset?.bg || '';

  // ---------- UI ----------
  const $ = (s) => document.querySelector(s);
  const show = (el) => el && el.classList.remove('hidden');
  const hide = (el) => el && el.classList.add('hidden');
  const debugGate = (msg)=>{ const el=$('#gate-text'); if(el) el.textContent=`[debug] ${msg}`; };

  function showMessage(text, retry=false){
    const txt=$('#gate-text'), btn=$('#retryBtn');
    if(txt) txt.textContent = text;
    show($('#gate')); hide($('#scene')); hide($('#hud')); hide($('#bottom'));
    if(btn) btn.classList.toggle('hidden', !retry);
  }
  function showGameUI(name, balance){
    $('#playerName').textContent = name || 'Игрок';
    $('#playerSub').textContent  = 'Хорошего урожая!';
    $('#balance').textContent    = balance ?? 0;
    hide($('#gate')); show($('#scene')); show($('#hud')); show($('#bottom'));
    requestRender();
  }

  // Регулировка отступов панелей при желании
  function setLayoutVars({ hudH, hudTopGap, bottomH, bottomGap } = {}){
    const root = document.documentElement;
    if (hudH != null)      root.style.setProperty('--hud-h', addPx(hudH));
    if (hudTopGap != null) root.style.setProperty('--hud-top-gap', addPx(hudTopGap));
    if (bottomH != null)   root.style.setProperty('--bottom-h', addPx(bottomH));
    if (bottomGap != null) root.style.setProperty('--bottom-gap', addPx(bottomGap));
    requestRender();
  }
  const addPx = v => (String(v).endsWith('px') ? String(v) : `${v}px`);

  // ---------- API ----------
  let ACTION_TOKEN = null;

  async function apiMe(){
    try{ const r=await fetch('/api/me',{credentials:'same-origin'}); return r.ok? r.json(): null; }
    catch{ return null; }
  }
  async function apiState(){
    try{ const r=await fetch('/api/state',{credentials:'same-origin'}); return r.ok? r.json(): null; }
    catch{ return null; }
  }
  async function apiVerify(extra){
    const initData = tg?.initData; if(!initData) return {ok:false,text:'initData missing'};
    try{
      const r = await fetch('/auth/verify',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'same-origin',
        body: JSON.stringify({ initData, ...extra })
      });
      const text = await r.text();
      return { ok:r.ok, text };
    }catch(e){ return { ok:false, text:String(e) }; }
  }
  async function apiOpenSoil(){
    const r = await fetch('/api/open_soil', {
      method:'POST',
      credentials:'same-origin',
      headers: { 'X-Action-Token': ACTION_TOKEN || '' }
    });
    return r.json().catch(()=>({ok:false}));
  }

  // ---------- WebApp / фон ----------
  function hardenWebApp(){
    try{
      tg?.ready(); tg?.expand();
      tg?.setHeaderColor('secondary_bg_color');
      tg?.setBackgroundColor('#0f172a');
      tg?.disableVerticalSwipes?.();
    }catch(_){}
    // Фон как CSS-слой
    if (BG_SRC){
      document.documentElement.style.setProperty('--bg-image', `url('${BG_SRC}')`);
    }
    // Запрет жестов зума/скролла
    let lastTouch=0;
    window.addEventListener('touchend', e=>{
      const now=Date.now(); if(now-lastTouch<=300){ e.preventDefault(); }
      lastTouch=now;
    }, {passive:false});
    ['touchmove','gesturestart','gesturechange','gestureend'].forEach(ev=>{
      window.addEventListener(ev, e=>e.preventDefault(), {passive:false});
    });
  }

  // ---------- Сцена / сетка ----------
  const BASE_W=768, BASE_H=1429;
  const COLS=4, ROWS=4, MAX=COLS*ROWS; // 16
  const TILE=150, GAP=20;
  const GRID_W = COLS*TILE + (COLS-1)*GAP;
  const GRID_X0 = Math.round((BASE_W - GRID_W)/2);
  const GRID_Y0 = 560;                 // при необходимости отрегулировать

  const img = { soil:new Image(), plus:new Image() };
  img.soil.src = '/static/img/tiles/soil.png';
  img.plus.src = '/static/img/tiles/plus.png';

  const field = { soilsCount: 2, balance: 0, name: 'Игрок' };
  const ANIM_MS = 320;
  const anim = new Map(); // idx -> { t }

  let rafId=null, needsRender=true;
  const canvas = $('#field');
  const ctx = canvas.getContext('2d');

  function layout(){
    const scene = $('#scene');
    const rect = scene.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = Math.max(1, Math.round(rect.width  * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    return { w: rect.width, h: rect.height, dpr };
  }

  const plusIndex = () => (field.soilsCount < MAX ? field.soilsCount : -1);
  const cellPos = (i) => { const r=Math.floor(i/COLS), c=i%COLS; return { x: GRID_X0 + c*(TILE+GAP), y: GRID_Y0 + r*(TILE+GAP) }; };

  function easePop(t){ const s=1.70158,p=1.525; if((t*=2)<1) return 0.6+(t*t*(((s*p)+1)*t-(s*p)))*0.4; t-=2; return 1+(t*t*(((s*p)+1)*t+(s*p)))*0.04; }
  function drawScaled(image,x,y,size,scale,ctx2){ const cx=x+size/2, cy=y+size/2, s=size*scale; ctx2.save(); const sh=Math.max(0,(scale-1)*20); if(sh>0){ctx2.shadowColor='rgba(0,0,0,0.25)';ctx2.shadowBlur=sh;} ctx2.translate(cx,cy); ctx2.drawImage(image,-s/2,-s/2,s,s); ctx2.restore(); }

  function render(){
    const { w, h, dpr } = layout();
    const ctx2 = ctx;

    // Поле вписываем (contain) между панелями
    const scale = Math.min(w/BASE_W, h/BASE_H);
    const drawW = BASE_W*scale, drawH = BASE_H*scale;
    const offX = (w - drawW)/2, offY = (h - drawH)/2;

    ctx2.setTransform(1,0,0,1,0,0);
    ctx2.clearRect(0,0,canvas.width,canvas.height);
    ctx2.scale(dpr, dpr);
    ctx2.translate(offX, offY);
    ctx2.scale(scale, scale);

    for(let i=0;i<MAX;i++){
      const {x,y}=cellPos(i);
      if (i < field.soilsCount){
        const a=anim.get(i);
        if(a){ drawScaled(img.soil,x,y,TILE,easePop(a.t),ctx2); }
        else if(img.soil.complete) ctx2.drawImage(img.soil,x,y,TILE,TILE);
      } else if (i === plusIndex()){
        if(img.plus.complete) ctx2.drawImage(img.plus,x,y,TILE,TILE);
      }
    }
  }

  function tick(){ rafId=null; let any=false; anim.forEach(a=>{ a.t+=16/ANIM_MS; if(a.t<1) any=true; else a.t=1; }); if(needsRender||any){ render(); needsRender=false; rafId=requestAnimationFrame(tick); } }
  function requestRender(){ needsRender=true; if(!rafId) rafId=requestAnimationFrame(tick); }

  function pickBasicCoords(evt){
    const rect = canvas.getBoundingClientRect();
    const x = (evt.clientX - rect.left) * (canvas.width / rect.width);
    const y = (evt.clientY - rect.top ) * (canvas.height/ rect.height);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    return { x: x/dpr, y: y/dpr, rect };
  }

  function onFieldClick(evt){
    const { x:px, y:py, rect } = pickBasicCoords(evt);
    const w=rect.width, h=rect.height;
    const scale = Math.min(w/BASE_W, h/BASE_H);
    const offX = (w - BASE_W*scale)/2;
    const offY = (h - BASE_H*scale)/2;
    const bx = (px - offX)/scale;
    const by = (py - offY)/scale;

    const idx = plusIndex();
    if (idx < 0) return;
    const {x:cx,y:cy} = cellPos(idx);
    if (bx>=cx && bx<=cx+TILE && by>=cy && by<=cy+TILE){
      openSoil();
    }
  }

  async function openSoil(){
    let res = await apiOpenSoil();
    if(!res?.ok && res?.error === 'forbidden'){
      const st = await apiState();         // авто-лечим токен
      if (st?.ok && st.action_token){
        ACTION_TOKEN = st.action_token;
        res = await apiOpenSoil();
      }
    }
    if(!res?.ok){
      if (res?.error === 'too_fast') return; // тихо игнорим
      if (res?.error === 'not_enough_money') alert('Не хватает монет.');
      else if (res?.error === 'max_reached') alert('Достигнут максимум.');
      else if (res?.error === 'forbidden') alert('Сессия устарела. Перезайдите в Mini App.');
      else alert('Ошибка. Перезайдите в Mini App.');
      return;
    }
    const old = field.soilsCount;
    field.soilsCount = res.soils_count;
    field.balance    = res.balance;
    $('#balance').textContent = field.balance;
    anim.set(old, { t:0 });
    requestRender();
  }

  // ---------- Init ----------
  async function init(){
    hardenWebApp();

    // При желании подстрой: setLayoutVars({ hudH: 72, hudTopGap: 30, bottomH: 96, bottomGap: 10 });

    const platform = tg?.platform || 'no-tg';
    const version  = tg?.version  || 'n/a';
    debugGate(`platform=${platform}, version=${version}, hasInitData=${typeof tg?.initData === 'string'}`);

    try{ await fetch('/api/me',{credentials:'same-origin'}); }catch(_){}

    if (typeof tg?.initData === 'string' && tg.initData.length){
      const ver = await apiVerify({ platform, version });
      if(!ver.ok){
        debugGate(`auth fail: ${ver.text?.slice(0,140)||'unknown'}`);
        showMessage('Не удалось авторизоваться. Перезайдите в Mini App из Telegram на телефоне.', true);
        bindRetry(); return;
      }
      const st = await apiState();
      if(st?.ok){
        ACTION_TOKEN = st.action_token || null;
        field.name = st.name; field.balance = st.balance; field.soilsCount = st.soils_count;
        showGameUI(st.name, st.balance);
      } else {
        showMessage('Перезайдите в Mini App из Telegram на телефоне.', true);
        bindRetry();
      }
    } else {
      showMessage('Откройте игру из Telegram на телефоне.', true);
      bindRetry();
    }

    window.addEventListener('resize', requestRender, {passive:true});
    img.soil.onload=requestRender; img.plus.onload=requestRender;
    $('#field').addEventListener('click', onFieldClick);
  }

  function bindRetry(){ const b=$('#retryBtn'); if(b) b.onclick=()=>{ debugGate('retry…'); init(); }; }

  document.addEventListener('DOMContentLoaded', init);
})();
