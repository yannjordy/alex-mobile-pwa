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
const msgInput = $('#msgInput') || $('#textInput');
const sendBtn = $('#sendBtn');
const stopBtn = $('#stopBtn');
const micBtn = $('#micBtn');
const emptyState = $('#emptyState');
const statusBar = $('#statusBar') || $('#statusOverlay');
const statusText = $('#statusText');
const statusDot = $('#statusDot');
const sidebar = $('#chatMenu');
const sidebarOverlay = $('#sidebarOverlay');
const settingsPanel = $('#settingsPanel');
const historyList = $('#cmList') || $('#historyList');
const mediaViewer = $('#mediaViewer');
const toast = $('#toast');
const quickActions = $('#quickActions');

document.addEventListener('DOMContentLoaded', init);

function init() {
  setupEventListeners();
  checkBackendStatus();
  loadSettings();
  registerServiceWorker();
  if (quickActions) setTimeout(() => quickActions.classList.remove('hidden'), 1000);
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
  if (msgInput) {
    msgInput.addEventListener('input', handleInput);
    msgInput.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  }
  if (sendBtn) sendBtn.addEventListener('click', sendMessage);
  if (stopBtn) stopBtn.addEventListener('click', stopAlex);
  if (micBtn) micBtn.addEventListener('click', toggleMic);

  document.querySelectorAll('.quick-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      const msg = btn.dataset.msg;
      if (msg && msgInput) {
        msgInput.value = msg;
        handleInput();
        sendMessage();
      }
    });
  });

  const menuBtn = $('#menuBtn');
  if (menuBtn) menuBtn.addEventListener('click', openSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);
  
  const closeSidebarBtn = $('#closeSidebar') || $('.cm-head button');
  if (closeSidebarBtn) closeSidebarBtn.addEventListener('click', closeSidebar);
  
  const newChatBtn = $('#newChatBtn') || $('#cmNewChat');
  if (newChatBtn) newChatBtn.addEventListener('click', newChat);
  
  const settingsBtn = $('#settingsBtn');
  if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
  
  const closeSettingsBtn = $('#closeSettings');
  if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);

  const cfgVoiceEnabled = $('#cfgVoiceEnabled');
  if (cfgVoiceEnabled) {
    cfgVoiceEnabled.addEventListener('change', (e) => {
      voiceEnabled = e.target.checked;
      localStorage.setItem(CONFIG.storageKeys.voiceEnabled, voiceEnabled);
    });
  }

  const btnClearHist = $('#btnClearHist') || $('#cmClearAll');
  if (btnClearHist) btnClearHist.addEventListener('click', clearHistory);

  // Install button
  let deferredPrompt;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    const installBtn = $('#installBtn');
    if (installBtn) installBtn.classList.remove('hidden');
  });
  
  const installBtn = $('#installBtn');
  if (installBtn) {
    installBtn.addEventListener('click', async () => {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') showToast('Alex installé !');
        deferredPrompt = null;
        installBtn.classList.add('hidden');
      }
    });
  }

  const mvClose = $('#mvClose');
  if (mvClose) mvClose.addEventListener('click', closeMediaViewer);
  if (mediaViewer) {
    mediaViewer.addEventListener('click', (e) => {
      if (e.target === mediaViewer) closeMediaViewer();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (mediaViewer && mediaViewer.style.display !== 'none') closeMediaViewer();
      else if (settingsPanel && settingsPanel.style.display !== 'none') closeSettings();
      else if (sidebar && sidebar.classList.contains('open')) closeSidebar();
    }
  });
}

function handleInput() {
  if (!msgInput) return;
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 100) + 'px';
  if (sendBtn) sendBtn.disabled = !msgInput.value.trim();
}

async function sendMessage() {
  const text = msgInput ? msgInput.value.trim() : '';
  if (!text || streaming) return;
  if (emptyState) emptyState.style.display = 'none';
  if (quickActions) quickActions.classList.add('hidden');
  addMsg('user', escapeHtml(text));
  if (msgInput) {
    msgInput.value = '';
    msgInput.style.height = 'auto';
  }
  if (sendBtn) sendBtn.disabled = true;
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

function scrollToBottom() {
  requestAnimationFrame(() => { if (chatArea) chatArea.scrollTop = chatArea.scrollHeight; });
}

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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
              thinking.innerHTML = '<div class="bubble"><div class="thinking-toggle" style="cursor:pointer;color:rgba(255,246,234,0.5);font-size:12px">🧠 Penser ▸</div><div class="thinking-content" style="display:none;margin-top:8px;padding:8px;background:rgba(255,255,255,0.03);border-radius:8px;font-size:13px;color:rgba(255,246,234,0.5)">' + escapeHtml(p.text) + '</div></div>';
              chatArea.appendChild(thinking);
              if (ld && ld.parentNode) ld.remove();
              thinking.querySelector('.thinking-toggle').addEventListener('click', function() {
                const content = this.nextElementSibling;
                content.style.display = content.style.display === 'none' ? 'block' : 'none';
                this.textContent = content.style.display === 'none' ? '🧠 Penser ▸' : '🧠 Penser ▾';
              });
            } else {
              const tc = thinking.querySelector('.thinking-content');
              if (tc) tc.textContent += p.text;
            }
            scrollToBottom();
            continue;
          }
          if (p.type === 'delta') {
            if (ld && ld.parentNode) ld.remove();
            if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
            full += p.text;
            bubble.querySelector('.bubble').innerHTML = renderMd(full);
            scrollToBottom();
            continue;
          }
          if (p.type === 'status') { showStatus(p.text || ''); continue; }
          if (p.type === 'tool' || p.type === 'cmd') {
            if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
            const chip = document.createElement('div');
            chip.className = 'tool-chip';
            chip.style.cssText = 'margin:8px 0;padding:8px 12px;background:rgba(255,157,61,0.05);border:1px solid rgba(255,157,61,0.15);border-radius:8px;font-size:12px';
            chip.innerHTML = '<div style="color:#ffc98c;margin-bottom:4px">' + (p.type === 'tool' ? '🔧' : '▶') + ' ' + escapeHtml(p.tool || p.command || '') + '</div><div style="color:rgba(255,246,234,0.6);white-space:pre-wrap;max-height:100px;overflow:auto">' + escapeHtml((p.result || p.output || '').slice(0, 500)) + '</div>';
            bubble.appendChild(chip);
            scrollToBottom();
            continue;
          }
          if (p.error) {
            if (bubble) bubble.querySelector('.bubble').innerHTML = '<span style="color:#ef5350">' + escapeHtml(p.error) + '</span>';
            else { ld.remove(); addMsg('alex', '<span style="color:#ef5350">❌ ' + escapeHtml(p.error) + '</span>'); }
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
    if (e.name !== 'AbortError') addMsg('alex', '<span style="color:#ef5350">❌ Serveur indisponible.</span>');
  } finally {
    streaming = false;
    abortCtrl = null;
    hideStatus();
    setStreaming(false);
  }
}

function stopAlex() {
  speechQueue = [];
  if (audioPlayer) { audioPlayer.onended = null; audioPlayer.onerror = null; }
  audioPlayer.pause(); audioPlayer.src = ''; queuePlaying = false;
  if (abortCtrl) { abortCtrl.abort(); abortCtrl = null; }
  streaming = false; hideStatus(); setStreaming(false);
}

function showStatus(text) {
  if (statusText) statusText.textContent = text;
  if (statusBar) statusBar.classList.remove('hidden');
}

function hideStatus() {
  if (statusBar) statusBar.classList.add('hidden');
}

function setStreaming(val) {
  streaming = val;
  if (stopBtn) stopBtn.classList.toggle('visible', val);
  if (sendBtn) sendBtn.classList.toggle('hidden', val);
  if (micBtn) micBtn.classList.toggle('hidden', val);
}

async function checkBackendStatus() {
  try {
    const res = await fetch(API + '/health', { signal: AbortSignal.timeout(5000) });
    const data = await res.json();
    if (statusDot) statusDot.className = 'status-dot ' + (data.online ? 'online' : '');
    const st = $('#cfgStatus');
    if (st) st.textContent = data.online ? 'Connecté' : 'Déconnecté';
  } catch {
    if (statusDot) statusDot.className = 'status-dot';
    const st = $('#cfgStatus');
    if (st) st.textContent = 'Indisponible';
  }
}
setInterval(checkBackendStatus, 30000);

// Sidebar
function openSidebar() {
  if (sidebar) sidebar.classList.add('open');
  if (sidebarOverlay) sidebarOverlay.classList.remove('hidden');
  loadHistory();
}

function closeSidebar() {
  if (sidebar) sidebar.classList.remove('open');
  if (sidebarOverlay) sidebarOverlay.classList.add('hidden');
}

function newChat() {
  if (chatArea) chatArea.innerHTML = '';
  cid = crypto.randomUUID();
  if (emptyState) { emptyState.style.display = ''; if (chatArea) chatArea.appendChild(emptyState); }
  if (quickActions) quickActions.classList.remove('hidden');
  closeSidebar();
}

async function loadHistory() {
  if (!historyList) return;
  try {
    const res = await fetch(API + '/history');
    const data = await res.json();
    const messages = data.messages || [];
    if (messages.length === 0) {
      historyList.innerHTML = '<div class="cm-empty">Aucune conversation</div>';
      return;
    }
    const conversations = buildConversations(messages);
    historyList.innerHTML = conversations.map((conv, i) =>
      '<div class="cm-item" data-i="' + i + '"><div class="cm-q">' + escapeHtml(conv.q) + '</div><div class="cm-a">' + escapeHtml(conv.a) + '</div></div>'
    ).join('');
    historyList.querySelectorAll('.cm-item').forEach(el => {
      el.addEventListener('click', () => { loadConversation(+el.dataset.i, conversations); closeSidebar(); });
    });
  } catch {
    historyList.innerHTML = '<div class="cm-empty">Erreur de chargement</div>';
  }
}

function buildConversations(messages) {
  const turns = []; let current = null;
  for (const m of messages) {
    if (m.role === 'user') {
      if (current) turns.push(current);
      current = { q: m.content, a: '', full: [m] };
    } else if (current) {
      current.full.push(m);
      current.a = m.content.slice(0, 140);
    }
  }
  if (current) turns.push(current);
  return turns.reverse().map(t => ({ q: t.q.slice(0, 90), a: t.a, full: t.full }));
}

function loadConversation(i, conversations) {
  const conv = conversations[i]; if (!conv) return;
  if (chatArea) chatArea.innerHTML = '';
  if (quickActions) quickActions.classList.add('hidden');
  for (const m of conv.full) addMsg(m.role === 'user' ? 'user' : 'alex', escapeHtml(m.content));
  scrollToBottom();
}

// Settings
function openSettings() {
  if (settingsPanel) settingsPanel.classList.remove('hidden');
  const cfgUrl = $('#cfgUrl');
  if (cfgUrl) cfgUrl.value = API;
  loadModels();
  loadVoices();
  loadMemory();
}

function closeSettings() {
  if (settingsPanel) settingsPanel.classList.add('hidden');
}

function loadSettings() {
  const cfgUrl = $('#cfgUrl');
  if (cfgUrl) cfgUrl.value = API;
  const cfgVoiceEnabled = $('#cfgVoiceEnabled');
  if (cfgVoiceEnabled) cfgVoiceEnabled.checked = voiceEnabled;
}

async function loadModels() {
  try {
    const res = await fetch(API + '/models');
    const data = await res.json();
    const sel = $('#cfgModelSel');
    if (sel) {
      sel.innerHTML = '';
      for (const m of (data.models || [])) {
        const opt = document.createElement('option');
        opt.value = m; opt.textContent = m;
        if (m === data.current) opt.selected = true;
        sel.appendChild(opt);
      }
    }
    const cfgModel = $('#cfgModel');
    if (cfgModel) cfgModel.textContent = data.current || '-';
    if (sel) {
      sel.addEventListener('change', async () => {
        await fetch(API + '/model', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: sel.value })
        });
        if (cfgModel) cfgModel.textContent = sel.value;
      });
    }
  } catch {}
}

async function loadVoices() {
  try {
    const res = await fetch(API + '/voices');
    const data = await res.json();
    const sel = $('#cfgVoice');
    if (sel) {
      sel.innerHTML = '';
      for (const v of (data.voices || [])) {
        const opt = document.createElement('option');
        opt.value = v.id; opt.textContent = v.name || v.id;
        if (v.id === currentVoice) opt.selected = true;
        sel.appendChild(opt);
      }
      sel.addEventListener('change', () => {
        currentVoice = sel.value;
        localStorage.setItem(CONFIG.storageKeys.voice, currentVoice);
      });
    }
  } catch {}
}

async function loadMemory() {
  try {
    const res = await fetch(API + '/memory');
    const data = await res.json();
    const cfgMem = $('#cfgMem');
    if (cfgMem) cfgMem.textContent = (data.level || 1) + ' · ' + (data.facts || 0) + ' faits';
  } catch {}
}

async function clearHistory() {
  if (!confirm('Effacer tout l\'historique ?')) return;
  await fetch(API + '/history', { method: 'DELETE' });
  location.reload();
}

// TTS
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
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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

// Microphone
async function toggleMic() {
  if (!micActive) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micActive = true;
      if (micBtn) micBtn.classList.add('active');
      showToast('Micro activé');
      stream.getTracks().forEach(t => t.addEventListener('ended', () => { micActive = false; if (micBtn) micBtn.classList.remove('active'); }));
    } catch { showToast('Accès micro refusé'); }
  } else {
    micActive = false;
    if (micBtn) micBtn.classList.remove('active');
  }
}

// Markdown
function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function renderMd(t) {
  if (!t) return '';
  let h = escapeHtml(t);
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (_, l, c) => '<pre style="background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;overflow-x:auto;font-size:13px;margin:8px 0"><code>' + c + '</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;font-size:13px">$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  h = h.replace(/(https?:\/\/[^\s<&]+)/g, '<a href="$1" target="_blank" rel="noopener" style="color:#ffc98c">$1</a>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

// Media Viewer
function openMediaViewer(url, type) {
  if (mediaViewer) {
    mediaViewer.style.display = 'flex';
    const content = $('#mvContent');
    if (content) {
      if (type === 'image') content.innerHTML = '<img src="' + url + '">';
      else content.innerHTML = '<video src="' + url + '" controls autoplay style="max-width:90%;max-height:90%"></video>';
    }
  }
}

function closeMediaViewer() {
  if (mediaViewer) mediaViewer.style.display = 'none';
  const content = $('#mvContent');
  if (content) content.innerHTML = '';
}

// Toast
function showToast(msg) {
  if (toast) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2500);
  }
}

// Service Worker
function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js', { scope: './' })
      .then(reg => console.log('SW registered:', reg.scope))
      .catch(err => console.log('SW registration failed:', err));
  }
}