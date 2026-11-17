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

function setup() {
  const dom = new JSDOM(html, { url: "http://127.0.0.1:8765", runScripts: "outside-only" });
  const win = dom.window;
  const state = { projects: [], conversations: [], tasks: [], prompts: [], confirm: true, chatCalls: [] };
  let nextProject = 1;
  let nextConversation = 1;
  let nextTask = 1;

  win.setInterval = () => 1;
  win.clearInterval = () => {};
  win.prompt = message => state.prompts.shift() ?? null;
  win.confirm = () => state.confirm;
  win.fetch = async (url, options = {}) => {
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(options.body) : {};
    if (url === "/api/health") return response({ core: "mock" });
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
    if (url === "/api/chat" && method === "POST") {
      state.chatCalls.push(body);
      const id = body.conversation_id || String(nextConversation++);
      const conversation = { id, title: body.message, project_id: body.project_id || null, updated_at: new Date().toISOString() };
      state.conversations = [conversation, ...state.conversations.filter(c => c.id !== id)];
      return response({ conversation_id: id, answer: "Resposta simulada do MAX." });
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
