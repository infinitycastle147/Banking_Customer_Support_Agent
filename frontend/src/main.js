import { PipecatClient, RTVIEvent } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import './style.css';

document.querySelector('#app').innerHTML = `
  <div class="shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark" aria-hidden="true">H</span><span>HARBOR <small>SUPPORT PILOT</small></span></div>
      <span class="environment"><i></i> LOCAL PROTOTYPE</span>
    </header>
    <main>
      <div class="eyebrow"><span>01 / VOICE GUIDANCE</span><span>PUBLIC INFORMATION ONLY</span></div>
      <div class="content">
        <section class="intro">
          <p class="overline">A clearer way forward</p>
          <h1>Start with<br/><em>a conversation.</em></h1>
          <p class="lead">Ask about approved public guidance. This pilot has no access to accounts, transactions, or disputes.</p>
          <div class="notice"><span class="notice-icon" aria-hidden="true">i</span><p>Live speech is sent to the configured voice provider during a session. Please do not share account numbers, passwords, card details, or one-time codes. No transcript is saved by this browser.</p></div>
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
    <footer><span>HARBOR / CUSTOMER SUPPORT</span><span>Prototype for local evaluation · No bank connection</span></footer>
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
        setStatus('Connected', 'Ask a public guidance question.', 'active');
      },
      onDisconnected: resetConnection,
      onBotReady: () => setStatus('Listening', 'Ask a public guidance question.', 'active'),
      onUserStartedSpeaking: () => setStatus('Listening', 'Take your time.', 'listening'),
      onUserStoppedSpeaking: () => setStatus('Preparing an answer', 'Checking available guidance.', 'working'),
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
    await client.startBotAndConnect({
      endpoint: '/start',
      requestData: { transport: 'webrtc', createDailyRoom: false, enableDefaultIceServers: true },
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
