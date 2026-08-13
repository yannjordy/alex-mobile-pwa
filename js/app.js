const CONFIG = {
  defaultUrl: location.origin,
  storageKeys: { api: 'alex_api', voice: 'alex_voice', voiceEnabled: 'alex_voice_enabled' }
};

let API = localStorage.getItem(CONFIG.storageKeys.api) || CONFIG.defaultUrl;
let currentVoice = localStorage.getItem(CONFIG.storageKeys.voice) || 'denise';
let voiceEnabled = localStorage.getItem(CONFIG.storageKeys.voiceEnabled) !== 'false';
let streaming = false, abortCtrl = null, cid = crypto.randomUUID();
let audioPlayer = new Audio(), speechQueue = [], queuePlaying = false, micActive = false;

const $ = (sel) => document.querySelector(sel);
const chatArea = $('#chatArea');
const msgInput = $('#msgInput');
const sendBtn = $('#sendBtn');
const stopBtn = $('#stopBtn');
const micBtn = $('#micBtn');
const emptyState = $('#emptyState');
const statusBar = $('#statusBar');
const statusText = $('#statusText');
const statusDot = $('#statusDot');
const sidebar = $('#sidebar');
const sidebarOverlay = $('#sidebarOverlay');
const settingsPanel = $('#settingsPanel');
const historyList = $('#historyList');
const mediaViewer = $('#mediaViewer');
const toast = $('#toast');
const quickActions = $('#quickActions');

document.addEventListener('DOMContentLoaded', init);

function init() {
  setupEventListeners();
  checkBackendStatus();
  loadSettings();
  registerServiceWorker();
  setTimeout(() => quickActions.classList.remove('hidden'), 1000);
  if (!localStorage.getItem(CONFIG.storageKeys.api)) promptForUrl();
}

function promptForUrl() {
  const url = prompt('URL du backend Alex (ex: http://192.168.1.10:8765):', API);
  if (url && url.trim()) {
    API = url.trim();
    localStorage.setItem(CONFIG.storageKeys.api, API);
    checkBackendStatus();
  }
}

function setupEventListeners() {
  msgInput.addEventListener('input', handleInput);
  msgInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  sendBtn.addEventListener('click', sendMessage);
  stopBtn.addEventListener('click', stopAlex);
  micBtn.addEventListener('click', toggleMic);
  document.querySelectorAll('.quick-pill').forEach(btn => {
    btn.addEventListener('click', () => { const msg = btn.dataset.msg; if (msg) { msgInput.value = msg; handleInput(); sendMessage(); } });
  });
  $('#menuBtn').addEventListener('click', openSidebar);
  sidebarOverlay.addEventListener('click', closeSidebar);
  $('#newChatBtn').addEventListener('click', newChat);
  $('#settingsBtn').addEventListener('click', openSettings);
  $('#closeSettings').addEventListener('click', closeSettings);
  $('#cfgUrl').addEventListener('change', saveUrl);
  $('#cfgVoiceEnabled').addEventListener('change', (e) => { voiceEnabled = e.target.checked; localStorage.setItem(CONFIG.storageKeys.voiceEnabled, voiceEnabled); });
  $('#btnClearHist').addEventListener('click', clearHistory);
  let deferredPrompt;
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredPrompt = e; $('#installBtn').classList.remove('hidden'); });
  $('#installBtn').addEventListener('click', async () => { if (deferredPrompt) { deferredPrompt.prompt(); const { outcome } = await deferredPrompt.userChoice; if (outcome === 'accepted') showToast('Alex installé !'); deferredPrompt = null; $('#installBtn').classList.add('hidden'); } });
  $('#mvClose').addEventListener('click', closeMediaViewer);
  mediaViewer.addEventListener('click', (e) => { if (e.target === mediaViewer) closeMediaViewer(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (!mediaViewer.classList.contains('hidden')) closeMediaViewer(); else if (!settingsPanel.classList.contains('hidden')) closeSettings(); else if (sidebar.classList.contains('open')) closeSidebar(); } });
}

function handleInput() {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 100) + 'px';
  sendBtn.disabled = !msgInput.value.trim();
}

async function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || streaming) return;
  if (emptyState) emptyState.style.display = 'none';
  quickActions.classList.add('hidden');
  addMsg('user', escapeHtml(text));
  msgInput.value = '';
  msgInput.style.height = 'auto';
  sendBtn.disabled = true;
  await handleAlexReply(text);
}

function addMsg(role, html, extra = '') {
  if (emptyState) emptyState.style.display = 'none';
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = '<div class="bubble">' + html + '</div>' + extra;
  chatArea.appendChild(div);
  scrollToBottom();
  return div;
}

function addLoading() {
  if (emptyState) emptyState.style.display = 'none';
  const div = document.createElement('div');
  div.className = 'msg alex';
  div.innerHTML = '<div class="bubble"><div class="loading-dots"><span></span><span></span><span></span></div></div>';
  chatArea.appendChild(div);
  scrollToBottom();
  return div;
}

function scrollToBottom() { requestAnimationFrame(() => { chatArea.scrollTop = chatArea.scrollHeight; }); }

async function handleAlexReply(text) {
  if (streaming) return;
  streaming = true;
  abortCtrl = new AbortController();
  showStatus('Alex réfléchit...');
  setStreaming(true);
  const ld = addLoading();
  let full = '', bubble = null, thinking = null;
  try {
    const res = await fetch(API + '/chat/opencode', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, mode: 'auto', cid }),
      signal: abortCtrl.signal
    });
    const reader = res.body.getReader(), decoder = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split('\n\n');
      buf = parts.pop() || '';
      for (const part of parts) {
        if (!part.startsWith('data: ')) continue;
        let payload = part.slice(6);
        if (payload === '[DONE]') break;
        try {
          const p = JSON.parse(payload);
          if (p.type === 'thinking') {
            if (!thinking) {
              thinking = document.createElement('div');
              thinking.className = 'msg alex';
              thinking.innerHTML = '<div class="bubble"><button class="thinking-toggle" onclick="this.nextElementSibling.classList.toggle(\'open\')">🧠 Penser</button><div class="thinking-content">' + escapeHtml(p.text) + '</div></div>';
              chatArea.appendChild(thinking);
              if (ld && ld.parentNode) ld.remove();
            } else {
              const tc = thinking.querySelector('.thinking-content');
              if (tc) tc.textContent += p.text;
            }
            scrollToBottom(); continue;
          }
          if (p.type === 'delta') {
            if (ld && ld.parentNode) ld.remove();
            if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
            full += p.text;
            bubble.querySelector('.bubble').innerHTML = renderMd(full);
            scrollToBottom(); continue;
          }
          if (p.type === 'status') { showStatus(p.text || ''); continue; }
          if (p.type === 'tool' || p.type === 'cmd') {
            if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
            const chip = document.createElement('div');
            chip.className = 'tool-chip';
            chip.innerHTML = '<div class="cmd">' + (p.type === 'tool' ? '🔧' : '▶') + ' ' + escapeHtml(p.tool || p.command || '') + '</div><div class="out">' + escapeHtml((p.result || p.output || '').slice(0, 500)) + '</div>';
            bubble.appendChild(chip); scrollToBottom(); continue;
          }
          if (p.error) {
            if (bubble) bubble.querySelector('.bubble').innerHTML = '<span class="error">' + escapeHtml(p.error) + '</span>';
            else { ld.remove(); addMsg('alex', '<span class="error">❌ ' + escapeHtml(p.error) + '</span>'); }
            break;
          }
        } catch (e) {
          if (ld && ld.parentNode) ld.remove();
          if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
          full += payload;
          bubble.querySelector('.bubble').innerHTML = renderMd(full);
          scrollToBottom();
        }
      }
    }
    if (bubble && full) bubble.querySelector('.bubble').innerHTML = renderMd(full);
    if (ld && ld.parentNode) ld.remove();
    if (full && voiceEnabled) speakText(stripMdForTTS(full));
  } catch (e) {
    if (ld && ld.parentNode) ld.remove();
    if (e.name !== 'AbortError') addMsg('alex', '<span class="error">❌ Serveur indisponible.</span>');
  } finally { streaming = false; abortCtrl = null; hideStatus(); setStreaming(false); }
}

function stopAlex() {
  speechQueue = [];
  if (audioPlayer) { audioPlayer.onended = null; audioPlayer.onerror = null; }
  audioPlayer.pause(); audioPlayer.src = ''; queuePlaying = false;
  if (abortCtrl) { abortCtrl.abort(); abortCtrl = null; }
  streaming = false; hideStatus(); setStreaming(false);
}

function showStatus(text) { statusText.textContent = text; statusBar.classList.remove('hidden'); }
function hideStatus() { statusBar.classList.add('hidden'); }
function setStreaming(val) { streaming = val; stopBtn.classList.toggle('hidden', !val); sendBtn.classList.toggle('hidden', val); micBtn.classList.toggle('hidden', val); }

async function checkBackendStatus() {
  try {
    const res = await fetch(API + '/health', { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    statusDot.className = data.online ? 'status-dot online' : 'status-dot offline';
    const st = $('#cfgStatus');
    if (st) st.textContent = data.online ? 'Connecté' : 'Déconnecté';
  } catch { statusDot.className = 'status-dot offline'; const st = $('#cfgStatus'); if (st) st.textContent = 'Indisponible'; }
}
setInterval(checkBackendStatus, 30000);

// ─── Sidebar ───
function openSidebar() { sidebar.classList.add('open'); sidebarOverlay.classList.remove('hidden'); loadHistory(); }
function closeSidebar() { sidebar.classList.remove('open'); sidebarOverlay.classList.add('hidden'); }
function newChat() { chatArea.innerHTML = ''; cid = crypto.randomUUID(); if (emptyState) { chatArea.appendChild(emptyState); emptyState.style.display = ''; } quickActions.classList.remove('hidden'); closeSidebar(); }

async function loadHistory() {
  try {
    const res = await fetch(API + '/history');
    const data = await res.json();
    const messages = data.messages || [];
    if (messages.length === 0) { historyList.innerHTML = '<div class="history-empty">Aucune conversation</div>'; return; }
    const conversations = buildConversations(messages);
    historyList.innerHTML = conversations.map((conv, i) => '<div class="history-item" data-i="' + i + '"><div class="q">' + escapeHtml(conv.q) + '</div><div class="a">' + escapeHtml(conv.a) + '</div></div>').join('');
    historyList.querySelectorAll('.history-item').forEach(el => {
      el.addEventListener('click', () => { loadConversation(+el.dataset.i, conversations); closeSidebar(); });
    });
  } catch { historyList.innerHTML = '<div class="history-empty">Erreur de chargement</div>'; }
}

function buildConversations(messages) {
  const turns = []; let current = null;
  for (const m of messages) {
    if (m.role === 'user') { if (current) turns.push(current); current = { q: m.content, a: '', full: [m] }; }
    else if (current) { current.full.push(m); current.a = m.content.slice(0, 140); }
  }
  if (current) turns.push(current);
  return turns.reverse().map(t => ({ q: t.q.slice(0, 90), a: t.a, full: t.full }));
}

function loadConversation(i, conversations) {
  const conv = conversations[i]; if (!conv) return;
  chatArea.innerHTML = ''; quickActions.classList.add('hidden');
  for (const m of conv.full) addMsg(m.role === 'user' ? 'user' : 'alex', escapeHtml(m.content));
  scrollToBottom();
}

// ─── Settings ───
function openSettings() { settingsPanel.classList.remove('hidden'); $('#cfgUrl').value = API; loadModels(); loadVoices(); loadMemory(); }
function closeSettings() { settingsPanel.classList.add('hidden'); }
function saveUrl() { const url = $('#cfgUrl').value.trim(); if (url) { API = url; localStorage.setItem(CONFIG.storageKeys.api, url); checkBackendStatus(); showToast('URL mise à jour'); } }
function loadSettings() { $('#cfgUrl').value = API; $('#cfgVoiceEnabled').checked = voiceEnabled; }

async function loadModels() {
  try {
    const res = await fetch(API + '/models'); const data = await res.json();
    const sel = $('#cfgModelSel'); sel.innerHTML = '';
    for (const m of (data.models || [])) { const opt = document.createElement('option'); opt.value = m; opt.textContent = m; if (m === data.current) opt.selected = true; sel.appendChild(opt); }
    $('#cfgModel').textContent = data.current || '-';
    sel.addEventListener('change', async () => { await fetch(API + '/model', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: sel.value }) }); $('#cfgModel').textContent = sel.value; });
  } catch {}
}

async function loadVoices() {
  try {
    const res = await fetch(API + '/voices'); const data = await res.json();
    const sel = $('#cfgVoice'); sel.innerHTML = '';
    for (const v of (data.voices || [])) { const opt = document.createElement('option'); opt.value = v.id; opt.textContent = v.name || v.id; if (v.id === currentVoice) opt.selected = true; sel.appendChild(opt); }
    sel.addEventListener('change', () => { currentVoice = sel.value; localStorage.setItem(CONFIG.storageKeys.voice, currentVoice); });
  } catch {}
}

async function loadMemory() {
  try { const res = await fetch(API + '/memory'); const data = await res.json(); $('#cfgMem').textContent = (data.level || 1) + ' · ' + (data.facts || 0) + ' faits'; } catch {}
}

async function clearHistory() {
  if (!confirm('Effacer tout ?')) return;
  await fetch(API + '/history', { method: 'DELETE' }); location.reload();
}

// ─── TTS ───
function stripMdForTTS(text) {
  text = text.replace(/```[\s\S]*?```/g, ' ');
  text = text.replace(/`([^`]+)`/g, '$1');
  text = text.replace(/\*+/g, '');
  text = text.replace(/[#_~|>]/g, '');
  try { text = text.replace(/\p{Extended_Pictographic}/gu, ' '); } catch (_) {}
  text = text.replace(/^[ \t]*[-*+•]\s+/gm, '');
  text = text.replace(/https?:\/\/[^\s]+/g, ' ');
  text = text.replace(/\n{3,}/g, '\n\n');
  return text.trim();
}

function fetchTTSBlob(text) {
  return fetch(API + '/vocal', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice: currentVoice })
  }).then(async res => {
    if (!res.ok) throw new Error('TTS ' + res.status);
    const reader = res.body.getReader(), chunks = [];
    while (true) { const { done, value } = await reader.read(); if (done) break; chunks.push(value); }
    return new Blob(chunks, { type: 'audio/mpeg' });
  });
}

function speakText(text) {
  if (!text.trim() || !voiceEnabled) return;
  speechQueue.push({ text });
  if (!queuePlaying) playNextInQueue();
}

function playNextInQueue() {
  if (speechQueue.length === 0) { queuePlaying = false; return; }
  queuePlaying = true;
  const item = speechQueue.shift();
  fetchTTSBlob(item.text).then(blob => {
    if (!blob) { playNextInQueue(); return; }
    if (audioPlayer) { audioPlayer.onended = null; audioPlayer.onerror = null; audioPlayer.pause(); audioPlayer.src = ''; }
    audioPlayer = new Audio(URL.createObjectURL(blob));
    const url = audioPlayer.src;
    const done = () => { URL.revokeObjectURL(url); playNextInQueue(); };
    audioPlayer.onended = done;
    audioPlayer.onerror = done;
    audioPlayer.play().catch(done);
  }).catch(playNextInQueue);
}

// ─── Microphone ───
async function toggleMic() {
  if (!micActive) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micActive = true;
      micBtn.classList.add('active');
      showToast('Micro activé');
      stream.getTracks().forEach(t => t.addEventListener('ended', () => { micActive = false; micBtn.classList.remove('active'); }));
    } catch { showToast('Accès micro refusé'); }
  } else {
    micActive = false;
    micBtn.classList.remove('active');
  }
}

// ─── Markdown ───
function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function renderMd(t) {
  if (!t) return '';
  let h = escapeHtml(t);
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (_, l, c) => '<pre><code>' + c + '</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  h = h.replace(/(https?:\/\/[^\s<&]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

// ─── Media Viewer ───
function openMediaViewer(url, type) {
  mediaViewer.classList.remove('hidden');
  if (type === 'image') mvContent.innerHTML = '<img src="' + url + '">';
  else mvContent.innerHTML = '<video src="' + url + '" controls autoplay></video>';
}
function closeMediaViewer() { mediaViewer.classList.add('hidden'); mvContent.innerHTML = ''; }

// ─── Toast ───
function showToast(msg) { toast.textContent = msg; toast.classList.add('show'); setTimeout(() => toast.classList.remove('show'), 2500); }

// ─── Service Worker ───
function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js', { scope: './' })
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  }
}