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
        if (projectResponse.ok) activeProjectName = (await projectResponse.json()).name;\n        else activeProjectId = null;
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

  async function refreshProjects() {
    const list = $("projectList");
    if (!list) return;
    try {
      const response = await fetch("/api/projects");
      if (!response.ok) throw new Error("Falha ao consultar projetos.");
      const projects = await response.json();
      list.replaceChildren();
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
        open.addEventListener("click", () => {
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
        actions.append(open, edit, archive);
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
    if (name === null) return;
    const description = window.prompt("Descrição:", project.description || "");
    if (description === null) return;
    const instructions = window.prompt("Instruções:", project.instructions || "");
    if (instructions === null) return;
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
    } catch (error) { toast(error.message); }
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
  refreshHealth();
  refreshRecent();
  setInterval(refreshHealth, 15000);
})();