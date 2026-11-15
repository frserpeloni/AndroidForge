(() => {
  const $ = id => document.getElementById(id);
  const nav = [...document.querySelectorAll(".nav-item")];
  const views = {chat:"chatView",projects:"projectsView",tasks:"tasksView",memory:"memoryView"};
  const names = {chat:"Conversa",projects:"Projetos",tasks:"Tarefas",memory:"Memória"};
  let conversationId = null;
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

  function resetChat() {
    if (sending) return;
    $("conversation").replaceChildren();
    $("conversation").classList.remove("has-messages");
    $("welcome").style.display = "";
    $("messageInput").value = "";
    conversationId = null;
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
      $("conversation").replaceChildren();
      $("conversation").classList.remove("has-messages");
      $("welcome").style.display = "none";
      data.messages.forEach(message => appendMessage(message.role, message.content, message.status));
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
        body: JSON.stringify({message, conversation_id:conversationId})
      });
      const data = await response.json();
      if (!response.ok) {
        if (data.detail) throw new Error(data.detail);
        throw new Error("Falha na solicitação.");
      }
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
  $("newProject").addEventListener("click", () => toast("Projetos ainda não foram ativados no backend."));
  $("modelSelect").addEventListener("change", () => toast("O roteamento do núcleo atual permanece automático."));
  refreshHealth();
  refreshRecent();
  setInterval(refreshHealth, 15000);
})();