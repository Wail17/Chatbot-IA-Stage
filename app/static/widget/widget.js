/**
 * Zwembad.eu AI Chatbot Widget
 *
 * Self-contained chat widget for integration on any website.
 * Pure vanilla JS — no external dependencies.
 *
 * Usage:
 *   <script src="https://chatbot-zwembad.railway.app/static/widget/widget.js"></script>
 */
(function () {
  'use strict';

  // ==========================================================================
  // CONFIGURATION
  // ==========================================================================
  const CONFIG = {
    apiBaseUrl: 'https://chatbot-zwembad.railway.app',
    language: 'nl',
    primaryColor: '#0066cc',
    primaryDark: '#0052a3',
    welcomeMessage:
      'Hallo! Ik ben je AI assistent voor zwembadvragen. Hoe kan ik je helpen? 🏊',
    sessionKey: 'zwembad_chat_session',
    maxStoredMessages: 10,
    requestTimeout: 15000,
  };

  // ==========================================================================
  // CSS INJECTION
  // ==========================================================================
  function injectCSS() {
    var style = document.createElement('style');
    style.setAttribute('data-zwembad-widget', 'true');
    style.textContent = `
/* ── Reset (scoped) ─────────────────────────────────────── */
#zwembad-chatbot,
#zwembad-chatbot * {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
    Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}

/* ── Bubble ─────────────────────────────────────────────── */
#zwembad-chat-bubble {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: ${CONFIG.primaryColor};
  color: #fff;
  border: none;
  cursor: pointer;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(0, 102, 204, 0.4);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}
#zwembad-chat-bubble:hover {
  transform: scale(1.08);
  box-shadow: 0 6px 24px rgba(0, 102, 204, 0.55);
}
#zwembad-chat-bubble:active { transform: scale(0.95); }
#zwembad-chat-bubble svg { width: 28px; height: 28px; fill: #fff; }
#zwembad-chat-bubble.zw-hidden { display: none; }

/* Notification dot */
#zwembad-chat-bubble .zw-notif {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #ff4444;
  border: 2px solid #fff;
  display: none;
}
#zwembad-chat-bubble .zw-notif.zw-active { display: block; }

/* ── Chat Window ────────────────────────────────────────── */
#zwembad-chat-window {
  position: fixed;
  bottom: 90px;
  right: 20px;
  width: 380px;
  height: 600px;
  max-height: calc(100vh - 110px);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.18);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  opacity: 0;
  transform: translateY(20px) scale(0.96);
  pointer-events: none;
  transition: opacity 0.3s ease, transform 0.3s ease;
}
#zwembad-chat-window.zw-open {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}

/* ── Header ─────────────────────────────────────────────── */
.zw-header {
  background: linear-gradient(135deg, ${CONFIG.primaryColor}, ${CONFIG.primaryDark});
  color: #fff;
  padding: 18px 20px;
  border-radius: 12px 12px 0 0;
  position: relative;
  flex-shrink: 0;
}
.zw-header-title {
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}
.zw-header-subtitle {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 4px;
}
.zw-close-btn {
  position: absolute;
  top: 14px;
  right: 14px;
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: #fff;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  line-height: 1;
}
.zw-close-btn:hover { background: rgba(255, 255, 255, 0.35); }

/* ── Messages area ──────────────────────────────────────── */
.zw-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f8f9fa;
  display: flex;
  flex-direction: column;
  gap: 4px;
  scroll-behavior: smooth;
}
.zw-messages::-webkit-scrollbar { width: 5px; }
.zw-messages::-webkit-scrollbar-track { background: transparent; }
.zw-messages::-webkit-scrollbar-thumb {
  background: #ccc;
  border-radius: 3px;
}

/* ── Message bubbles ────────────────────────────────────── */
.zw-msg {
  max-width: 78%;
  padding: 11px 16px;
  font-size: 14px;
  line-height: 1.5;
  word-wrap: break-word;
  animation: zw-fadeIn 0.25s ease;
}
.zw-msg-user {
  align-self: flex-end;
  background: ${CONFIG.primaryColor};
  color: #fff;
  border-radius: 18px 18px 4px 18px;
  box-shadow: 0 1px 4px rgba(0, 102, 204, 0.25);
  margin-bottom: 12px;
}
.zw-msg-bot {
  align-self: flex-start;
  background: #fff;
  color: #333;
  border-radius: 18px 18px 18px 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  margin-bottom: 4px;
}

/* ── Feedback buttons ───────────────────────────────────── */
.zw-feedback {
  align-self: flex-start;
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
  margin-left: 4px;
}
.zw-fb-btn {
  background: transparent;
  border: 1px solid #ddd;
  border-radius: 16px;
  padding: 3px 10px;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.15s, background 0.15s, border-color 0.15s;
  display: flex;
  align-items: center;
  gap: 3px;
  color: #888;
}
.zw-fb-btn:hover:not(:disabled) {
  transform: scale(1.1);
  border-color: ${CONFIG.primaryColor};
  color: #333;
}
.zw-fb-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.zw-fb-btn.zw-selected {
  background: ${CONFIG.primaryColor};
  color: #fff;
  border-color: ${CONFIG.primaryColor};
  opacity: 1;
}

/* ── Typing indicator ───────────────────────────────────── */
.zw-typing {
  align-self: flex-start;
  background: #fff;
  border-radius: 18px 18px 18px 4px;
  padding: 12px 20px;
  display: flex;
  gap: 5px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  margin-bottom: 12px;
}
.zw-typing-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #bbb;
  animation: zw-bounce 1.2s infinite ease-in-out;
}
.zw-typing-dot:nth-child(2) { animation-delay: 0.15s; }
.zw-typing-dot:nth-child(3) { animation-delay: 0.3s; }

/* ── Input area ─────────────────────────────────────────── */
.zw-input-area {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  flex-shrink: 0;
}
.zw-input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 24px;
  padding: 11px 20px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  color: #333;
  background: #fff;
}
.zw-input::placeholder { color: #aaa; }
.zw-input:focus { border-color: ${CONFIG.primaryColor}; }
.zw-send-btn {
  background: ${CONFIG.primaryColor};
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 10px 18px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s, transform 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.zw-send-btn:hover { background: ${CONFIG.primaryDark}; }
.zw-send-btn:active { transform: scale(0.95); }
.zw-send-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.zw-send-btn svg { width: 18px; height: 18px; fill: #fff; }

/* ── Powered by ─────────────────────────────────────────── */
.zw-powered {
  text-align: center;
  font-size: 10px;
  color: #bbb;
  padding: 4px 0 8px 0;
  background: #fff;
  flex-shrink: 0;
}

/* ── Animations ─────────────────────────────────────────── */
@keyframes zw-bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-6px); }
}
@keyframes zw-fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ── Mobile ─────────────────────────────────────────────── */
@media (max-width: 480px) {
  #zwembad-chat-bubble {
    bottom: 15px;
    right: 15px;
    width: 56px;
    height: 56px;
  }
  #zwembad-chat-window {
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: 100%;
    max-height: 100%;
    border-radius: 0;
  }
  #zwembad-chat-window.zw-open {
    transform: translateY(0) scale(1);
  }
  .zw-header { border-radius: 0; }
}
    `;
    document.head.appendChild(style);
  }

  // ==========================================================================
  // SVG ICONS
  // ==========================================================================
  var ICON_CHAT =
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H5.2L4 17.2V4h16v12z"/><path d="M7 9h10v2H7zm0-3h10v2H7zm0 6h7v2H7z"/></svg>';
  var ICON_SEND =
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>';
  var ICON_POOL =
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="#fff" d="M22 21c-1.11 0-1.73-.37-2.18-.64-.37-.22-.6-.36-1.15-.36-.56 0-.78.13-1.15.36-.46.27-1.07.64-2.18.64s-1.73-.37-2.18-.64c-.37-.22-.6-.36-1.15-.36-.56 0-.78.13-1.15.36-.46.27-1.08.64-2.19.64-1.11 0-1.73-.37-2.18-.64-.37-.23-.6-.36-1.15-.36s-.78.13-1.15.36c-.46.27-1.08.64-2.19.64v-2c.56 0 .78-.13 1.15-.36.46-.27 1.08-.64 2.19-.64s1.73.37 2.18.64c.37.23.59.36 1.15.36.56 0 .78-.13 1.15-.36.46-.27 1.08-.64 2.19-.64 1.11 0 1.73.37 2.18.64.37.22.6.36 1.15.36s.78-.13 1.15-.36c.45-.27 1.07-.64 2.18-.64s1.73.37 2.18.64c.37.23.59.36 1.15.36v2zM22 16.3c-1.11 0-1.73-.37-2.18-.64-.37-.22-.6-.36-1.15-.36-.56 0-.78.13-1.15.36-.46.27-1.08.64-2.19.64-1.11 0-1.73-.37-2.18-.64-.37-.22-.6-.36-1.15-.36-.56 0-.78.13-1.15.36-.45.27-1.07.64-2.18.64s-1.73-.37-2.18-.64c-.37-.22-.6-.36-1.15-.36s-.78.14-1.15.36c-.46.27-1.08.64-2.19.64v-2c.56 0 .78-.13 1.15-.36.46-.27 1.08-.64 2.19-.64s1.73.37 2.18.64c.37.22.6.36 1.15.36.56 0 .78-.13 1.15-.36.45-.27 1.07-.64 2.18-.64s1.73.37 2.18.64c.37.22.6.36 1.15.36s.78-.13 1.15-.36c.45-.27 1.07-.64 2.18-.64s1.73.37 2.18.64c.37.22.6.36 1.15.36v2zM22 12c-.56 0-.78-.13-1.15-.36C20.39 11.37 19.77 11 18.67 11s-1.73.37-2.18.64c-.37.22-.6.36-1.15.36s-.78-.13-1.15-.36c-.45-.27-1.07-.64-2.18-.64s-1.73.37-2.18.64c-.37.22-.6.36-1.15.36s-.78-.13-1.15-.36C7.06 11.37 6.44 11 5.34 11s-1.73.37-2.18.64c-.37.23-.6.36-1.15.36v-2c1.11 0 1.73-.37 2.18-.64.37-.22.6-.36 1.15-.36s.78.13 1.15.36c.46.27 1.08.64 2.19.64s1.73-.37 2.18-.64c.37-.22.6-.36 1.15-.36s.78.14 1.15.36c.45.27 1.07.64 2.18.64s1.73-.37 2.18-.64c.37-.23.59-.36 1.15-.36.56 0 .78.13 1.15.36.45.27 1.07.64 2.18.64v2z"/></svg>';

  // ==========================================================================
  // HTML INJECTION
  // ==========================================================================
  function injectHTML() {
    var container = document.createElement('div');
    container.id = 'zwembad-chatbot';
    container.innerHTML =
      '<button id="zwembad-chat-bubble" aria-label="Open chat">' +
        ICON_CHAT +
        '<span class="zw-notif"></span>' +
      '</button>' +
      '<div id="zwembad-chat-window" role="dialog" aria-label="Chat">' +
        '<div class="zw-header">' +
          '<div class="zw-header-title">' + ICON_POOL + ' Zwembad AI Assistent</div>' +
          '<div class="zw-header-subtitle">Stel je vraag over zwembaden en spa\'s</div>' +
          '<button class="zw-close-btn" aria-label="Sluit chat">&times;</button>' +
        '</div>' +
        '<div class="zw-messages" id="zw-messages"></div>' +
        '<div class="zw-input-area">' +
          '<input class="zw-input" id="zw-input" type="text" ' +
            'placeholder="Stel je vraag..." autocomplete="off" />' +
          '<button class="zw-send-btn" id="zw-send" aria-label="Verstuur">' +
            ICON_SEND +
          '</button>' +
        '</div>' +
        '<div class="zw-powered">Powered by Zwembad AI</div>' +
      '</div>';
    document.body.appendChild(container);
  }

  // ==========================================================================
  // STATE
  // ==========================================================================
  var isOpen = false;
  var isSending = false;
  var welcomeShown = false;
  var sessionId = null;

  // ==========================================================================
  // DOM HELPERS
  // ==========================================================================
  function $(id) { return document.getElementById(id); }

  function scrollToBottom() {
    var el = $('zw-messages');
    if (el) el.scrollTop = el.scrollHeight;
  }

  // ==========================================================================
  // TOGGLE CHAT
  // ==========================================================================
  function toggleChat() {
    isOpen = !isOpen;
    var win = $('zwembad-chat-window');
    var bubble = $('zwembad-chat-bubble');

    if (isOpen) {
      win.classList.add('zw-open');
      bubble.classList.add('zw-hidden');
      $('zw-input').focus();
      if (!welcomeShown) {
        showWelcomeMessage();
        welcomeShown = true;
      }
      scrollToBottom();
    } else {
      win.classList.remove('zw-open');
      bubble.classList.remove('zw-hidden');
    }
  }

  function closeChat() {
    if (!isOpen) return;
    isOpen = false;
    $('zwembad-chat-window').classList.remove('zw-open');
    $('zwembad-chat-bubble').classList.remove('zw-hidden');
  }

  // ==========================================================================
  // MESSAGE RENDERING
  // ==========================================================================
  function addUserMessage(text) {
    var el = document.createElement('div');
    el.className = 'zw-msg zw-msg-user';
    el.textContent = text;
    $('zw-messages').appendChild(el);
    scrollToBottom();
    saveToSession({ role: 'user', text: text });
  }

  function addBotMessage(text, conversationId) {
    var el = document.createElement('div');
    el.className = 'zw-msg zw-msg-bot';
    el.textContent = text;
    $('zw-messages').appendChild(el);

    if (conversationId) {
      addFeedbackButtons(conversationId);
    }

    scrollToBottom();
    saveToSession({ role: 'bot', text: text, conversationId: conversationId || null });
  }

  function addFeedbackButtons(conversationId) {
    var wrapper = document.createElement('div');
    wrapper.className = 'zw-feedback';

    var btnUp = document.createElement('button');
    btnUp.className = 'zw-fb-btn';
    btnUp.innerHTML = '&#x1F44D;';
    btnUp.setAttribute('aria-label', 'Positieve feedback');

    var btnDown = document.createElement('button');
    btnDown.className = 'zw-fb-btn';
    btnDown.innerHTML = '&#x1F44E;';
    btnDown.setAttribute('aria-label', 'Negatieve feedback');

    function disable(selected) {
      btnUp.disabled = true;
      btnDown.disabled = true;
      selected.classList.add('zw-selected');
    }

    btnUp.addEventListener('click', function () {
      disable(btnUp);
      sendFeedback(conversationId, true);
    });
    btnDown.addEventListener('click', function () {
      disable(btnDown);
      sendFeedback(conversationId, false);
    });

    wrapper.appendChild(btnUp);
    wrapper.appendChild(btnDown);
    $('zw-messages').appendChild(wrapper);
  }

  function addTypingIndicator() {
    removeTypingIndicator();
    var el = document.createElement('div');
    el.className = 'zw-typing';
    el.id = 'zw-typing';
    el.innerHTML =
      '<span class="zw-typing-dot"></span>' +
      '<span class="zw-typing-dot"></span>' +
      '<span class="zw-typing-dot"></span>';
    $('zw-messages').appendChild(el);
    scrollToBottom();
  }

  function removeTypingIndicator() {
    var el = $('zw-typing');
    if (el) el.remove();
  }

  function showWelcomeMessage() {
    var stored = loadSession();
    if (stored && stored.length > 0) return;
    addBotMessage(CONFIG.welcomeMessage, null);
  }

  // ==========================================================================
  // API CALLS
  // ==========================================================================
  function sendMessage(question) {
    if (isSending) return;
    isSending = true;
    setSendEnabled(false);
    addTypingIndicator();

    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, CONFIG.requestTimeout);

    var body = { question: question, language: CONFIG.language };
    if (sessionId) body.session_id = sessionId;

    fetch(CONFIG.apiBaseUrl + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .then(function (res) {
        clearTimeout(timeoutId);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        removeTypingIndicator();
        sessionId = data.session_id || sessionId;
        addBotMessage(data.answer, data.conversation_id);
      })
      .catch(function (err) {
        removeTypingIndicator();
        if (err.name === 'AbortError') {
          addBotMessage('Sorry, het duurde te lang. Probeer het opnieuw.', null);
        } else {
          addBotMessage('Sorry, er ging iets mis. Probeer het later opnieuw.', null);
        }
        console.error('[ZwembadChat]', err);
      })
      .finally(function () {
        isSending = false;
        setSendEnabled(true);
        $('zw-input').focus();
      });
  }

  function sendFeedback(conversationId, thumbsUp) {
    fetch(CONFIG.apiBaseUrl + '/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation_id: conversationId,
        thumbs_up: thumbsUp,
      }),
    }).catch(function (err) {
      console.error('[ZwembadChat] Feedback error:', err);
    });
  }

  // ==========================================================================
  // INPUT HANDLING
  // ==========================================================================
  function handleSend() {
    var input = $('zw-input');
    var text = (input.value || '').trim();
    if (!text || isSending) return;
    input.value = '';
    addUserMessage(text);
    sendMessage(text);
  }

  function setSendEnabled(enabled) {
    $('zw-send').disabled = !enabled;
  }

  // ==========================================================================
  // SESSION PERSISTENCE
  // ==========================================================================
  function saveToSession(message) {
    try {
      var data = JSON.parse(localStorage.getItem(CONFIG.sessionKey) || '[]');
      data.push(message);
      if (data.length > CONFIG.maxStoredMessages) {
        data = data.slice(data.length - CONFIG.maxStoredMessages);
      }
      localStorage.setItem(CONFIG.sessionKey, JSON.stringify(data));
    } catch (_) { /* storage unavailable */ }
  }

  function loadSession() {
    try {
      var data = JSON.parse(localStorage.getItem(CONFIG.sessionKey) || '[]');
      if (!Array.isArray(data) || data.length === 0) return [];

      welcomeShown = true;
      var msgs = $('zw-messages');
      data.forEach(function (m) {
        var el = document.createElement('div');
        if (m.role === 'user') {
          el.className = 'zw-msg zw-msg-user';
          el.textContent = m.text;
          msgs.appendChild(el);
        } else {
          el.className = 'zw-msg zw-msg-bot';
          el.textContent = m.text;
          msgs.appendChild(el);
        }
      });
      scrollToBottom();
      return data;
    } catch (_) {
      return [];
    }
  }

  // ==========================================================================
  // EVENT HANDLERS
  // ==========================================================================
  function setupEventHandlers() {
    $('zwembad-chat-bubble').addEventListener('click', toggleChat);

    $('zwembad-chat-window').querySelector('.zw-close-btn')
      .addEventListener('click', closeChat);

    $('zw-send').addEventListener('click', handleSend);

    $('zw-input').addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    });

    // Close on Escape
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && isOpen) closeChat();
    });
  }

  // ==========================================================================
  // INIT
  // ==========================================================================
  function init() {
    injectCSS();
    injectHTML();
    setupEventHandlers();
    loadSession();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
