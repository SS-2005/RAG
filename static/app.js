// State management
const state = {
    provider: "ollama",
    baseUrl: "http://127.0.0.1:11434",
    model: "llama3",
    topK: 6,
    temperature: 0.1,
    documentLoaded: false,
    documentInfo: null
};

// DOM Elements
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const uploadView = document.getElementById("uploadView");
const chatView = document.getElementById("chatView");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const queryInput = document.getElementById("queryInput");
const sendBtn = document.getElementById("sendBtn");

const providerSelect = document.getElementById("providerSelect");
const baseUrlInput = document.getElementById("baseUrlInput");
const modelInput = document.getElementById("modelInput");
const modelDatalist = document.getElementById("modelDatalist");
const refreshModelsBtn = document.getElementById("refreshModelsBtn");
const connectionStatus = document.getElementById("connectionStatus");
const statusDot = connectionStatus.querySelector(".status-dot");
const statusText = connectionStatus.querySelector(".status-text");

const toggleAdvancedBtn = document.getElementById("toggleAdvancedBtn");
const advancedPanel = document.getElementById("advancedPanel");
const topKInput = document.getElementById("topKInput");
const topKVal = document.getElementById("topKVal");
const tempInput = document.getElementById("tempInput");
const tempVal = document.getElementById("tempVal");

const docCard = document.getElementById("docCard");
const docName = document.getElementById("docName");
const docStats = document.getElementById("docStats");
const resetDocBtn = document.getElementById("resetDocBtn");
const inspectChunksBtn = document.getElementById("inspectChunksBtn");

const chunksModal = document.getElementById("chunksModal");
const closeModalBtn = document.getElementById("closeModalBtn");
const modalChunksList = document.getElementById("modalChunksList");

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    checkConnection();
    checkExistingDocument();
});

function setupEventListeners() {
    // Provider changes
    providerSelect.addEventListener("change", (e) => {
        state.provider = e.target.value;
        if (state.provider === "ollama") {
            baseUrlInput.value = "http://127.0.0.1:11434";
            document.getElementById("urlGroup").style.display = "block";
            document.getElementById("modelGroup").style.display = "block";
        } else if (state.provider === "openai_compatible") {
            baseUrlInput.value = "http://127.0.0.1:1234/v1";
            document.getElementById("urlGroup").style.display = "block";
            document.getElementById("modelGroup").style.display = "block";
        } else if (state.provider === "offline") {
            document.getElementById("urlGroup").style.display = "none";
            document.getElementById("modelGroup").style.display = "none";
            statusDot.className = "status-dot online";
            statusText.innerText = "Offline Grounding Active";
            return;
        }
        state.baseUrl = baseUrlInput.value;
        checkConnection();
    });

    baseUrlInput.addEventListener("change", (e) => {
        state.baseUrl = e.target.value;
        checkConnection();
    });

    modelInput.addEventListener("change", (e) => {
        state.model = e.target.value;
    });

    refreshModelsBtn.addEventListener("click", () => {
        checkConnection(true);
    });

    // Sliders
    topKInput.addEventListener("input", (e) => {
        state.topK = parseInt(e.target.value);
        topKVal.innerText = state.topK;
    });

    tempInput.addEventListener("input", (e) => {
        state.temperature = parseFloat(e.target.value);
        tempVal.innerText = state.temperature;
    });

    toggleAdvancedBtn.addEventListener("click", () => {
        advancedPanel.classList.toggle("open");
    });

    // File Drag & Drop
    browseBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    ["dragenter", "dragover"].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach(name => {
        dropZone.addEventListener(name, (e) => {
            e.preventDefault();
            dropZone.classList.remove("drag-over");
        });
    });

    dropZone.addEventListener("drop", (e) => {
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    // Chat
    chatForm.addEventListener("submit", (e) => {
        e.preventDefault();
        submitQuery();
    });

    queryInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submitQuery();
        }
    });

    // Document Reset
    resetDocBtn.addEventListener("click", resetDocument);

    // Chunks Modal
    inspectChunksBtn.addEventListener("click", openChunksModal);
    closeModalBtn.addEventListener("click", () => chunksModal.style.display = "none");
    chunksModal.addEventListener("click", (e) => {
        if (e.target === chunksModal) chunksModal.style.display = "none";
    });
}

// Connection & Model Detection
async function checkConnection(alertOnFail = false) {
    if (state.provider === "offline") return;

    statusDot.className = "status-dot unknown";
    statusText.innerText = "Checking...";

    try {
        const res = await fetch(`/api/models?provider=${encodeURIComponent(state.provider)}&base_url=${encodeURIComponent(baseUrlInput.value)}`);
        const data = await res.json();

        if (data.online) {
            statusDot.className = "status-dot online";
            statusText.innerText = `Connected (${data.status_message})`;

            modelDatalist.innerHTML = "";
            if (data.models && data.models.length > 0) {
                data.models.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m;
                    modelDatalist.appendChild(opt);
                });
                if (!modelInput.value || !data.models.includes(modelInput.value)) {
                    modelInput.value = data.models[0];
                    state.model = data.models[0];
                }
            }
        } else {
            statusDot.className = "status-dot offline";
            statusText.innerText = "Server offline";
            if (alertOnFail) {
                alert(`Cannot connect to ${state.provider} at ${baseUrlInput.value}.\nPlease ensure your local LLM server (Ollama or LM Studio) is running.`);
            }
        }
    } catch (err) {
        statusDot.className = "status-dot offline";
        statusText.innerText = "Check failed";
    }
}

// Document Upload
async function handleFileUpload(file) {
    if (!file.name.toLowerCase().endsWith(".docx")) {
        alert("Invalid file type. Please upload a Microsoft Word .docx document.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    const originalText = browseBtn.innerText;
    browseBtn.innerText = "Indexing Document...";
    browseBtn.disabled = true;

    try {
        const res = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Upload failed");
        }

        displayDocumentActive(data.document);
    } catch (err) {
        alert(`Failed to upload: ${err.message}`);
    } finally {
        browseBtn.innerText = originalText;
        browseBtn.disabled = false;
    }
}

function displayDocumentActive(doc) {
    state.documentLoaded = true;
    state.documentInfo = doc;

    docName.innerText = doc.filename;
    docStats.innerText = `${doc.chunk_count} chunks • ${doc.word_count.toLocaleString()} words`;
    docCard.style.display = "block";

    uploadView.style.display = "none";
    chatView.style.display = "flex";
    queryInput.focus();
}

async function checkExistingDocument() {
    try {
        const res = await fetch("/api/document");
        const data = await res.json();
        if (data.loaded && data.document) {
            displayDocumentActive(data.document);
        }
    } catch (e) {}
}

async function resetDocument() {
    if (!confirm("Are you sure you want to remove the current document?")) return;

    try {
        await fetch("/api/reset", { method: "POST" });
        state.documentLoaded = false;
        state.documentInfo = null;

        docCard.style.display = "none";
        chatView.style.display = "none";
        uploadView.style.display = "flex";
        fileInput.value = "";

        // Reset chat messages
        chatMessages.innerHTML = `
            <div class="message assistant-msg system-banner">
                <div class="msg-bubble">
                    <p><strong>Document loaded successfully!</strong> Ask any question regarding the document contents. The model will strictly retrieve context chunks before generating answers.</p>
                </div>
            </div>
        `;
    } catch (e) {
        alert("Failed to reset document.");
    }
}

// Query Execution with Real-Time SSE Streaming
async function submitQuery() {
    const query = queryInput.value.trim();
    if (!query) return;

    appendMessage("user", query);
    queryInput.value = "";
    queryInput.disabled = true;
    sendBtn.disabled = true;

    // Create live streaming assistant bubble with blinking cursor
    const msgId = appendLiveMessage("assistant");

    try {
        const payload = {
            query: query,
            provider: state.provider,
            base_url: baseUrlInput.value,
            model: modelInput.value,
            top_k: state.topK,
            temperature: state.temperature
        };

        const res = await fetch("/api/query/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            let errorText = "Server error";
            try {
                const errData = await res.json();
                errorText = errData.detail || errorText;
            } catch (e) {}
            finalizeLiveMessage(msgId, `⚠️ **Error:** ${errorText}`);
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        let accumulatedText = "";
        let sources = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop(); // keep remainder

            for (const part of parts) {
                const lines = part.split("\n");
                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.type === "sources") {
                                sources = data.sources || [];
                                attachSourcesToMessage(msgId, sources);
                            } else if (data.type === "token") {
                                accumulatedText += data.token;
                                streamTokenToMessage(msgId, accumulatedText);
                            } else if (data.type === "error") {
                                accumulatedText += `⚠️ ${data.message}`;
                                streamTokenToMessage(msgId, accumulatedText);
                            } else if (data.type === "done") {
                                finalizeLiveMessage(msgId, accumulatedText, sources);
                            }
                        } catch (e) {}
                    }
                }
            }
        }

        finalizeLiveMessage(msgId, accumulatedText, sources);
    } catch (err) {
        finalizeLiveMessage(msgId, `⚠️ **Network Error:** Could not stream response. ${err.message}`);
    } finally {
        queryInput.disabled = false;
        sendBtn.disabled = false;
        queryInput.focus();
    }
}

function appendLiveMessage(role) {
    const msgId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 4);
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}-msg`;
    msgDiv.id = msgId;

    msgDiv.innerHTML = `
        <div class="msg-bubble">
            <span class="live-content"><span class="loading-dots">Searching & streaming answer...</span></span><span class="streaming-cursor"></span>
            <div class="sources-placeholder" id="sources-slot-${msgId}"></div>
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgId;
}

function streamTokenToMessage(msgId, fullText) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    const contentSpan = msgDiv.querySelector(".live-content");
    if (contentSpan) {
        contentSpan.innerHTML = formatMarkdown(fullText);
    }

    // Keep auto-scrolling
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function attachSourcesToMessage(msgId, sources) {
    if (!sources || sources.length === 0) return;
    const slot = document.getElementById(`sources-slot-${msgId}`);
    if (!slot) return;

    const sourceItems = sources.map(s => `
        <div class="source-item">
            <div class="source-meta">${s.section ? `[${escapeHtml(s.section)}] ` : ''}Chunk #${s.chunk_id} • Relevance: ${Math.round(s.score * 100)}%</div>
            <div>${escapeHtml(s.text.substring(0, 220))}${s.text.length > 220 ? "..." : ""}</div>
        </div>
    `).join("");

    slot.innerHTML = `
        <div class="sources-container">
            <button type="button" class="sources-toggle" onclick="toggleSources('${msgId}')">
                🔍 Retrieved ${sources.length} Context Chunks ▾
            </button>
            <div class="sources-list" id="sources-${msgId}" style="display: none;">
                ${sourceItems}
            </div>
        </div>
    `;
}

function finalizeLiveMessage(msgId, fullText, sources = null) {
    const msgDiv = document.getElementById(msgId);
    if (!msgDiv) return;

    const cursor = msgDiv.querySelector(".streaming-cursor");
    if (cursor) cursor.remove();

    const contentSpan = msgDiv.querySelector(".live-content");
    if (contentSpan) {
        contentSpan.innerHTML = formatMarkdown(fullText);
    }

    if (sources && sources.length > 0) {
        attachSourcesToMessage(msgId, sources);
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendMessage(role, text, isLoader = false, sources = null) {
    const msgId = "msg-" + Date.now() + "-" + Math.random().toString(36).substr(2, 4);
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}-msg`;
    msgDiv.id = msgId;

    let contentHtml = formatMarkdown(text);

    let sourcesHtml = "";
    if (sources && sources.length > 0) {
        const sourceItems = sources.map(s => `
            <div class="source-item">
                <div class="source-meta">${s.section ? `[${escapeHtml(s.section)}] ` : ''}Chunk #${s.chunk_id} • Relevance: ${Math.round(s.score * 100)}%</div>
                <div>${escapeHtml(s.text.substring(0, 220))}${s.text.length > 220 ? "..." : ""}</div>
            </div>
        `).join("");

        sourcesHtml = `
            <div class="sources-container">
                <button type="button" class="sources-toggle" onclick="toggleSources('${msgId}')">
                    🔍 Retrieved ${sources.length} Context Chunks ▾
                </button>
                <div class="sources-list" id="sources-${msgId}" style="display: none;">
                    ${sourceItems}
                </div>
            </div>
        `;
    }

    msgDiv.innerHTML = `
        <div class="msg-bubble">
            ${isLoader ? `<span class="loading-dots">⏳ ${escapeHtml(text)}</span>` : contentHtml}
            ${sourcesHtml}
        </div>
    `;

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return msgId;
}

function removeMessage(msgId) {
    const el = document.getElementById(msgId);
    if (el) el.remove();
}

window.toggleSources = function(msgId) {
    const list = document.getElementById(`sources-${msgId}`);
    if (list) {
        list.style.display = list.style.display === "none" ? "flex" : "none";
    }
};

function formatMarkdown(text) {
    if (!text) return "";
    let escaped = escapeHtml(text);
    // Simple inline formatting for bold, lists, code
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/`([^`]+)`/g, '<code style="background:#111827;padding:2px 5px;border-radius:4px;color:#a5b4fc;">$1</code>');
    escaped = escaped.replace(/\n\n/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
}

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Chunks Inspection Modal
async function openChunksModal() {
    try {
        const res = await fetch("/api/chunks");
        const data = await res.json();
        const chunks = data.chunks || [];

        modalChunksList.innerHTML = "";
        if (chunks.length === 0) {
            modalChunksList.innerHTML = "<p>No chunks found.</p>";
        } else {
            chunks.forEach(c => {
                const card = document.createElement("div");
                card.className = "chunk-card";
                card.innerHTML = `
                    <div class="chunk-header">
                        <span>Chunk #${c.chunk_id}</span>
                        <span>${c.word_count} words • characters ${c.start_char}-${c.end_char}</span>
                    </div>
                    <div class="chunk-text">${escapeHtml(c.text)}</div>
                `;
                modalChunksList.appendChild(card);
            });
        }
        chunksModal.style.display = "flex";
    } catch (e) {
        alert("Failed to load chunks.");
    }
}
