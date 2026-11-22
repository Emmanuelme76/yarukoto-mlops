const SUBCATEGORIES = {
  Escuela: [
    "Tarea / Ejercicios",
    "Proyecto / Código",
    "Estudio para examen",
    "Lectura / Resumen",
  ],
  Trabajo: [
    "Reunión",
    "Desarrollo / Técnico",
    "Documentación / Reporte",
    "Correo / Admin",
  ],
  Hogar: [
    "Limpieza",
    "Compras / Mandados",
    "Cocina",
    "Mantenimiento",
  ],
  Personal: [
    "Ejercicio",
    "Trámites / Finanzas",
    "Cita médica",
    "Ocio / Lectura",
  ],
};

let currentUser = localStorage.getItem("yarukoto_user") || "";
let activeTasks = [];
let timers = {}; // { taskId: { seconds: number, running: boolean, intervalId: number } }

// --- Inicialización ---
document.addEventListener("DOMContentLoaded", () => {
  initDueDateInput();
  onCategoryChange();
  checkApiHealth();

  document.getElementById("taskForm").addEventListener("submit", handleCreateTask);

  if (!currentUser) {
    openAuthModal(true);
  } else {
    updateUserHeaderUI();
    loadUserTasks();
  }
});

// --- Calendario y Cálculo de Días Restantes ---
function getLocalISODate(offsetDays = 0) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function initDueDateInput() {
  const dateInput = document.getElementById("fecha_entrega");
  dateInput.min = getLocalISODate(0);
  dateInput.value = getLocalISODate(2); // Por defecto +2 días
  updateDaysRemainingHint();
}

function getDaysUntilDueDate() {
  const dateStr = document.getElementById("fecha_entrega").value;
  if (!dateStr) return 0;

  const [y, m, d] = dateStr.split("-").map(Number);
  const target = new Date(y, m - 1, d);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  const diffMs = target - today;
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));
  return Math.max(0, diffDays);
}

function updateDaysRemainingHint() {
  const days = getDaysUntilDueDate();
  const hint = document.getElementById("daysRemainingHint");
  if (days === 0) {
    hint.textContent = "Entrega hoy";
  } else if (days === 1) {
    hint.textContent = "Entrega mañana (1 día)";
  } else {
    hint.textContent = `En ${days} días`;
  }
}

function onDueDateChange() {
  updateDaysRemainingHint();
  triggerLivePrediction();
}

// --- Estado de API y Modelo ---
async function checkApiHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    document.getElementById("modelSourceBadge").textContent = `Modelo activo: ${data.model_source}`;
  } catch (err) {
    document.getElementById("modelSourceBadge").textContent = "Error conectando con API";
  }
}

// --- Gestión de Perfiles y Sesión ---
function getSavedProfiles() {
  try {
    return JSON.parse(localStorage.getItem("yarukoto_profiles") || "[]");
  } catch {
    return [];
  }
}

function saveProfileRecord(username, role) {
  const profiles = getSavedProfiles();
  const existingIdx = profiles.findIndex((p) => p.username.toLowerCase() === username.toLowerCase());
  const record = {
    username,
    role: role || "Estudiante",
    lastUsed: new Date().toLocaleDateString("es-MX", { day: "2-digit", month: "short" }),
  };

  if (existingIdx >= 0) {
    profiles[existingIdx] = record;
  } else {
    profiles.unshift(record);
  }
  localStorage.setItem("yarukoto_profiles", JSON.stringify(profiles.slice(0, 6)));
}

function updateUserHeaderUI() {
  const profiles = getSavedProfiles();
  const profile = profiles.find((p) => p.username === currentUser);
  document.getElementById("currentUserLabel").textContent = currentUser;
  document.getElementById("currentUserRoleLabel").textContent = profile ? profile.role : "Perfil activo";
  document.getElementById("userAvatarBadge").textContent = currentUser.slice(0, 2).toUpperCase();
}

function openAuthModal(forceLogin = false) {
  const modal = document.getElementById("authModal");
  const closeBtn = document.getElementById("closeAuthModalBtn");
  closeBtn.style.display = forceLogin ? "none" : "block";

  renderSavedAccounts();
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function closeAuthModal() {
  if (!currentUser) return;
  const modal = document.getElementById("authModal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

function renderSavedAccounts() {
  const profiles = getSavedProfiles();
  const section = document.getElementById("savedAccountsSection");
  const list = document.getElementById("savedAccountsList");

  if (profiles.length === 0) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  list.innerHTML = "";

  profiles.forEach((prof) => {
    const isCurrent = prof.username === currentUser;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.onclick = () => switchAccount(prof.username, prof.role);
    btn.className = `w-full flex items-center justify-between p-3 rounded-xl border transition text-left ${
      isCurrent
        ? "bg-indigo-600/10 border-indigo-500/40"
        : "bg-slate-950 border-slate-800 hover:border-slate-700"
    }`;

    btn.innerHTML = `
      <div class="flex items-center gap-3">
        <div class="w-8 h-8 rounded-lg bg-slate-800 text-indigo-400 font-bold text-xs flex items-center justify-center uppercase">
          ${prof.username.slice(0, 2)}
        </div>
        <div>
          <p class="text-sm font-semibold text-white">${prof.username}</p>
          <p class="text-[11px] text-slate-400">${prof.role} · Último acceso: ${prof.lastUsed}</p>
        </div>
      </div>
      ${
        isCurrent
          ? `<span class="text-[11px] font-medium px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300">Activa</span>`
          : `<span class="text-xs text-slate-500">Entrar →</span>`
      }
    `;
    list.appendChild(btn);
  });
}

function switchAccount(username, role) {
  currentUser = username;
  localStorage.setItem("yarukoto_user", currentUser);
  saveProfileRecord(username, role);
  updateUserHeaderUI();
  closeAuthModal();
  loadUserTasks();
}

function handleAuthSubmit(e) {
  e.preventDefault();
  const username = document.getElementById("authUsernameInput").value.trim();
  const role = document.getElementById("authRoleInput").value;
  if (!username) return;

  document.getElementById("authUsernameInput").value = "";
  switchAccount(username, role);
}

// --- Subcategoría Híbrida ---
function onCategoryChange() {
  const cat = document.getElementById("categoria").value;
  const subSelect = document.getElementById("subcategoriaSelect");
  subSelect.innerHTML = "";

  SUBCATEGORIES[cat].forEach((sub) => {
    const opt = document.createElement("option");
    opt.value = sub;
    opt.textContent = sub;
    subSelect.appendChild(opt);
  });

  const customOpt = document.createElement("option");
  customOpt.value = "__custom__";
  customOpt.textContent = "+ Otra (personalizada)...";
  subSelect.appendChild(customOpt);

  onSubcategoryChange();
}

function onSubcategoryChange() {
  const subVal = document.getElementById("subcategoriaSelect").value;
  const wrapper = document.getElementById("customSubcatWrapper");
  if (subVal === "__custom__") {
    wrapper.classList.remove("hidden");
  } else {
    wrapper.classList.add("hidden");
  }
  triggerLivePrediction();
}

function getEffectiveSubcategory() {
  const subVal = document.getElementById("subcategoriaSelect").value;
  if (subVal === "__custom__") {
    const custom = document.getElementById("customSubcategoria").value.trim();
    return custom || "Personalizada";
  }
  return subVal;
}

// --- Construir Payload para ML ---
function buildFeaturePayload() {
  const now = new Date();
  const jsDay = now.getDay();
  const diaSemana = jsDay === 0 ? 6 : jsDay - 1;

  return {
    usuario: currentUser || "invitado",
    categoria: document.getElementById("categoria").value,
    subcategoria: getEffectiveSubcategory(),
    prioridad: parseInt(document.getElementById("prioridad").value, 10),
    complejidad: parseInt(document.getElementById("complejidad").value, 10),
    dia_semana: diaSemana,
    hora_creacion: now.getHours(),
    dias_para_entrega: getDaysUntilDueDate(),
    tareas_pendientes: activeTasks.length,
  };
}

// --- Predicción en Tiempo Real ---
async function triggerLivePrediction() {
  if (!currentUser) return;
  const payload = buildFeaturePayload();
  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return;
    const pred = await res.json();

    const pct = Math.round(pred.probabilidad_completar * 100);
    document.getElementById("liveProbText").textContent = `${pct}%`;
    document.getElementById("liveProbBar").style.width = `${pct}%`;
    document.getElementById("liveTimeText").textContent = `${pred.tiempo_estimado_min} min`;

    const badge = document.getElementById("liveRiskBadge");
    badge.textContent = pred.riesgo_abandono;

    if (pct >= 75) {
      badge.className = "text-xs font-medium px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
      document.getElementById("liveProbBar").className = "bg-emerald-500 h-full transition-all duration-300";
    } else if (pct >= 50) {
      badge.className = "text-xs font-medium px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20";
      document.getElementById("liveProbBar").className = "bg-amber-500 h-full transition-all duration-300";
    } else {
      badge.className = "text-xs font-medium px-2.5 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20";
      document.getElementById("liveProbBar").className = "bg-rose-500 h-full transition-all duration-300";
    }
  } catch (err) {
    console.error("Error en predicción en vivo:", err);
  }
}

// --- CRUD de Tareas ---
async function loadUserTasks() {
  if (!currentUser) return;
  try {
    const res = await fetch(`/api/tasks/${encodeURIComponent(currentUser)}`);
    activeTasks = await res.json();
    renderTasks();
    triggerLivePrediction();
  } catch (err) {
    console.error("Error cargando tareas:", err);
  }
}

async function handleCreateTask(e) {
  e.preventDefault();
  const titulo = document.getElementById("titulo").value.trim();
  if (!titulo) return;

  const payload = {
    titulo,
    ...buildFeaturePayload(),
  };

  try {
    const res = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      document.getElementById("titulo").value = "";
      document.getElementById("customSubcategoria").value = "";
      await loadUserTasks();
    }
  } catch (err) {
    console.error("Error creando tarea:", err);
  }
}

function formatDueDateBadge(days) {
  const target = new Date();
  target.setDate(target.getDate() + days);
  const formatted = target.toLocaleDateString("es-MX", { day: "2-digit", month: "short" });
  if (days === 0) return `Hoy (${formatted})`;
  if (days === 1) return `Mañana (${formatted})`;
  return `${formatted} (en ${days}d)`;
}

function renderTasks() {
  const container = document.getElementById("tasksListContainer");
  document.getElementById("pendingCountBadge").textContent = `${activeTasks.length} pendientes`;

  if (activeTasks.length === 0) {
    container.innerHTML = `
      <div class="bg-slate-900/60 border border-dashed border-slate-800 rounded-2xl p-10 text-center">
        <p class="text-slate-400 text-sm">No tienes tareas pendientes como <strong class="text-indigo-400">${currentUser}</strong>.</p>
        <p class="text-slate-500 text-xs mt-1">Crea una tarea en el panel izquierdo para ver su predicción ML.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = "";
  activeTasks.forEach((task) => {
    if (!timers[task.id]) {
      timers[task.id] = { seconds: 0, running: false, intervalId: null };
    }
    const pct = Math.round(task.probabilidad_completar * 100);
    const pillColor =
      pct >= 75
        ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
        : pct >= 50
        ? "text-amber-400 bg-amber-500/10 border-amber-500/20"
        : "text-rose-400 bg-rose-500/10 border-rose-500/20";

    const card = document.createElement("div");
    card.className = "bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 transition shadow-md flex flex-col sm:flex-row sm:items-center justify-between gap-4";
    card.innerHTML = `
      <div class="space-y-1.5">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs font-medium px-2.5 py-0.5 rounded-md bg-slate-800 text-slate-300">${task.categoria}</span>
          <span class="text-xs text-slate-400">${task.subcategoria}</span>
          <span class="text-[11px] px-2 py-0.5 rounded-full border ${pillColor}">${pct}% éxito</span>
        </div>
        <h3 class="text-base font-semibold text-white">${task.titulo}</h3>
        <div class="flex flex-wrap items-center gap-4 text-xs text-slate-400">
          <span>Estimado ML: <strong class="text-indigo-400">${task.tiempo_estimado_min} min</strong></span>
          <span>Complejidad: <strong class="text-slate-200">${task.complejidad}/5</strong></span>
          <span>Límite: <strong class="text-slate-200">${formatDueDateBadge(task.dias_para_entrega)}</strong></span>
        </div>
      </div>

      <div class="flex items-center gap-2.5 self-end sm:self-center">
        <!-- Cronómetro -->
        <div class="flex items-center gap-2 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-xl">
          <span id="timer-display-${task.id}" class="font-mono text-xs text-slate-300 w-12 text-center">
            ${formatSeconds(timers[task.id].seconds)}
          </span>
          <button onclick="toggleTimer('${task.id}')" id="timer-btn-${task.id}"
            class="text-xs font-medium px-2 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-indigo-400 transition">
            ${timers[task.id].running ? "Pausar" : "Iniciar"}
          </button>
        </div>

        <!-- Botón Completar / Cerrar -->
        <button onclick="openCompleteModal('${task.id}')"
          class="px-3.5 py-2 rounded-xl bg-emerald-600/20 hover:bg-emerald-600 text-emerald-400 hover:text-white border border-emerald-500/30 text-xs font-semibold transition cursor-pointer">
          Cerrar
        </button>

        <!-- Botón Eliminar Tarea Pendiente -->
        <button onclick="deletePendingTask('${task.id}')" title="Descartar tarea"
          class="px-2.5 py-2 rounded-xl bg-rose-500/10 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/20 text-xs font-semibold transition cursor-pointer">
          ✕
        </button>
      </div>
    `;
    container.appendChild(card);
  });
}

// --- Cronómetro por Tarea ---
function formatSeconds(totalSec) {
  const mins = Math.floor(totalSec / 60).toString().padStart(2, "0");
  const secs = (totalSec % 60).toString().padStart(2, "0");
  return `${mins}:${secs}`;
}

function toggleTimer(taskId) {
  const t = timers[taskId];
  if (!t) return;

  if (t.running) {
    clearInterval(t.intervalId);
    t.running = false;
  } else {
    t.running = true;
    t.intervalId = setInterval(() => {
      t.seconds += 1;
      const display = document.getElementById(`timer-display-${taskId}`);
      if (display) display.textContent = formatSeconds(t.seconds);
    }, 1000);
  }

  const btn = document.getElementById(`timer-btn-${taskId}`);
  if (btn) btn.textContent = t.running ? "Pausar" : "Iniciar";
}

// --- Modal de Cierre (Ground Truth) ---
function openCompleteModal(taskId) {
  const task = activeTasks.find((t) => t.id === taskId);
  if (!task) return;

  if (timers[taskId] && timers[taskId].running) {
    toggleTimer(taskId);
  }

  document.getElementById("completingTaskId").value = taskId;
  document.getElementById("completeModalTitle").textContent = task.titulo;

  const trackedMinutes = timers[taskId] ? Math.round(timers[taskId].seconds / 60) : 0;
  const suggestedMin = trackedMinutes >= 1 ? trackedMinutes : task.tiempo_estimado_min;
  document.getElementById("completeRealMinutes").value = suggestedMin;

  document.getElementById("completeTimerHint").textContent =
    trackedMinutes >= 1
      ? `Tiempo medido en cronómetro: ${trackedMinutes} min.`
      : `Sin cronómetro activo; sugerido según estimación ML (${task.tiempo_estimado_min} min).`;

  const modal = document.getElementById("completeModal");
  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

function closeCompleteModal() {
  const modal = document.getElementById("completeModal");
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

async function submitTaskCompletion() {
  const taskId = document.getElementById("completingTaskId").value;
  const completada = parseInt(document.getElementById("completeStatusSelect").value, 10);
  const tiempoRealMin = parseInt(document.getElementById("completeRealMinutes").value || "1", 10);

  try {
    const res = await fetch(`/api/tasks/${taskId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        completada,
        tiempo_real_min: tiempoRealMin,
      }),
    });

    if (res.ok) {
      delete timers[taskId];
      closeCompleteModal();
      await loadUserTasks();
    }
  } catch (err) {
    console.error("Error cerrando tarea:", err);
  }
}

async function deletePendingTask(taskId) {
  if (!confirm("¿Descartar esta tarea pendiente? (No se guardará en el dataset)")) return;
  try {
    const res = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
    if (res.ok) {
      if (timers[taskId] && timers[taskId].intervalId) {
        clearInterval(timers[taskId].intervalId);
      }
      delete timers[taskId];
      await loadUserTasks();
    }
  } catch (err) {
    console.error("Error eliminando tarea pendiente:", err);
  }
}

// --- Navegación de Pestañas ---
function switchTab(tabName) {
  ["tasks", "history", "monitoring"].forEach((name) => {
    document.getElementById(`view-${name}`).classList.add("hidden");
    const btn = document.getElementById(`tab-btn-${name}`);
    if (btn) {
      btn.className = "tab-btn px-4 py-1.5 rounded-lg text-sm font-medium text-slate-400 hover:text-white transition";
    }
  });

  document.getElementById(`view-${tabName}`).classList.remove("hidden");
  const activeBtn = document.getElementById(`tab-btn-${tabName}`);
  if (activeBtn) {
    activeBtn.className = "tab-btn px-4 py-1.5 rounded-lg text-sm font-medium bg-indigo-600 text-white transition";
  }

  if (tabName === "history") loadDatasetHistory();
  if (tabName === "monitoring") {
    document.getElementById("monitoringFrame").src = "/monitoring";
  }
}

async function loadDatasetHistory() {
  try {
    const res = await fetch("/api/dataset/history?limit=25");
    const data = await res.json();
    document.getElementById("datasetSourceText").textContent = `Fuente: ${data.source} (${data.total} registros totales)`;

    const tbody = document.getElementById("historyTableBody");
    tbody.innerHTML = "";

    data.records.forEach((row) => {
      const tr = document.createElement("tr");
      tr.className = "hover:bg-slate-800/40 transition";
      const statusBadge =
        row.completada === 1
          ? `<span class="px-2 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Completada</span>`
          : `<span class="px-2 py-0.5 rounded-full text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20">Abandonada</span>`;

      // Botón condicional: solo se habilita si estamos viendo new_tasks.csv (can_delete === true)
      const deleteButton = data.can_delete
        ? `<button onclick="deleteHistoryRecord(${row.row_index})" 
             title="Eliminar registro"
             class="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-600 text-rose-400 hover:text-white border border-rose-500/20 text-xs font-medium transition cursor-pointer">
             Eliminar
           </button>`
        : `<span class="text-xs text-slate-600">Protegido</span>`;

      tr.innerHTML = `
        <td class="py-3 px-4 font-medium text-white">${row.usuario}</td>
        <td class="py-3 px-4">${row.categoria}</td>
        <td class="py-3 px-4 text-slate-400">${row.subcategoria}</td>
        <td class="py-3 px-4">${row.prioridad}</td>
        <td class="py-3 px-4">${row.complejidad}/5</td>
        <td class="py-3 px-4">${statusBadge}</td>
        <td class="py-3 px-4 font-mono text-indigo-400">${row.tiempo_real_min} min</td>
        <td class="py-3 px-4 text-right">${deleteButton}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error cargando historial:", err);
  }
}

async function deleteHistoryRecord(rowIndex) {
  if (!confirm("¿Eliminar este registro del historial de entrenamiento?")) return;
  try {
    const res = await fetch(`/api/dataset/history/${rowIndex}`, { method: "DELETE" });
    if (res.ok) {
      await loadDatasetHistory();
    }
  } catch (err) {
    console.error("Error eliminando registro:", err);
  }
}