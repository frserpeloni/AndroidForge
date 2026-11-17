(() => {
  const $ = id => document.getElementById(id);
  const nav = [...document.querySelectorAll(".nav-item")];
  const views = {chat:"chatView",projects:"projectsView",tasks:"tasksView",memory:"memoryView"};
  const names = {chat:"Conversa",projects:"Projetos",tasks:"Tarefas",memory:"Memória"};
  let conversationId = null;
  let activeProjectId = null;
  let sending = false;

  const toast = message => {
    $("toast").textContent = message;
    $("toast").classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => $("toast").classList.remove("show"), 3000);
  };
  function switchView(name) {
    Object.values(views).forEach(id => $(id).classList.remove("active"));
    $(views[name]).classList.add("active");
    nav.forEach(item => item.classList.toggle("active", item.dataset.view === name));
    $("sectionName").textContent = names[name];
    $("sidebar").classList.remove("open");
    if (name === "projects") refreshProjects();
    if (name === "tasks") refreshTasks();
    if (name === "memory") refreshMemory();
  }
  async function refreshHealth() {
    try {
      const response = await fetch("/api/health");
      if (!response.ok) throw new Error("API indisponível");
      const data = await response.json();
      document.querySelectorAll(".connection").forEach(el => {
        el.innerHTML = '<span class="state-dot" style="background:#9be34b"></span> Serviço local online';
      });
      const state = document.querySelector(".service-state");
      if (state) state.innerHTML = '<span class="state-dot" style="background:#9be34b"></span><div><b>API local online</b><small>Núcleo: ' + data.core + '</small></div>';
    } catch {
      document.querySelectorAll(".connection").forEach(el => {
        el.innerHTML = '<span class="state-dot"></span> Serviço desconectado';
      });
    }
  }
  nav.forEach(item => item.addEventListener("click", () => switchView(item.dataset.view)));
  $("openSidebar").addEventListener("click", () => $("sidebar").classList.add("open"));
  $("closeSidebar").addEventListener("click", () => $("sidebar").classList.remove("open"));

  function updateProjectContext() {
    const label = $("activeProjectLabel");
    if (!label) return;
    label.textContent = activeProjectName ? "Projeto: " + activeProjectName : "";
    label.hidden = !activeProjectName;
  }
  let activeProjectName = "";
  function resetChat() {
    if (sending) return;
    $("conversation").replaceChildren();
    $("conversation").classList.remove("has-messages");
    $("welcome").style.display = "";
    $("messageInput").value = "";
    conversationId = null;
    updateProjectContext();
    switchView("chat");
  }
  $("newChat").addEventListener("click", resetChat);

  function appendMessage(role, text, status="complete") {
    $("welcome").style.display = "none";
    const area = $("conversation");
    area.classList.add("has-messages");
    const item = document.createElement("div");
    item.className = role === "user" ? "message" : (role === "error" ? "system-note error" : "system-note");
    item.textContent = text;
    if (status === "error") item.title = "Mensagem registrada, mas o núcleo não concluiu a solicitação.";
    area.appendChild(item);
    area.scrollTop = area.scrollHeight;
  }

  async function refreshRecent() {
    const list = $("recentList");
    try {
      const response = await fetch("/api/conversations");
      if (!response.ok) throw new Error("Histórico indisponível");
      const conversations = await response.json();
      list.replaceChildren();
      if (!conversations.length) {
        const empty = document.createElement("p");
        empty.className = "recent-item";
        empty.textContent = "Nenhuma conversa";
        list.appendChild(empty);
        return;
      }
      conversations.forEach(conversation => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "recent-item" + (conversation.id === conversationId ? " active" : "");
        const dot = document.createElement("span");
        dot.className = "recent-dot";
        const title = document.createElement("span");
        title.textContent = conversation.title || "Conversa";
        title.className = "recent-title";
        button.append(dot, title);
        button.title = conversation.title || "Abrir conversa";
        button.addEventListener("click", () => openConversation(conversation.id));
        list.appendChild(button);
      });
    } catch {
      list.textContent = "Histórico indisponível";
    }
  }

  async function openConversation(id) {
    if (sending) return;
    try {
      const response = await fetch("/api/conversations/" + encodeURIComponent(id));
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao abrir conversa.");
      conversationId = data.conversation.id;
      activeProjectId = data.conversation.project_id || null;
      activeProjectName = "";
      if (activeProjectId) {
        const projectResponse = await fetch("/api/projects/" + encodeURIComponent(activeProjectId));
        if (projectResponse.ok) activeProjectName = (await projectResponse.json()).name;
        else activeProjectName = "Projeto arquivado";
      }
      $("conversation").replaceChildren();
      $("conversation").classList.remove("has-messages");
      $("welcome").style.display = "none";
      data.messages.forEach(message => appendMessage(message.role, message.content, message.status));
      updateProjectContext();
      switchView("chat");
      await refreshRecent();
    } catch (error) {
      toast("Não foi possível abrir a conversa. " + error.message);
    }
  }

  async function submitMessage(value) {
    const message = value.trim();
    if (!message || sending) return;
    sending = true;
    appendMessage("user", message);
    $("messageInput").value = "";
    $("messageInput").style.height = "auto";
    $("sendButton").disabled = true;
    $("sendButton").textContent = "…";
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({message, conversation_id:conversationId, project_id:activeProjectId})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha na solicitação.");
      conversationId = data.conversation_id;
      appendMessage("assistant", data.answer);
    } catch (error) {
      appendMessage("error", "Não foi possível obter resposta do MAX. " + error.message, "error");
    } finally {
      sending = false;
      $("sendButton").disabled = false;
      $("sendButton").textContent = "↑";
      await refreshRecent();
    }
  }
  $("sendButton").addEventListener("click", () => submitMessage($("messageInput").value));
  $("messageInput").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage(event.currentTarget.value);
    }
  });
  $("messageInput").addEventListener("input", event => {
    event.currentTarget.style.height = "auto";
    event.currentTarget.style.height = Math.min(event.currentTarget.scrollHeight,180) + "px";
  });
  document.querySelectorAll(".quick-card").forEach(button => button.addEventListener("click", () => {
    switchView("chat");
    submitMessage(button.dataset.prompt);
  }));
  $("attachButton").addEventListener("click", () => toast("Anexos serão ativados após validação de segurança."));
  $("modelSelect").addEventListener("change", () => toast("O roteamento do núcleo atual permanece automático."));

  async function showProjectDetails(project) {
    const detail = $("projectDetail");
    const grid = $("projectList");
    detail.hidden = false;
    grid.hidden = true;
    detail.replaceChildren();
    const header = document.createElement("div");
    header.className = "project-detail-header";
    const back = document.createElement("button");
    back.className = "secondary-button";
    back.textContent = "← Voltar aos projetos";
    back.addEventListener("click", () => { detail.hidden = true; grid.hidden = false; });
    const heading = document.createElement("div");
    heading.className = "project-detail-heading";
    const title = document.createElement("h2");
    title.textContent = project.name;
    const description = document.createElement("p");
    description.textContent = project.description || "Sem descrição cadastrada.";
    const instructions = document.createElement("div");
    instructions.className = "project-instructions";
    const instructionsTitle = document.createElement("b");
    instructionsTitle.textContent = "Instruções do projeto";
    const instructionsText = document.createElement("p");
    instructionsText.textContent = project.instructions || "Nenhuma instrução específica cadastrada.";
    instructions.append(instructionsTitle, instructionsText);
    heading.append(title, description, instructions);
    header.append(back, heading);
    const actions = document.createElement("div");
    actions.className = "project-detail-actions";
    const activate = document.createElement("button");
    activate.className = "primary-button";
    activate.textContent = "Nova conversa neste projeto";
    activate.addEventListener("click", () => {
      activeProjectId = project.id;
      activeProjectName = project.name;
      conversationId = null;
      $("conversation").replaceChildren();
      $("conversation").classList.remove("has-messages");
      $("welcome").style.display = "";
      updateProjectContext();
      switchView("chat");
      toast("Projeto ativo. A próxima conversa será vinculada a ele.");
    });
    const edit = document.createElement("button");
    edit.className = "secondary-button";
    edit.textContent = "Editar projeto";
    edit.addEventListener("click", async () => {
      const updated = await editProject(project);
      if (!updated) return;
      try {
        await showProjectDetails({...project, ...(await fetchProject(project.id))});
      } catch (error) {
        toast(error.message);
      }
    });
    actions.append(activate, edit);
    const conversationSection = document.createElement("div");
    conversationSection.className = "project-conversation-section";
    const listTitle = document.createElement("h3");
    listTitle.textContent = "Conversas vinculadas";
    const list = document.createElement("div");
    list.className = "project-conversation-list";
    list.textContent = "Carregando conversas...";
    conversationSection.append(listTitle, list);
    detail.append(header, actions, conversationSection);
    try {
      const response = await fetch("/api/projects/" + encodeURIComponent(project.id) + "/conversations");
      const conversations = await response.json();
      if (!response.ok) throw new Error(conversations.detail || "Falha ao consultar conversas.");
      list.replaceChildren();
      if (!conversations.length) {
        const empty = document.createElement("p");
        empty.className = "project-empty";
        empty.textContent = "Este projeto ainda não possui conversas.";
        list.appendChild(empty);
      } else {
        conversations.forEach(conversation => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "project-conversation-item";
          const name = document.createElement("b");
          name.textContent = conversation.title || "Conversa";
          const date = document.createElement("small");
          date.textContent = new Date(conversation.updated_at).toLocaleString("pt-BR");
          item.append(name, date);
          item.addEventListener("click", () => openConversation(conversation.id));
          list.appendChild(item);
        });
      }
    } catch (error) {
      list.textContent = error.message;
    }
  }

  async function fetchProject(id) {
    const response = await fetch("/api/projects/" + encodeURIComponent(id));
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Falha ao consultar projeto.");
    return data;
  }

  async function refreshProjects() {
    const list = $("projectList");
    if (!list) return;
    try {
      const response = await fetch("/api/projects");
      if (!response.ok) throw new Error("Falha ao consultar projetos.");
      const projects = await response.json();
      list.replaceChildren();
      $("projectDetail").hidden = true;
      list.hidden = false;
      if (!projects.length) {
        const empty = document.createElement("div");
        empty.className = "empty-panel";
        empty.innerHTML = '<div class="empty-icon">▦</div><h2>Nenhum projeto cadastrado</h2><p>Crie um projeto para separar conversas e instruções.</p>';
        list.appendChild(empty);
        return;
      }
      projects.forEach(project => {
        const card = document.createElement("article");
        card.className = "project-card";
        const title = document.createElement("h2");
        title.textContent = project.name;
        const description = document.createElement("p");
        description.textContent = project.description || "Sem descrição";
        const meta = document.createElement("small");
        meta.textContent = project.instructions ? "Instruções configuradas" : "Sem instruções específicas";
        const actions = document.createElement("div");
        actions.className = "project-actions";
        const open = document.createElement("button");
        open.className = "primary-button";
        open.textContent = "Abrir projeto";
        open.addEventListener("click", () => showProjectDetails(project));
        const activate = document.createElement("button");
        activate.className = "secondary-button";
        activate.textContent = "Usar no MAX";
        activate.addEventListener("click", () => {
          activeProjectId = project.id;
          activeProjectName = project.name;
          conversationId = null;
          $("conversation").replaceChildren();
          $("conversation").classList.remove("has-messages");
          $("welcome").style.display = "";
          updateProjectContext();
          switchView("chat");
          toast("Projeto ativo. Novas conversas serão associadas a ele.");
        });
        const edit = document.createElement("button");
        edit.className = "secondary-button";
        edit.textContent = "Editar";
        edit.addEventListener("click", () => editProject(project));
        const archive = document.createElement("button");
        archive.className = "secondary-button";
        archive.textContent = "Arquivar";
        archive.addEventListener("click", () => archiveProject(project));
        actions.append(open, activate, edit, archive);
        card.append(title, description, meta, actions);
        list.appendChild(card);
      });
    } catch (error) {
      toast(error.message);
    }
  }

  async function createProject() {
    const name = window.prompt("Nome do projeto:");
    if (name === null) return;
    if (!name.trim()) return toast("Informe um nome para o projeto.");
    const description = window.prompt("Descrição do projeto (opcional):") || "";
    const instructions = window.prompt("Instruções específicas do projeto (opcional):") || "";
    try {
      const response = await fetch("/api/projects", {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name, description, instructions})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao criar projeto.");
      toast("Projeto salvo.");
      await refreshProjects();
    } catch (error) { toast(error.message); }
  }
  async function editProject(project) {
    const name = window.prompt("Nome do projeto:", project.name);
    if (name === null) return false;
    if (!name.trim()) { toast("Informe um nome para o projeto."); return false; }
    const description = window.prompt("Descrição:", project.description || "");
    if (description === null) return false;
    const instructions = window.prompt("Instruções:", project.instructions || "");
    if (instructions === null) return false;
    try {
      const response = await fetch("/api/projects/" + encodeURIComponent(project.id), {
        method:"PUT", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({name, description, instructions})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao atualizar projeto.");
      if (activeProjectId === project.id) { activeProjectName = data.name; updateProjectContext(); }
      toast("Projeto atualizado.");
      await refreshProjects();
      return true;
    } catch (error) { toast(error.message); return false; }
  }
  async function archiveProject(project) {
    if (!window.confirm('Arquivar "' + project.name + '"? As conversas serão preservadas.')) return;
    try {
      const response = await fetch("/api/projects/" + encodeURIComponent(project.id) + "/archive", {method:"POST"});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao arquivar projeto.");
      if (activeProjectId === project.id) { activeProjectId = null; activeProjectName = ""; conversationId = null; updateProjectContext(); }
      toast("Projeto arquivado. Conversas preservadas.");
      await refreshProjects();
    } catch (error) { toast(error.message); }
  }
  $("newProject").addEventListener("click", createProject);
  const taskStatusLabels = {
    pending: "Pendente",
    in_progress: "Em andamento",
    completed: "Concluída",
    cancelled: "Cancelada"
  };
  const taskPriorityLabels = {
    low: "Baixa",
    normal: "Normal",
    high: "Alta",
    urgent: "Urgente"
  };

  async function refreshTasks() {
    const list = $("taskList");
    if (!list) return;
    list.textContent = "Carregando tarefas...";
    try {
      const filter = $("taskStatusFilter").value;
      const url = filter ? "/api/tasks?status=" + encodeURIComponent(filter) : "/api/tasks";
      const response = await fetch(url);
      const tasks = await response.json();
      if (!response.ok) throw new Error(tasks.detail || "Falha ao consultar tarefas.");
      list.replaceChildren();
      if (!tasks.length) {
        const empty = document.createElement("p");
        empty.className = "task-empty";
        empty.textContent = "Nenhuma tarefa neste filtro.";
        list.appendChild(empty);
        return;
      }
      tasks.forEach(task => {
        const card = document.createElement("article");
        card.className = "task-card";
        const main = document.createElement("div");
        main.className = "task-main";
        const title = document.createElement("h2");
        title.textContent = task.title;
        const description = document.createElement("p");
        description.textContent = task.description || "Sem descrição.";
        const meta = document.createElement("div");
        meta.className = "task-meta";
        const priority = document.createElement("span");
        priority.className = "task-priority priority-" + task.priority;
        priority.textContent = "Prioridade: " + taskPriorityLabels[task.priority];
        const due = document.createElement("span");
        if (task.due_at) {
          const parsed = new Date(task.due_at);
          due.textContent = "Prazo: " + (Number.isNaN(parsed.getTime()) ? task.due_at : parsed.toLocaleString("pt-BR"));
        } else {
          due.textContent = "Sem prazo";
        }
        meta.append(priority, due);
        main.append(title, description, meta);
        const controls = document.createElement("div");
        controls.className = "task-controls";
        const status = document.createElement("select");
        status.className = "task-status";
        status.setAttribute("aria-label", "Estado da tarefa " + task.title);
        Object.entries(taskStatusLabels).forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          status.appendChild(option);
        });
        status.value = task.status;
        status.addEventListener("change", () => updateTaskStatus(task.id, status.value));
        controls.appendChild(status);
        card.append(main, controls);
        list.appendChild(card);
      });
    } catch (error) {
      list.textContent = error.message;
      toast(error.message);
    }
  }

  async function updateTaskStatus(taskId, status) {
    try {
      const response = await fetch("/api/tasks/" + encodeURIComponent(taskId) + "/status", {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({status})
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao atualizar tarefa.");
      toast("Estado da tarefa atualizado.");
      await refreshTasks();
    } catch (error) {
      toast(error.message);
      await refreshTasks();
    }
  }

  $("taskForm").addEventListener("submit", async event => {
    event.preventDefault();
    const title = $("taskTitle").value.trim();
    if (!title) return toast("Informe o título da tarefa.");
    const dueValue = $("taskDueAt").value;
    const payload = {
      title,
      description: $("taskDescription").value.trim(),
      priority: $("taskPriority").value,
      due_at: dueValue ? new Date(dueValue).toISOString() : null
    };
    try {
      const response = await fetch("/api/tasks", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao salvar tarefa.");
      $("taskForm").reset();
      $("taskStatusFilter").value = "";
      toast("Tarefa registrada.");
      await refreshTasks();
    } catch (error) {
      toast(error.message);
    }
  });
  $("taskStatusFilter").addEventListener("change", refreshTasks);

  async function refreshMemory() {
    const list = $("memoryList");
    const count = $("memoryCount");
    if (!list || !count) return;
    list.textContent = "Consultando memória carregada pelo núcleo...";
    count.textContent = "Consultando...";
    try {
      const query = $("memorySearch").value.trim();
      const params = new URLSearchParams({limit: "100"});
      if (query) params.set("q", query);
      const response = await fetch("/api/memory?" + params.toString(), {
        method: "GET",
        cache: "no-store"
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Falha ao consultar a memória.");
      list.replaceChildren();
      if (data.status === "core_not_loaded") {
        count.textContent = "Núcleo ainda não carregado";
        const empty = document.createElement("p");
        empty.className = "memory-empty";
        empty.textContent = data.message;
        list.appendChild(empty);
        return;
      }
      count.textContent = data.returned + " de " + data.total + " registros encontrados";
      if (!data.items.length) {
        const empty = document.createElement("p");
        empty.className = "memory-empty";
        empty.textContent = query ? "Nenhuma memória corresponde à busca." : "Não há registros pessoais disponíveis.";
        list.appendChild(empty);
        return;
      }
      data.items.forEach((memory, index) => {
        const card = document.createElement("article");
        card.className = "memory-card";
        const number = document.createElement("span");
        number.className = "memory-index";
        number.textContent = String(data.total - index).padStart(2, "0");
        const text = document.createElement("p");
        text.textContent = memory.content;
        card.append(number, text);
        list.appendChild(card);
      });
    } catch (error) {
      count.textContent = "Consulta indisponível";
      list.textContent = error.message;
      toast(error.message);
    }
  }

  $("refreshMemory").addEventListener("click", refreshMemory);
  $("memorySearch").addEventListener("keydown", event => {
    if (event.key === "Enter") {
      event.preventDefault();
      refreshMemory();
    }
  });

  refreshHealth();
  refreshRecent();
  setInterval(refreshHealth, 15000);
})();