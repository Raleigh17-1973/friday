const messages = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");

const conversationId = `conv-${Math.random().toString(36).slice(2, 9)}`;
const projectId = "white board";
let sending = false;

function addMessage(role, text, meta = "") {
  const el = document.createElement("article");
  el.className = `message ${role}`;
  el.textContent = text;
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    el.appendChild(m);
  }
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(event) {
  event.preventDefault();
  if (sending) return;
  const text = input.value.trim();
  if (!text) return;

  addMessage("user", text);
  input.value = "";
  sending = true;
  sendBtn.disabled = true;

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        project_id: projectId,
        conversation_id: conversationId,
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const reply = data?.final_answer?.direct_answer ?? data?.response ?? "No response";
    const domains = data?.planner?.domains_involved?.join(", ") ?? data?.domain ?? "";
    addMessage("assistant", reply, domains ? `Domain: ${domains}` : "");
  } catch (error) {
    addMessage("assistant", "Request failed. Please try again.", "Error");
  } finally {
    sending = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", sendMessage);
