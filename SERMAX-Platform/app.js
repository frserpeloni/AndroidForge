(() => {
  const $ = id => document.getElementById(id);
  const nav = [...document.querySelectorAll(".nav-item")];
  const views = {chat:"chatView",projects:"projectsView",tasks:"tasksView",memory:"memoryView"};
  const names = {chat:"Conversa",projects:"Projetos",tasks:"Tarefas",memory:"Memória"};
  let conversationId = null;
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
    $("conversation").innerHTML = "";
    $("conversation").classList.remove("has-messages");
    $("welcome").style.display = "";
    $("messageInput").value = "";
    conversationId = null;
    switchView("chat");
  }
  $("newChat").addEventListener("click", resetChat);
  $("recentConversation").addEventListener("click", resetChat);
  function appendMessage(role, text) {
    $("welcome").style.display = "none";
    const area = $("conversation");
    area.classList.add("has-messages");
    const item = document.createElement("div");
    item.className = role === "user" ? "message" : "system-note";
    item.textContent = text;
    area.appendChild(item);
    area.scrollTop = area.scrollHeight;
  }
  async function submitMessage(value) {
    const message = value.trim();
    if (!message) return;
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
      if (!response.ok) throw new Error(data.detail || "Falha na solicitação.");
      conversationId = data.conversation_id;
      appendMessage("assistant", data.answer);
    } catch (error) {
      appendMessage("error", "Não foi possível obter resposta do MAX. " + error.message);
    } finally {
      $("sendButton").disabled = false;
      $("sendButton").textContent = "↑";
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
  $("modelSelect").addEventListener("change", () => toast("O roteamento do núcleo atual permanece automático. A seleção manual será integrada após validar os adaptadores."));
  refreshHealth();
  setInterval(refreshHealth, 15000);
})();