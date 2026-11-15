(() => {
  const $ = (id) => document.getElementById(id);
  const nav = [...document.querySelectorAll(".nav-item")];
  const views = {chat:"chatView",projects:"projectsView",tasks:"tasksView",memory:"memoryView"};
  const names = {chat:"Conversa",projects:"Projetos",tasks:"Tarefas",memory:"Memória"};
  const toast = (message) => {
    $("toast").textContent = message;
    $("toast").classList.add("show");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => $("toast").classList.remove("show"), 2600);
  };
  function switchView(name) {
    Object.values(views).forEach(id => $(id).classList.remove("active"));
    $(views[name]).classList.add("active");
    nav.forEach(item => item.classList.toggle("active", item.dataset.view === name));
    $("sectionName").textContent = names[name];
    $("sidebar").classList.remove("open");
  }
  nav.forEach(item => item.addEventListener("click", () => switchView(item.dataset.view)));
  $("openSidebar").addEventListener("click", () => $("sidebar").classList.add("open"));
  $("closeSidebar").addEventListener("click", () => $("sidebar").classList.remove("open"));
  function resetChat() {
    $("conversation").innerHTML = "";
    $("conversation").classList.remove("has-messages");
    $("welcome").style.display = "";
    $("messageInput").value = "";
    switchView("chat");
  }
  $("newChat").addEventListener("click", resetChat);
  $("recentConversation").addEventListener("click", resetChat);
  function submitMessage(value) {
    const message = value.trim();
    if (!message) return;
    $("welcome").style.display = "none";
    const area = $("conversation");
    area.classList.add("has-messages");
    const user = document.createElement("div");
    user.className = "message";
    user.textContent = message;
    area.appendChild(user);
    const note = document.createElement("div");
    note.className = "system-note";
    note.textContent = "Mensagem registrada somente nesta demonstração visual. O serviço MAX ainda não está conectado. Nenhuma resposta de IA foi gerada ou enviada ao núcleo SERMAX.";
    area.appendChild(note);
    $("messageInput").value = "";
    $("messageInput").style.height = "auto";
    area.scrollTop = area.scrollHeight;
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
  $("attachButton").addEventListener("click", () => toast("Anexos serão ativados após a integração segura com o backend."));
  $("newProject").addEventListener("click", () => toast("Projetos serão persistidos quando o backend estiver conectado."));
  $("modelSelect").addEventListener("change", event => toast("Seleção visual: " + event.target.value + ". Motor ainda não conectado."));
})();