import { PipecatClient, RTVIEvent } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import { Clerk } from '@clerk/clerk-js';
import { ui } from '@clerk/ui';
import './style.css';

document.querySelector('#app').innerHTML = `
  <div class="shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark" aria-hidden="true">H</span><span>HARBOR <small>SUPPORT</small></span></div>
      <div id="userButton" class="user-button"></div>
    </header>
    <section id="authPanel" class="auth-panel" aria-label="Sign in"></section>
    <main id="mainContent" hidden>
      <div class="eyebrow"><span>HARBOR SUPPORT</span><span>YOUR ACTIVITY AND GUIDANCE</span></div>
      <div class="content">
        <section class="intro">
          <p class="overline">A clearer way forward</p>
          <h1>Start with<br/><em>a conversation.</em></h1>
          <p class="lead">Ask about your recent activity or public banking guidance.</p>
          <div class="notice"><span class="notice-icon" aria-hidden="true">i</span><p>This demonstration shows sample activity linked to your sign-in. It is not connected to a bank account. Live speech is sent to the configured voice provider. Please do not share passwords, card details, or one-time codes.</p></div>
          <div class="activity"><h2>Recent activity</h2><div id="activityList" class="activity-list">Loading activity…</div></div>
        </section>
        <section class="call-panel" aria-label="Voice session">
          <div class="panel-top"><span>LIVE SESSION</span><span id="statusBadge" class="status-badge">OFFLINE</span></div>
          <div id="voiceSymbol" class="voice-symbol" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>
          <div class="panel-copy"><p class="panel-label">CURRENT STATUS</p><h2 id="callStatus">Ready when you are</h2><p id="callHint">Connect your microphone to begin.</p></div>
          <div class="controls"><button id="connectButton" class="connect-button" type="button">Start conversation <span aria-hidden="true">↗</span></button><button id="muteButton" class="mute-button" type="button" disabled aria-label="Mute microphone">Mic on</button></div>
          <p id="errorMessage" class="error-message" role="alert" hidden></p>
          <div class="panel-footer"><span>Interrupt whenever you need to</span><span id="elapsed">00:00</span></div>
        </section>
      </div>
    </main>
    <footer><span>HARBOR / CUSTOMER SUPPORT</span><span>Sample activity for demonstration</span></footer>
  </div>
`;

const elements = Object.fromEntries(
  ['connectButton', 'muteButton', 'statusBadge', 'voiceSymbol', 'callStatus', 'callHint', 'errorMessage', 'elapsed']
    .map(id => [id, document.getElementById(id)]),
);
const audio = new Audio();
audio.autoplay = true;

let client;
let connected = false;
let connecting = false;
let muted = false;
let startedAt = 0;
let clerk;
let currentUserId = null;

async function authenticatedFetch(path, options = {}) {
  const token = await clerk.session?.getToken();
  if (!token) throw new Error('Please sign in again.');
  const response = await fetch(path, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(response.status === 401 ? 'Please sign in again.' : 'The service is unavailable.');
  return response.json();
}

async function loadActivity() {
  const list = document.getElementById('activityList');
  try {
    const { transactions } = await authenticatedFetch('/api/transactions');
    list.replaceChildren();
    for (const transaction of transactions) {
      const row = document.createElement('div');
      row.className = 'activity-row';
      const details = document.createElement('span');
      details.textContent = `${transaction.merchant} · ${new Date(transaction.occurred_at).toLocaleDateString()}`;
      const amount = document.createElement('strong');
      amount.textContent = `${transaction.currency} ${transaction.amount}`;
      row.append(details, amount);
      list.append(row);
    }
  } catch (error) {
    list.textContent = error.message;
  }
}

async function renderSession() {
  const userId = clerk.user?.id;
  if (userId === currentUserId) return;
  currentUserId = userId;
  const authPanel = document.getElementById('authPanel');
  const main = document.getElementById('mainContent');
  const userButton = document.getElementById('userButton');
  if (userId) {
    authPanel.replaceChildren();
    authPanel.hidden = true;
    main.hidden = false;
    clerk.mountUserButton(userButton);
    await loadActivity();
  } else {
    if (client && (connected || connecting)) await client.disconnect().catch(() => {});
    resetConnection();
    main.hidden = true;
    userButton.replaceChildren();
    authPanel.hidden = false;
    authPanel.innerHTML = '<h1>Welcome to Harbor Support</h1><p>Sign in to view your activity and start a conversation.</p><div id="signIn"></div>';
    clerk.mountSignIn(document.getElementById('signIn'));
  }
}

function setStatus(title, hint, mode = '') {
  elements.callStatus.textContent = title;
  elements.callHint.textContent = hint;
  elements.voiceSymbol.className = `voice-symbol ${mode}`;
}

function showError(error) {
  elements.errorMessage.hidden = false;
  elements.errorMessage.textContent = error?.data?.message || error?.message || String(error);
}

function resetConnection() {
  connected = false;
  connecting = false;
  muted = false;
  audio.srcObject = null;
  elements.connectButton.disabled = false;
  elements.connectButton.innerHTML = 'Start conversation <span aria-hidden="true">↗</span>';
  elements.muteButton.disabled = true;
  elements.muteButton.textContent = 'Mic on';
  elements.muteButton.setAttribute('aria-label', 'Mute microphone');
  elements.statusBadge.textContent = 'OFFLINE';
  elements.elapsed.textContent = '00:00';
  setStatus('Ready when you are', 'Connect your microphone to begin.');
}

async function toggleConnection() {
  if (connecting) return;
  if (!clerk?.user) return;
  if (connected) {
    await client.disconnect();
    return;
  }

  connecting = true;
  elements.errorMessage.hidden = true;
  elements.connectButton.disabled = true;
  elements.statusBadge.textContent = 'CONNECTING';
  setStatus('Connecting', 'Allow microphone access when prompted.', 'working');

  client = new PipecatClient({
    transport: new SmallWebRTCTransport(),
    enableMic: true,
    enableCam: false,
    callbacks: {
      onConnected: () => {
        connecting = false;
        connected = true;
        startedAt = Date.now();
        elements.connectButton.disabled = false;
        elements.connectButton.textContent = 'End conversation';
        elements.muteButton.disabled = false;
        elements.statusBadge.textContent = 'CONNECTED';
        setStatus('Connected', 'Ask about your activity or banking guidance.', 'active');
      },
      onDisconnected: resetConnection,
      onBotReady: () => setStatus('Listening', 'Ask about your activity or banking guidance.', 'active'),
      onUserStartedSpeaking: () => setStatus('Listening', 'Take your time.', 'listening'),
      onUserStoppedSpeaking: () => setStatus('Preparing an answer', 'Checking your request.', 'working'),
      onBotStartedSpeaking: () => setStatus('Speaking', 'You can interrupt at any time.', 'speaking'),
      onBotStoppedSpeaking: () => setStatus('Listening', 'Ask another question.', 'active'),
      onError: showError,
      onDeviceError: showError,
    },
  });

  client.on(RTVIEvent.TrackStarted, (track, participant) => {
    if (track.kind === 'audio' && !participant?.local) {
      audio.srcObject = new MediaStream([track]);
      audio.play().catch(() => showError('Audio playback was blocked. Check your browser sound permission.'));
    }
  });

  try {
    const { ticket } = await authenticatedFetch('/api/voice-tickets', { method: 'POST' });
    await client.startBotAndConnect({
      endpoint: '/start',
      requestData: { transport: 'webrtc', createDailyRoom: false, enableDefaultIceServers: true, body: { voice_ticket: ticket } },
    });
  } catch (error) {
    await client.disconnect().catch(() => {});
    resetConnection();
    showError(error);
  }
}

elements.connectButton.addEventListener('click', () => toggleConnection().catch(showError));
elements.muteButton.addEventListener('click', () => {
  muted = !muted;
  client.enableMic(!muted);
  elements.muteButton.textContent = muted ? 'Mic off' : 'Mic on';
  elements.muteButton.setAttribute('aria-label', muted ? 'Unmute microphone' : 'Mute microphone');
});

setInterval(() => {
  if (!connected) return;
  const seconds = Math.floor((Date.now() - startedAt) / 1000);
  elements.elapsed.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
}, 1000);

const publishableKey = import.meta.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
if (publishableKey) {
  clerk = new Clerk(publishableKey);
  clerk.load({
    ui,
    localization: { signIn: { start: { title: 'Sign in' } } },
  }).then(() => {
    clerk.addListener(() => renderSession().catch(showError));
    renderSession().catch(showError);
  }).catch(showError);
} else {
  document.getElementById('authPanel').textContent = 'Sign-in configuration is missing.';
}
