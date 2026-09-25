"use strict";

const form = document.getElementById("message-form");
const input = document.getElementById("message-input");
const messageList = document.getElementById("message-list");
const projectSelect = document.getElementById("project-select");
const conversationSelect = document.getElementById("conversation-select");
const modeSelect = document.getElementById("mode-select");
const status = document.getElementById("chat-status");
const sendButton = document.getElementById("send-button");
const newButton = document.getElementById("new-conversation");
let conversationId = null;
let busy = false;
let selectionVersion = 0;

async function api(url, options = {}) {
    const response = await fetch(url, {credentials: "same-origin", ...options});
    if (response.status === 401) {
        window.location.assign("/login/");
        throw new Error("Please sign in again.");
    }
    const data = await response.json();
    if (!response.ok) {
        throw new Error(typeof data.detail === "string" ? data.detail : "Request could not be completed. Check your access and project configuration.");
    }
    return data;
}

function addMessage(role, content) {
    const row = document.createElement("article");
    row.className = `message-row message-row-${role === "user" ? "user" : "ai"}`;
    const body = document.createElement("div");
    const label = document.createElement("span");
    label.className = "message-name";
    label.textContent = role === "user" ? "You" : "Nova";
    const paragraph = document.createElement("p");
    paragraph.className = `message-bubble ${role === "user" ? "user" : "ai"}-bubble`;
    // Model and user content are always text, never executable HTML/Markdown.
    paragraph.textContent = content;
    body.append(label, paragraph);
    row.append(body);
    messageList.append(row);
    messageList.scrollTop = messageList.scrollHeight;
}

function setBusy(value) {
    busy = value;
    sendButton.disabled = value || !projectSelect.value;
    projectSelect.disabled = value;
    conversationSelect.disabled = value;
    modeSelect.disabled = value;
    newButton.disabled = value;
}

function resetConversation() {
    conversationId = null;
    conversationSelect.value = "";
    messageList.replaceChildren();
    status.textContent = "New conversation. Project access rules apply to every request.";
}

async function loadConversations(version) {
    const data = await api(`/api/conversations/?project_id=${projectSelect.value}&limit=100`);
    if (version !== selectionVersion) return;
    conversationSelect.replaceChildren(new Option("New conversation", ""));
    for (const conversation of data.results) {
        conversationSelect.add(new Option(`Chat ${conversation.id} · ${new Date(conversation.updated_at).toLocaleString()}`, conversation.id));
    }
    conversationSelect.value = conversationId || "";
}

projectSelect.addEventListener("change", async () => {
    const version = ++selectionVersion;
    resetConversation();
    setBusy(true);
    try { await loadConversations(version); }
    catch (error) { status.textContent = error.message; }
    finally { setBusy(false); }
});

conversationSelect.addEventListener("change", async () => {
    const selected = conversationSelect.value;
    const version = ++selectionVersion;
    resetConversation();
    if (!selected) return;
    setBusy(true);
    try {
        let url = `/api/conversations/${selected}/messages/?limit=100`;
        const messages = [];
        while (url) {
            const data = await api(url);
            messages.push(...data.results);
            url = data.next;
        }
        if (version !== selectionVersion) return;
        conversationId = Number(selected);
        conversationSelect.value = selected;
        messages.forEach(message => addMessage(message.role, message.content));
        status.textContent = "Conversation loaded.";
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); }
});

newButton.addEventListener("click", resetConversation);
form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy || !projectSelect.value || !input.value.trim()) return;
    const text = input.value.trim();
    setBusy(true);
    status.textContent = "Preparing an answer…";
    try {
        const payload = {project_id: Number(projectSelect.value), message: text, mode: modeSelect.value};
        if (conversationId) payload.conversation_id = conversationId;
        const data = await api("/api/chat/", {
            method: "POST",
            headers: {"Content-Type": "application/json", "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value},
            body: JSON.stringify(payload),
        });
        messageList.querySelector(".empty-state")?.remove();
        addMessage("user", text);
        addMessage("assistant", data.reply);
        conversationId = data.conversation_id;
        input.value = "";
        input.style.height = "auto";
        status.textContent = `${data.provider} · ${data.model}${data.sources.length ? " · Sources: " + data.sources.join(", ") : ""}`;
        await loadConversations(selectionVersion);
    } catch (error) { status.textContent = error.message; }
    finally { setBusy(false); input.focus(); }
});

input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
});
input.addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); }
});

(async function initialize() {
    try {
        const projects = [];
        let url = "/api/projects/?limit=100";
        while (url) {
            const data = await api(url);
            projects.push(...data.results);
            url = data.next;
        }
        projectSelect.replaceChildren();
        for (const project of projects) projectSelect.add(new Option(project.name, project.id));
        if (!projects.length) {
            status.textContent = "No projects assigned. Contact your project administrator.";
            return;
        }
        projectSelect.disabled = false;
        sendButton.disabled = false;
        await loadConversations(selectionVersion);
    } catch (error) { status.textContent = error.message; }
})();
