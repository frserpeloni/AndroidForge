const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "app.js"), "utf8");

function response(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, json: async () => data };
}

function setup(url = "http://127.0.0.1:8765") {
  const dom = new JSDOM(html, { url, runScripts: "outside-only" });
  const win = dom.window;
  const state = { projects: [], conversations: [], tasks: [], memories: [], coreLoaded: false, memoryCalls: [], engineCalls: 0, prompts: [], confirm: true, chatCalls: [], pairings: [{reservation_id:"reserve-123456789012",device:"android-test",expires_at:1893456000}], pairingInvites: [], remoteSession: false, remoteApproved: false, remoteReserveCalls: [], remoteFinalizeCalls: [], remoteLogoutCalls: [] };
  let nextProject = 1;
  let nextConversation = 1;
  let nextTask = 1;

  win.TextDecoder = TextDecoder;
  win.setInterval = () => 1;
  win.clearInterval = () => {};
  win.prompt = message => state.prompts.shift() ?? null;
  win.confirm = () => state.confirm;
  win.fetch = async (url, options = {}) => {
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(options.body) : {};
    if (url === "/api/device/session" && method === "GET") {
      return state.remoteSession
        ? response({authenticated:true,device_id:"android-browser"})
        : response({detail:"Dispositivo não autenticado."},401);
    }
    if (url === "/api/device/logout" && method === "POST") {
      state.remoteLogoutCalls.push(true);
      state.remoteSession = false;
      return response({logged_out:true,device_id:"android-browser"});
    }
    if (url === "/api/device/pairing/reserve" && method === "POST") {
      state.remoteReserveCalls.push(body);
      return response({reservation_id:"remote-reservation-123",status:"awaiting_local_approval"},202);
    }
    if (url === "/api/device/pairing/finalize" && method === "POST") {
      state.remoteFinalizeCalls.push(body);
      if (!state.remoteApproved) return response({detail:"Pareamento ainda não aprovado."},403);
      state.remoteSession = true;
      return response({device_id:body.device_id,authenticated:true});
    }
    if (url === "/api/health") return response({ core: "mock" });
    if (url === "/api/local/pairings/pending" && method === "GET") return response({items:state.pairings});
    if (url === "/api/local/pairings" && method === "POST") {
      state.pairingInvites.push(body.device_id);
      return response({device_id:body.device_id,code:"ONE-TIME-TEST-CODE",expires_in:300},201);
    }
    const pairingApproveMatch = url.match(/^\/api\/local\/pairings\/([^/]+)\/approve$/);
    if (pairingApproveMatch && method === "POST") {
      const index = state.pairings.findIndex(item => item.reservation_id === decodeURIComponent(pairingApproveMatch[1]) && item.device === body.device_id);
      if (index < 0) return response({detail:"Pedido não encontrado"},404);
      state.pairings.splice(index,1);
      return response({approved:true,device_id:body.device_id});
    }
    if (url === "/api/conversations" && method === "GET") return response(state.conversations);
    if (url === "/api/projects" && method === "GET") return response(state.projects.filter(p => !p.archived));
    if (url === "/api/projects" && method === "POST") {
      const project = { id: String(nextProject++), ...body, archived: false };
      state.projects.push(project);
      return response(project, 201);
    }
    if (url === "/api/tasks" && method === "GET" || url.startsWith("/api/tasks?") && method === "GET") {
      const filter = new URL(url, win.location.href).searchParams.get("status");
      return response(state.tasks.filter(task => !filter || task.status === filter));
    }
    if (url === "/api/tasks" && method === "POST") {
      const task = {
        id: String(nextTask++),
        ...body,
        status: "pending",
        due_at: body.due_at || null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null
      };
      state.tasks.push(task);
      return response(task, 201);
    }
    const taskStatusMatch = url.match(/^\/api\/tasks\/([^/]+)\/status$/);
    if (taskStatusMatch && method === "PATCH") {
      const task = state.tasks.find(item => item.id === decodeURIComponent(taskStatusMatch[1]));
      if (!task) return response({ detail: "Tarefa não encontrada" }, 404);
      task.status = body.status;
      task.completed_at = body.status === "completed" ? new Date().toISOString() : null;
      return response(task);
    }
    if (url === "/api/engines/status" && method === "GET") {
      state.engineCalls += 1;
      return response({
        core_loaded: true,
        ollama: {reachable: true, models: ["sermax:latest"], detail: "API local respondeu."},
        ocr: {status: "ready", languages: ["eng", "por"], missing_languages: [], detail: "Tesseract pronto. Idiomas português e inglês encontrados."},
        openjarvis: {environment_files_present: true, detail: "Arquivos encontrados; execução ainda não testada."},
        last_route: {backend: "ollama", fallback: ""},
        read_only: true,
        inference_started: false
      });
    }
    if (url.startsWith("/api/memory") && method === "GET") {
      state.memoryCalls.push({url, cache: options.cache || ""});
      if (!state.coreLoaded) {
        return response({status:"core_not_loaded",read_only:true,total:0,returned:0,items:[],message:"Núcleo ainda não carregado."});
      }
      const params = new URL(url, win.location.href).searchParams;
      const query = (params.get("q") || "").toLocaleLowerCase();
      const items = state.memories.filter(item => item.content.toLocaleLowerCase().includes(query)).slice(-(Number(params.get("limit")) || 100)).reverse();
      return response({status:"available",read_only:true,total:items.length,returned:items.length,items,message:"Somente leitura."});
    }
    if (url === "/api/chat/stream" && method === "POST") {
      state.chatCalls.push(body);
      const id = body.conversation_id || String(nextConversation++);
      const conversation = { id, title: body.message, project_id: body.project_id || null, updated_at: new Date().toISOString() };
      state.conversations = [conversation, ...state.conversations.filter(c => c.id !== id)];
      const frames =
        "event: snapshot\ndata: " + JSON.stringify({text:"Resposta "}) + "\n\n" +
        "event: complete\ndata: " + JSON.stringify({conversation_id:id,answer:"Resposta simulada do MAX."}) + "\n\n";
      const bytes = new TextEncoder().encode(frames);
      let sent = false;
      return {
        ok:true,
        status:200,
        json:async()=>({conversation_id:id,answer:"Resposta simulada do MAX."}),
        body:{getReader:()=>({read:async()=>{
          if (sent) return {done:true};
          sent = true;
          return {done:false,value:bytes};
        }})}
      };
    }
    const projectMatch = url.match(/^\/api\/projects\/([^/]+)(?:\/(conversations|archive))?$/);
    if (projectMatch) {
      const [, id, action] = projectMatch;
      const project = state.projects.find(p => p.id === decodeURIComponent(id));
      if (!project) return response({ detail: "Projeto não encontrado" }, 404);
      if (action === "conversations" && method === "GET") return response(state.conversations.filter(c => c.project_id === project.id));
      if (action === "archive" && method === "POST") { project.archived = true; return response({ ok: true }); }
      if (!action && method === "GET") return project.archived ? response({ detail: "Projeto arquivado" }, 404) : response(project);
      if (!action && method === "PUT") { Object.assign(project, body); return response(project); }
    }
    const conversationMatch = url.match(/^\/api\/conversations\/([^/]+)$/);
    if (conversationMatch && method === "GET") {
      const conversation = state.conversations.find(c => c.id === decodeURIComponent(conversationMatch[1]));
      if (!conversation) return response({ detail: "Conversa não encontrada" }, 404);
      return response({ conversation, messages: [{ role: "user", content: conversation.title, status: "complete" }, { role: "assistant", content: "Resposta simulada", status: "complete" }] });
    }
    return response({ detail: "Rota simulada desconhecida: " + method + " " + url }, 404);
  };
  win.eval(script);
  const tick = async () => { for (let i = 0; i < 8; i++) await new Promise(resolve => win.setTimeout(resolve, 0)); };
  return { dom, win, state, tick };
}

test("cria tarefa e atualiza seu estado pela interface", async () => {
  const { win, state, tick } = setup();
  win.document.querySelector('[data-view="tasks"]').click();
  await tick();

  win.document.getElementById("taskTitle").value = "Validar integração do núcleo";
  win.document.getElementById("taskDescription").value = "Executar testes de contrato";
  win.document.getElementById("taskPriority").value = "high";
  win.document.getElementById("taskForm").dispatchEvent(
    new win.Event("submit", { bubbles: true, cancelable: true })
  );
  await tick();

  assert.equal(state.tasks.length, 1);
  assert.equal(state.tasks[0].title, "Validar integração do núcleo");
  assert.equal(state.tasks[0].priority, "high");
  assert.match(win.document.getElementById("taskList").textContent, /Validar integração do núcleo/);

  const status = win.document.querySelector(".task-status");
  status.value = "completed";
  status.dispatchEvent(new win.Event("change", { bubbles: true }));
  await tick();
  assert.equal(state.tasks[0].status, "completed");
});

test("painel de motores verifica serviços sem iniciar inferência", async () => {
  const { win, state, tick } = setup();
  win.document.querySelector('[data-view="engines"]').click();
  await tick();

  assert.equal(state.engineCalls, 1);
  assert.match(win.document.getElementById("engineStatus").textContent, /Ollama local/);
  assert.match(win.document.getElementById("engineStatus").textContent, /sermax:latest/);
  assert.match(win.document.getElementById("engineStatus").textContent, /OpenJarvis/);
  assert.match(win.document.getElementById("engineStatus").textContent, /OCR local/);
  assert.match(win.document.getElementById("engineStatus").textContent, /eng, por/);
  assert.match(win.document.getElementById("engineStatus").textContent, /Último backend registrado: ollama/);
  assert.match(win.document.querySelector(".engine-safety-note").textContent, /não envia prompts/i);
});

test("painel de memória consulta somente leitura e permite busca", async () => {
  const { win, state, tick } = setup();
  win.document.querySelector('[data-view="memory"]').click();
  await tick();

  assert.match(win.document.getElementById("memoryList").textContent, /Núcleo ainda não carregado/);
  assert.equal(state.memoryCalls.length, 1);
  assert.equal(state.memoryCalls[0].cache, "no-store");

  state.coreLoaded = true;
  state.memories = [
    {id: 0, content: "Meu carro é um Fiat Siena 2008."},
    {id: 1, content: "Prefiro respostas em português."}
  ];
  win.document.getElementById("memorySearch").value = "Fiat";
  win.document.getElementById("refreshMemory").click();
  await tick();

  assert.equal(state.memoryCalls.length, 2);
  assert.match(state.memoryCalls[1].url, /q=Fiat/);
  assert.match(win.document.getElementById("memoryList").textContent, /Fiat Siena 2008/);
  assert.doesNotMatch(win.document.getElementById("memoryList").textContent, /português/);
  assert.match(win.document.querySelector(".memory-protection-note").textContent, /somente leitura/i);
});

test("navegação entre telas mantém a tela selecionada", async () => {
  const { win, tick } = setup();
  win.document.querySelector('[data-view="projects"]').click();
  await tick();
  assert.equal(win.document.getElementById("projectsView").classList.contains("active"), true);
  win.document.querySelector('[data-view="memory"]').click();
  assert.equal(win.document.getElementById("memoryView").classList.contains("active"), true);
});

test("cria, edita e arquiva projeto preservando o registro", async () => {
  const { win, state, tick } = setup();
  win.document.getElementById("projectsView");
  win.document.querySelector('[data-view="projects"]').click();
  await tick();

  state.prompts.push("Projeto Alfa", "Descrição inicial", "Instruções iniciais");
  win.document.getElementById("newProject").click();
  await tick();
  assert.equal(state.projects.length, 1);
  assert.equal(state.projects[0].name, "Projeto Alfa");

  state.prompts.push("Projeto Beta", "Descrição revisada", "Instruções revisadas");
  [...win.document.querySelectorAll(".project-card button")].find(button => button.textContent === "Editar").click();
  await tick();
  assert.equal(state.projects[0].name, "Projeto Beta");
  assert.equal(state.projects[0].description, "Descrição revisada");

  win.document.querySelector(".project-card .secondary-button:last-child").click();
  await tick();
  assert.equal(state.projects[0].archived, true);
  assert.equal(state.projects.length, 1, "arquivar não apaga o registro");
});

test("cancelar edição mantém os dados e não simula atualização", async () => {
  const { win, state, tick } = setup();
  state.projects.push({ id: "1", name: "Projeto Original", description: "", instructions: "", archived: false });
  win.document.querySelector('[data-view="projects"]').click();
  await tick();
  state.prompts.push(null);
  [...win.document.querySelectorAll(".project-card button")].find(button => button.textContent === "Editar").click();
  await tick();
  assert.equal(state.projects[0].name, "Projeto Original");
});

test("nova conversa envia o projeto ativo e reabre o histórico", async () => {
  const { win, state, tick } = setup();
  state.projects.push({ id: "7", name: "Projeto Teste", description: "", instructions: "", archived: false });
  win.document.querySelector('[data-view="projects"]').click();
  await tick();
  [...win.document.querySelectorAll(".project-card button")].find(button => button.textContent === "Usar no MAX").click();
  await tick();
  win.document.getElementById("messageInput").value = "Verificar integração";
  win.document.getElementById("sendButton").click();
  await tick();
  assert.equal(state.chatCalls.length, 1);
  assert.equal(state.chatCalls[0].project_id, "7");
  assert.equal(state.chatCalls[0].message, "Verificar integração");
  assert.match(win.document.getElementById("conversation").textContent, /Resposta simulada do MAX/);

  const recent = win.document.querySelector("#recentList button");
  assert.ok(recent);
  recent.click();
  await tick();
  assert.match(win.document.getElementById("conversation").textContent, /Resposta simulada/);
  assert.equal(win.document.getElementById("activeProjectLabel").textContent, "Projeto: Projeto Teste");
});

test("conversa de projeto arquivado mantém o contexto e informa o estado", async () => {
  const { win, state, tick } = setup();
  state.projects.push({ id: "9", name: "Projeto Arquivado", description: "", instructions: "", archived: true });
  state.conversations.push({ id: "22", title: "Histórico antigo", project_id: "9", updated_at: new Date().toISOString() });
  await tick();
  const recent = win.document.querySelector("#recentList button");
  assert.ok(recent);
  recent.click();
  await tick();
  assert.equal(win.document.getElementById("activeProjectLabel").textContent, "Projeto: Projeto arquivado");
});


test("painel local gera convite e exige aprovação explícita do dispositivo", async () => {
  const { win, state, tick } = setup();
  win.document.querySelector('[data-view="devices"]').click();
  await tick();

  assert.match(win.document.getElementById("devicePendingList").textContent, /android-test/);
  assert.match(win.document.querySelector(".device-security-note").textContent, /permanece bloqueado/);

  win.document.getElementById("deviceInviteId").value = "android-novo";
  win.document.getElementById("deviceInviteForm").dispatchEvent(
    new win.Event("submit", { bubbles: true, cancelable: true })
  );
  await tick();
  assert.deepEqual(state.pairingInvites, ["android-novo"]);
  assert.match(win.document.getElementById("deviceInviteResult").textContent, /ONE-TIME-TEST-CODE/);

  const approve = win.document.querySelector(".device-pending-card button");
  assert.ok(approve);
  approve.click();
  await tick();
  assert.equal(state.pairings.length, 0);
  assert.match(win.document.getElementById("devicePendingList").textContent, /Nenhum pedido aguardando aprovação/);
});


test("cliente remoto exige pareamento e só libera a interface após aprovação local", async () => {
  const { win, state, tick } = setup("https://sermax.example.ts.net");
  await tick();
  assert.equal(win.document.body.classList.contains("remote-locked"), true);
  assert.equal(win.document.getElementById("remoteAuthGate").hidden, false);

  win.document.getElementById("remoteDeviceId").value = "android-browser";
  win.document.getElementById("remotePairingCode").value = "TEMP-CODE";
  win.document.getElementById("remotePairingForm").dispatchEvent(
    new win.Event("submit", { bubbles: true, cancelable: true })
  );
  await tick();
  assert.deepEqual(state.remoteReserveCalls, [{device_id:"android-browser",code:"TEMP-CODE"}]);
  assert.equal(win.document.getElementById("remoteFinalizeButton").disabled, false);
  assert.match(win.document.getElementById("remoteAuthStatus").textContent, /Aprove este dispositivo/);

  win.document.getElementById("remoteFinalizeButton").click();
  await tick();
  assert.match(win.document.getElementById("remoteAuthStatus").textContent, /ainda não aprovado/);
  assert.equal(win.document.body.classList.contains("remote-locked"), true);

  state.remoteApproved = true;
  win.document.getElementById("remoteFinalizeButton").click();
  await tick();
  assert.equal(state.remoteSession, true);
  assert.equal(win.document.body.classList.contains("remote-locked"), false);
  assert.equal(win.document.getElementById("remoteAuthGate").hidden, true);
  assert.equal(win.document.getElementById("remoteLogoutButton").hidden, false);

  win.document.getElementById("remoteLogoutButton").click();
  await tick();
  assert.deepEqual(state.remoteLogoutCalls, [true]);
  assert.equal(win.document.body.classList.contains("remote-locked"), true);
  assert.equal(win.document.getElementById("remoteAuthGate").hidden, false);
  assert.equal(win.document.getElementById("remoteLogoutButton").hidden, true);
});
