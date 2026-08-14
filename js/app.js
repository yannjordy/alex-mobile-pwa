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

  const mvClose = $('#mvClose');
  if (mvClose) mvClose.addEventListener('click', closeMediaViewer);
  if (mediaViewer) {
    mediaViewer.addEventListener('click', (e) => {
      if (e.target === mediaViewer) closeMediaViewer();
    });
  }

  const mediaModalClose = $('#mediaModalClose');
  if (mediaModalClose) mediaModalClose.addEventListener('click', closeMediaModal);
  const mediaModal = $('#mediaModal');
  if (mediaModal) {
    mediaModal.addEventListener('click', (e) => {
      if (e.target === mediaModal) closeMediaModal();
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
          if (p.type === 'tool' || p.type === 'cmd' || p.type === 'tool_reply') {
            if (!bubble) { bubble = addMsg('alex', ''); bubble.querySelector('.bubble').innerHTML = ''; }
            const chip = document.createElement('div');
            chip.className = 'tool-chip';
            chip.style.cssText = 'margin:8px 0;padding:8px 12px;background:rgba(255,157,61,0.05);border:1px solid rgba(255,157,61,0.15);border-radius:8px;font-size:12px';
            const replyText = p.reply || p.result || p.output || '';
            chip.innerHTML = '<div style="color:#ffc98c;margin-bottom:4px">' + (p.type === 'tool' || p.type === 'tool_reply' ? '🔧' : '▶') + ' ' + escapeHtml(p.tool || p.command || '') + '</div><div style="color:rgba(255,246,234,0.6);white-space:pre-wrap;max-height:200px;overflow:auto">' + renderMediaContent(replyText) + '</div>';
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

// Markdown + Media rendering
function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

function renderMediaContent(text) {
  if (!text) return '';
  const URL_RE = /https?:\/\/[^\s<>]+/gi;
  const IMG_RE = /\.(jpe?g|png|gif|webp|bmp|svg|avif)(\?[^\s]*)?$/i;
  const VID_RE = /\.(mp4|webm|ogg|mov)(\?[^\s]*)?$/i;
  const AUD_RE = /\.(mp3|wav|ogg|flac|aac|m4a)(\?[^\s]*)?$/i;
  const embeds = [];

  const textWithMarkers = text.replace(URL_RE, (m) => {
    const idx = embeds.length;
    const lower = m.toLowerCase();
    if (IMG_RE.test(lower)) {
      embeds.push('<div style="margin:6px 0;cursor:pointer" onclick="openMediaViewer(\'' + escapeHtml(m) + '\',\'image\')"><img src="' + escapeHtml(m) + '" loading="lazy" style="max-width:100%;max-height:300px;border-radius:8px" onerror="this.style.display=\'none\'"></div>');
      try { addMedia('image', m); } catch(e) {}
    } else if (VID_RE.test(lower)) {
      embeds.push('<div style="margin:6px 0"><video src="' + escapeHtml(m) + '" controls loading="lazy" style="max-width:100%;max-height:300px;border-radius:8px"></video></div>');
      try { addMedia('video', m); } catch(e) {}
    } else if (AUD_RE.test(lower)) {
      embeds.push('<div style="margin:6px 0"><audio src="' + escapeHtml(m) + '" controls style="width:100%"></audio></div>');
      try { addMedia('audio', m); } catch(e) {}
    } else if (/youtube\.com\/watch\?v=|youtu\.be\//.test(lower)) {
      const idMatch = m.match(/[?&]v=([\w-]{11})|youtu\.be\/([\w-]{11})/);
      const ytId = idMatch ? (idMatch[1] || idMatch[2]) : null;
      if (ytId) {
        const embedUrl = 'https://www.youtube.com/embed/' + ytId + '?rel=0&modestbranding=1';
        embeds.push('<div style="margin:6px 0"><iframe src="' + embedUrl + '" frameborder="0" loading="lazy" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" allowfullscreen style="width:100%;aspect-ratio:16/9;border-radius:8px"></iframe></div>');
        try { addMedia('video', embedUrl, 'YouTube'); } catch(e) {}
      } else {
        embeds.push('<a href="' + escapeHtml(m) + '" target="_blank" rel="noopener" style="color:#ffc98c;font-size:13px">▶ Ouvrir sur YouTube</a>');
      }
    } else if (/dailymotion\.com\/video\//.test(lower)) {
      const idMatch = m.match(/dailymotion\.com\/video\/([a-zA-Z0-9]+)/);
      if (idMatch) {
        const embedUrl = 'https://www.dailymotion.com/embed/video/' + idMatch[1];
        embeds.push('<div style="margin:6px 0"><iframe src="' + embedUrl + '" frameborder="0" loading="lazy" allow="autoplay;fullscreen;picture-in-picture" allowfullscreen style="width:100%;aspect-ratio:16/9;border-radius:8px"></iframe></div>');
        try { addMedia('video', embedUrl, 'Dailymotion'); } catch(e) {}
      }
    } else {
      embeds.push('<a href="' + escapeHtml(m) + '" target="_blank" rel="noopener" style="color:#ffc98c;font-size:13px">🌐 Ouvrir</a>');
    }
    return '\x00EMBED' + idx + '\x00';
  });

  let html = escapeHtml(textWithMarkers);
  embeds.forEach((e, i) => { html = html.replace('\x00EMBED' + i + '\x00', e); });
  html = html.replace(/\n/g, '<br>');
  return html;
}

function renderMd(t) {
  if (!t) return '';
  // Render media URLs first (images, videos, audio)
  let h = renderMediaContent(t);
  // Then apply markdown
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (_, l, c) => '<pre style="background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;overflow-x:auto;font-size:13px;margin:8px 0"><code>' + c + '</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;font-size:13px">$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
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

// Media Modal data
const mediaData = { videos: [], images: [], pdfs: [], audio: [] };
const mediaIndex = { videos: 0, images: 0, pdfs: 0, audio: 0 };

function addMedia(type, url, title = '') {
  const tab = type === 'video' ? 'videos' : type === 'image' ? 'images' : type === 'pdf' ? 'pdfs' : 'audio';
  if (!mediaData[tab].find(m => m.url === url)) {
    mediaData[tab].push({ url, title });
    mediaIndex[tab] = mediaData[tab].length - 1;
  }
  openMediaModal(tab);
}

function openMediaModal(tab = 'images') {
  const modal = $('#mediaModal');
  if (modal) {
    modal.style.display = 'flex';
    modal.classList.add('open');
    renderMediaSlider(tab);
  }
}

function closeMediaModal() {
  const modal = $('#mediaModal');
  if (modal) {
    modal.classList.remove('open');
    modal.style.display = 'none';
  }
}

function renderMediaSlider(tab) {
  const slider = $('#' + tab.replace('s', '') + 'Slider') || $('#videoSlider');
  const counter = $('#' + tab.replace('s', '') + 'Counter') || $('#videoCounter');
  const items = mediaData[tab] || [];
  const idx = mediaIndex[tab] || 0;

  if (!slider) return;
  if (items.length === 0) {
    slider.innerHTML = '<div style="text-align:center;padding:40px;color:rgba(255,246,234,0.4)">Aucun ' + tab + '</div>';
    if (counter) counter.textContent = '0 / 0';
    return;
  }

  slider.innerHTML = items.map((item, i) => {
    let content = '';
    if (tab === 'images') {
      const imgUrl = escapeHtml(item.url);
      content = '<div class="media-image-wrap">' +
        '<img src="' + imgUrl + '" loading="lazy" style="max-width:100%;max-height:60vh;object-fit:contain;border-radius:8px;cursor:pointer" onclick="openMediaViewer(\'' + imgUrl + '\',\'image\')" onerror="this.style.display=\'none\'">' +
        '<div class="media-image-actions">' +
          '<button class="media-action-btn" onclick="event.stopPropagation();downloadMedia(\'' + imgUrl + '\',\'image\')" title="Enregistrer">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
            ' Enregistrer</button>' +
          '<button class="media-action-btn" onclick="event.stopPropagation();setWallpaper(\'' + imgUrl + '\')" title="Fond d\'écran">' +
            '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" stroke-width="2"/><circle cx="8.5" cy="8.5" r="1.5" fill="currentColor"/><path d="M3 16l5-5 4 4 3-3 6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>' +
            ' Fond écran</button>' +
        '</div>' +
      '</div>';
    } else if (tab === 'videos') {
      if (item.url.includes('youtube.com/embed') || item.url.includes('dailymotion.com/embed')) {
        content = '<iframe src="' + escapeHtml(item.url) + '" frameborder="0" allowfullscreen style="width:100%;aspect-ratio:16/9;border-radius:8px"></iframe>';
      } else {
        content = '<video src="' + escapeHtml(item.url) + '" controls style="max-width:100%;max-height:60vh;border-radius:8px"></video>';
      }
    } else if (tab === 'audio') {
      content = '<div style="text-align:center;padding:20px"><div style="font-size:48px;margin-bottom:12px">🎵</div><audio src="' + escapeHtml(item.url) + '" controls style="width:100%"></audio></div>';
    } else if (tab === 'pdfs') {
      content = '<iframe src="' + escapeHtml(item.url) + '" style="width:100%;height:60vh;border:none;border-radius:8px"></iframe>';
    }
    return '<div class="media-slide' + (i === idx ? ' active' : '') + '" data-index="' + i + '">' + content + '</div>';
  }).join('');

  if (counter) counter.textContent = (idx + 1) + ' / ' + items.length;

  // Nav buttons
  const prev = slider.parentElement?.querySelector('.media-prev');
  const next = slider.parentElement?.querySelector('.media-next');
  if (prev) prev.onclick = () => { mediaIndex[tab] = Math.max(0, idx - 1); renderMediaSlider(tab); };
  if (next) next.onclick = () => { mediaIndex[tab] = Math.min(items.length - 1, idx + 1); renderMediaSlider(tab); };
}

// Download media
window.downloadMedia = async function(url, type) {
  try {
    showToast('Téléchargement en cours...');
    const resp = await fetch(url);
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'alex-' + type + '-' + Date.now() + (url.includes('.png') ? '.png' : '.jpg');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    showToast('Image enregistrée !');
  } catch(e) {
    showToast('Erreur téléchargement');
    // Fallback: open in new tab
    window.open(url, '_blank');
  }
}

// Set wallpaper
window.setWallpaper = async function(url) {
  try {
    // Try to set as wallpaper via Electron API
    if (window.require) {
      const { ipcRenderer } = window.require('electron');
      ipcRenderer.send('set-wallpaper', url);
      showToast('Fond d\'écran appliqué !');
      return;
    }
    // Fallback: download and suggest
    showToast('Téléchargement pour fond d\'écran...');
    const resp = await fetch(url);
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'wallpaper-' + Date.now() + '.jpg';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    showToast('Image téléchargée. Appliquez-la comme fond d\'écran dans vos paramètres.');
  } catch(e) {
    showToast('Erreur fond d\'écran');
    window.open(url, '_blank');
  }
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