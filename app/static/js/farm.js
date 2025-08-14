// app/static/js/farm.js
(function () {
  // ===== DOM
  const grid = document.getElementById("fieldGrid");
  const nameEl = document.getElementById("playerName");
  const balanceEl = document.getElementById("playerBalance");

  const modal = document.getElementById("modal");
  const modalBody = document.getElementById("modalBody");
  const modalClose = document.getElementById("modalClose");

  const btnInventory = document.getElementById("btnInventory");
  const btnShop = document.getElementById("btnShop");
  const toastHost = document.getElementById("toastHost");

  // ===== State
  let state = null;
  let lastNonce = null;

  // Серверное UTC‑время + performance.now()
  let serverBaseMs = 0;
  let perfBase = 0;

  // анти‑дабл
  let isBuyingField = false;
  let isBuyingItem = false;
  let isPlanting = false;
  let isHarvesting = false;
  let isSellingItem = false;

  // длительности культур (мс) — клиент только для таймера UI
  const CROP_DURATION_MS = { 
    wheat: 120000,      // 2 минуты
    carrot: 144000,     // 2.4 минуты  
    watermelon: 172800, // 2.88 минуты
    pumpkin: 207360,    // 3.456 минуты
    onion: 248832       // 4.147 минуты
  };

  // ===== Utils
  const cssVar = (name, fallback) => {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name);
    const n = parseInt(v);
    return Number.isFinite(n) ? n : fallback;
  };
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  function toMsMaybe(x) { if (!Number.isFinite(x)) return x; return x < 1e12 ? x * 1000 : x; }
  function parseIsoToMs(iso) { if (!iso) return null; const t = Date.parse(iso); return Number.isFinite(t) ? t : null; }

  function formatRemain(ms) {
    ms = Math.max(0, ms | 0);
    const s = Math.ceil(ms / 1000);
    const m = Math.floor(s / 60);
    const ss = s % 60;
    return m > 0 ? `${m}:${String(ss).padStart(2, "0")}` : `${s}s`;
  }
  function nowServerAligned() {
    if (!serverBaseMs) return Date.now();
    return serverBaseMs + (performance.now() - perfBase);
  }
  function applyServerTimeDelta(fromState) {
    let base = Number(fromState?.server_time_unix_ms);
    if (!Number.isFinite(base)) base = parseIsoToMs(fromState?.server_time_iso);
    else base = toMsMaybe(base);
    if (Number.isFinite(base)) { serverBaseMs = base; perfBase = performance.now(); }
  }
  function computeReadyAtMs(plot) {
    if (!plot || !plot.crop_key) return null;
    const dur = CROP_DURATION_MS[plot.crop_key];
    if (!Number.isFinite(dur)) return null;
    let planted = Number(plot.planted_at_unix_ms);
    if (!Number.isFinite(planted) && plot.planted_at_iso) planted = parseIsoToMs(plot.planted_at_iso);
    if (!Number.isFinite(planted)) return null;
    planted = toMsMaybe(planted);
    return planted + dur;
  }
  function computeRemainMs(plot) {
    const readyAt = computeReadyAtMs(plot);
    if (!Number.isFinite(readyAt)) return null;
    return Math.max(0, readyAt - nowServerAligned());
  }

  // ===== Toasts
  const toastQueue = [];
  let toastShowing = false;
  function showToast(text, type = "info", duration = 1200) {
    toastQueue.push({ text, type, duration });
    if (!toastShowing) pumpToast();
  }
  async function pumpToast() {
    toastShowing = true;
    while (toastQueue.length) {
      const { text, type, duration } = toastQueue.shift();
      const el = document.createElement("div");
      el.className = `toast ${type}`;
      el.textContent = text;
      toastHost.appendChild(el);
      requestAnimationFrame(() => el.classList.add("show"));
      await sleep(duration);
      el.classList.remove("show");
      await sleep(200);
      el.remove();
    }
    toastShowing = false;
  }

  // ===== Modal helpers
  function openModal(title, contentNode) {
    const card = document.createElement("div");
    card.className = "modal-card";

    const head = document.createElement("div");
    head.className = "modal-head";

    const titleEl = document.createElement("div");
    titleEl.className = "modal-title";
    titleEl.textContent = title;

    head.appendChild(titleEl);
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "modal-body";
    if (contentNode instanceof Node) body.appendChild(contentNode);
    else if (typeof contentNode === "string") body.textContent = contentNode;
    card.appendChild(body);

    modalBody.innerHTML = "";
    modalBody.appendChild(card);
    modal.classList.add("open");
  }
  function closeModal() { modal.classList.remove("open"); }

  // ===== Server sync
  async function fetchState(full = true) {
    const r = await fetch("/api/state", { credentials: "same-origin" });
    const j = await r.json();
    if (!j.ok) { 
      if (j.error === "user_blocked") {
        sessionStorage.setItem("blocked_reason", j.blocked_reason || "Аккаунт заблокирован");
        location.replace("/blocked");
      } else {
        location.replace("/");
      }
      return; 
    }

    const prevPlots = state?.plots ? state.plots.slice() : null;

    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);

    if (!("plots" in state) && prevPlots) state.plots = prevPlots;

    renderHeader();

    if (full || grid.childElementCount === 0) buildFullGrid();
    else {
      const owned = Math.min(state.fields_owned || 0, cssVar("--grid-cols", 4) * cssVar("--grid-rows", 4));
      for (let i = 0; i < owned; i++) updateTile(i);
      movePlus();
    }
  }

  // ===== Header
  function renderHeader() {
    nameEl.textContent = state.display_name || state.first_name || state.username || "Игрок";
    balanceEl.textContent = state.balance;
  }

  // ===== Grid
  function buildFullGrid() {
    grid.innerHTML = "";
    const cols = cssVar("--grid-cols", 4);
    const rows = cssVar("--grid-rows", 4);
    const maxCells = cols * rows;
    const owned = Math.min(state.fields_owned || 0, maxCells);

    const planted = new Map((state.plots || []).map(p => [p.idx, p]));
    for (let i = 0; i < owned; i++) grid.appendChild(buildTile(i, planted.get(i)));
    if (owned < maxCells) grid.appendChild(buildPlus());
  }
  function buildTile(index, plotObj) {
    const t = document.createElement("div");
    t.className = "tile";
    t.dataset.index = String(index);
    applyPlotVisual(t, plotObj);
    t.addEventListener("click", () => {
      t.classList.add("bump");
      setTimeout(() => t.classList.remove("bump"), 180);
      const p = plotObjFromState(index);
      if (!p || !p.crop_key) openPlantMenu(index);
    });
    return t;
  }
  function buildPlus() {
    const plus = document.createElement("div");
    plus.className = "tile plus";
    plus.title = "Купить поле";
    plus.dataset.plus = "1";
    return plus;
  }
  function plotObjFromState(idx) { return (state.plots || []).find(p => p.idx === idx); }
  function updateTile(index) {
    let el = grid.querySelector(`.tile[data-index="${index}"]`);
    if (!el) {
      el = buildTile(index, plotObjFromState(index));
      const children = Array.from(grid.children).filter(c => !c.dataset.plus);
      const plus = grid.querySelector('.tile.plus');
      const insertBefore = plus || grid.children[children.length] || null;
      grid.insertBefore(el, insertBefore);
      return;
    }
    el.className = "tile";
    el.innerHTML = "";
    applyPlotVisual(el, plotObjFromState(index));
  }

  // визуал тайла, таймер, и кнопка «Собрать»
  function applyPlotVisual(tileEl, plotObj) {
    tileEl.innerHTML = "";
    if (plotObj && plotObj.crop_key) {
      tileEl.classList.add(`planted-${plotObj.crop_key}`);
      if (plotObj.stage) tileEl.classList.add(`stage-${plotObj.stage}`);

      const remain = computeRemainMs(plotObj);
      if (remain !== null && remain <= 0) {
        const btn = document.createElement("button");
        btn.className = "harvest-btn";
        btn.textContent = "Собрать";
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          harvestPlot(tileEl.dataset.index|0);
        });
        tileEl.appendChild(btn);
        tileEl.classList.remove("stage-sprout","stage-young","stage-mature");
        tileEl.classList.add("stage-ready");
        return;
      }
      if (remain !== null) {
        const badge = document.createElement("div");
        badge.className = "timer-badge";
        const readyAt = computeReadyAtMs(plotObj);
        badge.dataset.readyAt = String(readyAt);
        badge.dataset.fired = "0";
        badge.textContent = formatRemain(remain);
        tileEl.appendChild(badge);
      }
    }
  }

  function movePlus() {
    const cols = cssVar("--grid-cols", 4);
    const rows = cssVar("--grid-rows", 4);
    const maxCells = cols * rows;
    const owned = Math.min(state.fields_owned || 0, maxCells);

    const plus = grid.querySelector(".tile.plus");
    const needPlus = owned < maxCells;

    if (needPlus) {
      const desiredPos = owned;
      if (!plus) {
        const newPlus = buildPlus();
        grid.insertBefore(newPlus, grid.children[desiredPos] || null);
      } else {
        const currentIndex = Array.from(grid.children).indexOf(plus);
        if (currentIndex !== desiredPos) {
          plus.remove();
          grid.insertBefore(plus, grid.children[desiredPos] || null);
        }
      }
    } else if (plus) plus.remove();
  }

  // Клик по «плюсику»
  grid.addEventListener("click", (e) => {
    const plus = e.target.closest(".tile.plus");
    if (!plus || !grid.contains(plus)) return;
    e.preventDefault();
    buyField();
  });

  // ===== Global ticker
  setInterval(() => {
    const now = nowServerAligned();
    document.querySelectorAll(".timer-badge").forEach((badge) => {
      const ra = parseInt(badge.dataset.readyAt || "0", 10);
      if (!Number.isFinite(ra) || ra <= 0) return;

      const remain = Math.max(0, ra - now);
      badge.textContent = formatRemain(remain);

      if (remain <= 0 && badge.dataset.fired !== "1") {
        badge.dataset.fired = "1";
        const tile = badge.closest(".tile");
        if (!tile) return;
        badge.remove();

        const btn = document.createElement("button");
        btn.className = "harvest-btn";
        btn.textContent = "Собрать";
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          harvestPlot(tile.dataset.index|0);
        });
        tile.appendChild(btn);

        tile.classList.remove("stage-sprout","stage-young","stage-mature");
        tile.classList.add("stage-ready");
      }
    });
  }, 300);

  // ===== Inventory
  function inventoryRow({item_key, qty}){
    const row = document.createElement("div");
    row.className = "menu-row";

    const left = document.createElement("div");
    const t = document.createElement("div");
    t.className = "menu-title";
    
    const itemNames = {
      // Семена
      "seed_wheat": "Семена пшеницы",
      "seed_carrot": "Семена моркови", 
      "seed_watermelon": "Семена арбуза",
      "seed_pumpkin": "Семена тыквы",
      "seed_onion": "Семена лука",
      // Урожай
      "crop_wheat": "Пшеница",
      "crop_carrot": "Морковь",
      "crop_watermelon": "Арбуз", 
      "crop_pumpkin": "Тыква",
      "crop_onion": "Лук"
    };
    
    t.textContent = itemNames[item_key] || item_key;
    
    const sub = document.createElement("div");
    sub.className = "menu-sub";
    
    // Показываем цену продажи только для продаваемых предметов
    const sellPrices = { 
      "crop_wheat": 10,
      "crop_carrot": 20,
      "crop_watermelon": 40,
      "crop_pumpkin": 80,
      "crop_onion": 160
    };
    
    if (sellPrices[item_key]) {
      sub.textContent = `Цена: ${sellPrices[item_key]} монет`;
    } else {
      sub.textContent = "Нельзя продать";
    }
    
    left.appendChild(t); 
    left.appendChild(sub);

    const right = document.createElement("div");
    right.style.display = "flex";
    right.style.alignItems = "center";
    right.style.gap = "8px";

    const qtyPill = document.createElement("div");
    qtyPill.className = "qty-pill";
    qtyPill.textContent = `×${qty}`;

    right.appendChild(qtyPill);

    // Добавляем кнопку продажи только для продаваемых предметов
    if (sellPrices[item_key] && qty > 0) {
      const btn = document.createElement("button");
      btn.className = "pill-btn";
      btn.textContent = "продать";
      btn.addEventListener("click", async ()=>{ await sellItem(item_key, btn); });
      right.appendChild(btn);
    }

    row.appendChild(left);
    row.appendChild(right);
    return row;
  }

  async function openInventoryModal(){
    const wrap = document.createElement("div");
    wrap.className = "menu-list";

    const r = await fetch("/api/inventory", { credentials:"same-origin" });
    const j = await r.json();

    if (!j.ok){
      const err = document.createElement("div");
      err.className = "menu-title"; err.textContent = "Ошибка загрузки";
      wrap.appendChild(err);
      openModal("Инвентарь", wrap);
      return;
    }

    if (!j.inventory.length){
      const empty = document.createElement("div");
      empty.className = "menu-title"; empty.textContent = "Инвентарь пуст";
      wrap.appendChild(empty);
    } else {
      j.inventory.forEach(it=>{
        wrap.appendChild(inventoryRow(it));
      });
    }
    openModal("Инвентарь", wrap);
  }

  async function updateInventoryModal() {
    // Ищем body внутри modal-card, а не весь modalBody
    const modalCard = modal.querySelector(".modal-card");
    const modalBodyContent = modalCard ? modalCard.querySelector(".modal-body") : null;
    if (!modalBodyContent || modal.style.display === "none") return;

    const wrap = document.createElement("div");
    wrap.className = "menu-list";

    const r = await fetch("/api/inventory", { credentials:"same-origin" });
    const j = await r.json();

    if (!j.ok){
      const err = document.createElement("div");
      err.className = "menu-title"; err.textContent = "Ошибка загрузки";
      wrap.appendChild(err);
      modalBodyContent.innerHTML = "";
      modalBodyContent.appendChild(wrap);
      return;
    }

    if (!j.inventory.length){
      const empty = document.createElement("div");
      empty.className = "menu-title"; empty.textContent = "Инвентарь пуст";
      wrap.appendChild(empty);
    } else {
      j.inventory.forEach(it=>{
        wrap.appendChild(inventoryRow(it));
      });
    }

    modalBodyContent.innerHTML = "";
    modalBodyContent.appendChild(wrap);
  }

  // ===== Shop
  function shopRow({title, price, key}){
    const row = document.createElement("div");
    row.className = "menu-row";

    const left = document.createElement("div");
    const t = document.createElement("div");
    t.className = "menu-title"; t.textContent = title;
    const sub = document.createElement("div");
    sub.className = "menu-sub"; sub.textContent = `${price} монет`;
    left.appendChild(t); left.appendChild(sub);

    const btn = document.createElement("button");
    btn.className = "pill-btn"; btn.textContent = "купить";
    btn.addEventListener("click", async ()=>{ await buyItem(key, btn); });

    row.appendChild(left);
    row.appendChild(btn);
    return row;
  }
  async function openShopModal(){
    const list = document.createElement("div");
    list.className = "menu-list";
    const catalog = [
      { key:"seed_wheat", title:"Семена пшеницы", price:5 },
      { key:"seed_carrot", title:"Семена моркови", price:10 },
      { key:"seed_watermelon", title:"Семена арбуза", price:20 },
      { key:"seed_pumpkin", title:"Семена тыквы", price:40 },
      { key:"seed_onion", title:"Семена лука", price:80 }
    ];
    catalog.forEach(item => list.appendChild(shopRow(item)));
    openModal("Магазин", list);
  }

  // ===== Actions
  async function buyField() {
    if (isBuyingField) return;
    isBuyingField = true;

    if (!lastNonce) await fetchState(true);

    const r = await fetch("/api/action/buy_field", {
      method: "POST",
      headers: { "X-Action-Nonce": lastNonce },
      credentials: "same-origin",
    });
    const j = await r.json();

    isBuyingField = false;

    if (!j.ok) {
      if (j.error === "bad_or_expired_nonce") await fetchState(true);
      else if (j.error === "not_enough_money") showToast("Недостаточно монет", "error");
      else if (j.error === "max_fields") showToast("Максимум полей", "info");
      return;
    }

    const prevPlots = state?.plots ? state.plots.slice() : null;

    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);
    if (!("plots" in state) && prevPlots) state.plots = prevPlots;

    renderHeader();

    const idx = j.bought_index ?? (state.fields_owned - 1);
    updateTile(idx);
    movePlus();

    const t = grid.querySelector(`.tile[data-index="${idx}"]`);
    if (t) { t.classList.add("new-field"); setTimeout(() => t.classList.remove("new-field"), 260); }

    showToast("Поле куплено", "success");
  }

  async function buyItem(item_key, btnEl) {
    if (isBuyingItem) return;
    isBuyingItem = true;
    if (!lastNonce) await fetchState(true);
    const oldText = btnEl.textContent;
    btnEl.disabled = true; btnEl.textContent = "…";

    const r = await fetch("/api/action/shop/buy", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Action-Nonce": lastNonce },
      body: JSON.stringify({ item_key }),
      credentials: "same-origin",
    });
    const j = await r.json();

    isBuyingItem = false;
    btnEl.disabled = false; btnEl.textContent = oldText;

    if (!j.ok) {
      if (j.error === "bad_or_expired_nonce") await fetchState(true);
      else if (j.error === "not_enough_money") showToast("Недостаточно монет", "error");
      else if (j.error === "unknown_item") showToast("Неизвестный товар", "error");
      return;
    }

    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);
    renderHeader();
    showToast(`Куплено: ${j.bought.title} ×${j.bought.qty}`, "success");
  }

  async function sellItem(item_key, btnEl) {
    if (isSellingItem) return;
    isSellingItem = true;
    if (!lastNonce) await fetchState(true);
    const oldText = btnEl.textContent;
    btnEl.disabled = true; btnEl.textContent = "…";

    const r = await fetch("/api/action/sell", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Action-Nonce": lastNonce },
      body: JSON.stringify({ item_key }),
      credentials: "same-origin",
    });
    const j = await r.json();

    isSellingItem = false;
    btnEl.disabled = false; btnEl.textContent = oldText;

    if (!j.ok) {
      if (j.error === "bad_or_expired_nonce") await fetchState(true);
      else if (j.error === "no_items") showToast("Нет предметов для продажи", "error");
      else if (j.error === "cannot_sell_item") showToast("Этот предмет нельзя продать", "error");
      return;
    }

    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);
    renderHeader();
    
    const itemNames = {
      "crop_wheat": "Пшеница",
      "crop_carrot": "Морковь",
      "crop_watermelon": "Арбуз", 
      "crop_pumpkin": "Тыква",
      "crop_onion": "Лук"
    };
    const itemName = itemNames[item_key] || item_key;
    showToast(`Продано: ${itemName} (+${j.sold.price} монет)`, "success");
    
    // Обновляем содержимое инвентаря без закрытия модального окна
    await updateInventoryModal();
  }

  async function openPlantMenu(idx) {
    const r = await fetch("/api/inventory", { credentials: "same-origin" });
    const j = await r.json();
    if (!j.ok) { showToast("Ошибка инвентаря", "error"); return; }

    const seeds = new Map(j.inventory.map((it) => [it.item_key, it.qty]));
    
    const seedTypes = [
      { key: "seed_wheat", name: "Семена пшеницы", time: "2 мин" },
      { key: "seed_carrot", name: "Семена моркови", time: "2.4 мин" },
      { key: "seed_watermelon", name: "Семена арбуза", time: "2.9 мин" },
      { key: "seed_pumpkin", name: "Семена тыквы", time: "3.5 мин" },
      { key: "seed_onion", name: "Семена лука", time: "4.1 мин" }
    ];

    const wrap = document.createElement("div");
    wrap.className = "menu-list";
    
    let hasSeeds = false;
    seedTypes.forEach(seedType => {
      const qty = seeds.get(seedType.key) || 0;
      if (qty > 0) {
        const row = document.createElement("div");
        row.className = "menu-row";
        
        const left = document.createElement("div");
        const title = document.createElement("div");
        title.className = "menu-title";
        title.textContent = seedType.name;
        
        const sub = document.createElement("div");
        sub.className = "menu-sub";
        sub.textContent = `Время роста: ${seedType.time}`;
        
        left.appendChild(title);
        left.appendChild(sub);
        
        const right = document.createElement("div");
        right.style.display = "flex";
        right.style.alignItems = "center";
        right.style.gap = "8px";
        
        const qtyPill = document.createElement("div");
        qtyPill.className = "qty-pill";
        qtyPill.textContent = `×${qty}`;
        
        const btn = document.createElement("button");
        btn.className = "pill-btn";
        btn.textContent = "посадить";
        btn.addEventListener("click", async () => {
          if (isPlanting) return;
          isPlanting = true;
          btn.disabled = true;
          await plantSeed(idx, seedType.key);
          btn.disabled = false;
          isPlanting = false;
        });
        
        right.appendChild(qtyPill);
        right.appendChild(btn);
        
        row.appendChild(left);
        row.appendChild(right);
        wrap.appendChild(row);
        hasSeeds = true;
      }
    });

    if (!hasSeeds) {
      const t = document.createElement("div");
      t.className = "menu-title";
      t.textContent = "Нет подходящих семян.";
      wrap.appendChild(t);
    }

    openModal("Посадка", wrap);
  }

  async function plantSeed(idx, seedKey) {
    if (!lastNonce) await fetchState(true);

    const r = await fetch("/api/action/plant", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Action-Nonce": lastNonce },
      body: JSON.stringify({ idx, item_key: seedKey }),
      credentials: "same-origin",
    });
    const j = await r.json();

    if (!j.ok) {
      if (j.error === "bad_or_expired_nonce") await fetchState(true);
      else if (j.error === "no_seeds") showToast("Нет семян", "error");
      else if (j.error === "plot_busy") showToast("Клетка занята", "info");
      else if (j.error === "no_field_access") showToast("Клетка недоступна", "error");
      else if (j.error === "unknown_seed") showToast("Неизвестные семена", "error");
      return;
    }

    const prevPlots = state?.plots ? state.plots.slice() : null;

    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);
    if (!("plots" in state) && prevPlots) state.plots = prevPlots;

    renderHeader();
    updateTile(idx);
    
    // Определяем название культуры для уведомления
    const cropNames = {
      "seed_wheat": "пшеница",
      "seed_carrot": "морковь", 
      "seed_watermelon": "арбуз",
      "seed_pumpkin": "тыква",
      "seed_onion": "лук"
    };
    const cropName = cropNames[seedKey] || "культура";
    showToast(`Посажено: ${cropName}`, "success");
    closeModal();
  }

  // ===== Harvest
  async function harvestPlot(idx){
    if (isHarvesting) return;
    isHarvesting = true;

    if (!lastNonce) await fetchState(true);

    const r = await fetch("/api/action/harvest", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Action-Nonce": lastNonce },
      body: JSON.stringify({ idx }),
      credentials: "same-origin",
    });
    const j = await r.json();

    isHarvesting = false;

    if (!j.ok) {
      if (j.error === "bad_or_expired_nonce") await fetchState(true);
      else if (j.error === "not_ready") showToast("Ещё не готово", "info");
      else if (j.error === "nothing_to_harvest") showToast("Нечего собирать", "info");
      else showToast("Ошибка сбора", "error");
      return;
    }

    // сервер обновил nonce, баланс мог не меняться, но инвентарь — да
    state = j.state;
    lastNonce = state.action_nonce;
    applyServerTimeDelta(state);
    renderHeader();

    // визуально очищаем только эту клетку (сервер уже её очистил)
    const tile = grid.querySelector(`.tile[data-index="${idx}"]`);
    if (tile) {
      tile.className = "tile";
      tile.innerHTML = "";
    }

    showToast("Собрано: пшеница ×1", "success");
  }

  // ===== Listeners & start
  modalClose.addEventListener("click", closeModal);
  modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
  btnInventory.addEventListener("click", openInventoryModal);
  btnShop.addEventListener("click", openShopModal);

  closeModal();
  fetchState(true);
})();
