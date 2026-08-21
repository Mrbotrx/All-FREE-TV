(function () {
  "use strict";

  const script = document.currentScript;

  const PLAYLIST =
    script?.dataset.playlist ||
    "https://raw.githubusercontent.com/abusaeeidx/Mrgify-BDIX-IPTV/main/playlist.m3u";

  const TITLE =
    script?.dataset.title ||
    "KB CYBER TV";

  const LOGO =
    script?.dataset.logo ||
    "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/refs/heads/main/kbctlogo.png";

  let channels = [];
  let hls = null;
  let isSwitching = false;

  /* =========================
     LOAD HLS.JS
  ========================= */

  function loadHLS(callback) {
    if (window.Hls) {
      callback();
      return;
    }

    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/hls.js@latest";
    s.onload = callback;
    s.onerror = function () {
      console.error("KB CYBER TV: HLS.js failed to load.");
      callback();
    };
    document.head.appendChild(s);
  }

  /* =========================
     CSS WITH ANIMATIONS
  ========================= */

  function addCSS() {
    if (document.getElementById("kbcyber-css")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "kbcyber-css";
    style.textContent = `
      @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');

      .kbcyber {
        --pink:#ff1493;
        --pink2:#ff4db8;
        --dark:#080108;
        --panel:#12030e;
        --glass: rgba(255, 20, 147, 0.08);
        --glass-border: rgba(255, 20, 147, 0.15);
        
        width:100%;
        max-width:1150px;
        margin:15px auto;
        color:white;
        font-family: 'Orbitron', Arial, Helvetica, sans-serif;
        background: linear-gradient(145deg, #080108, #16000e);
        border: 1px solid var(--glass-border);
        border-radius:18px;
        overflow:hidden;
        box-shadow: 0 20px 70px rgba(255,20,147,.18);
        position:relative;
      }

      .kbcyber::before {
        content: '';
        position:absolute;
        top:-50%;
        left:-50%;
        width:200%;
        height:200%;
        background: radial-gradient(circle at 30% 50%, rgba(255,20,147,0.03), transparent 50%);
        animation: kbBgFloat 20s ease-in-out infinite;
        pointer-events:none;
        z-index:0;
      }

      @keyframes kbBgFloat {
        0%, 100% { transform: translate(0, 0) rotate(0deg); }
        33% { transform: translate(5%, 3%) rotate(5deg); }
        66% { transform: translate(-3%, 5%) rotate(-3deg); }
      }

      .kb-header {
        display:flex;
        align-items:center;
        justify-content:space-between;
        padding:13px 15px;
        background: linear-gradient(135deg, rgba(23,0,15,0.95), rgba(8,1,8,0.95));
        border-bottom: 1px solid var(--glass-border);
        position:relative;
        z-index:1;
        backdrop-filter: blur(10px);
      }

      .kb-brand {
        display:flex;
        align-items:center;
        gap:10px;
      }

      .kb-logo {
        width:40px;
        height:40px;
        object-fit:contain;
        border-radius:50%;
        border: 2px solid rgba(255,20,147,.5);
        box-shadow: 0 0 20px rgba(255,20,147,.3);
        animation: kbLogoPulse 3s ease-in-out infinite;
      }

      @keyframes kbLogoPulse {
        0%, 100% { box-shadow: 0 0 20px rgba(255,20,147,.3); }
        50% { box-shadow: 0 0 40px rgba(255,20,147,.6), 0 0 60px rgba(255,20,147,.2); }
      }

      .kb-name {
        font-size:16px;
        font-weight:900;
        letter-spacing:.4px;
        background: linear-gradient(135deg, #ff1493, #ff6bcb, #ff1493);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: kbGradientText 3s ease-in-out infinite;
      }

      @keyframes kbGradientText {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }

      .kb-small {
        margin-top:2px;
        color:#ff82c8;
        font-size:8px;
        letter-spacing:2px;
        opacity:0.7;
      }

      .kb-live {
        display:flex;
        align-items:center;
        gap:5px;
        padding: 6px 12px;
        border-radius:20px;
        background: linear-gradient(135deg, #ff1493, #b00062);
        font-size:10px;
        font-weight:900;
        box-shadow: 0 0 20px rgba(255,20,147,.3);
        animation: kbLivePulse 2s ease-in-out infinite;
        position:relative;
        overflow:hidden;
      }

      .kb-live::after {
        content: '';
        position:absolute;
        top:-50%;
        left:-50%;
        width:200%;
        height:200%;
        background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
        animation: kbLiveShine 3s ease-in-out infinite;
      }

      @keyframes kbLiveShine {
        0% { transform: translateX(-100%) rotate(45deg); }
        100% { transform: translateX(100%) rotate(45deg); }
      }

      @keyframes kbLivePulse {
        0%, 100% { box-shadow: 0 0 20px rgba(255,20,147,.3); }
        50% { box-shadow: 0 0 40px rgba(255,20,147,.6), 0 0 60px rgba(255,20,147,.2); }
      }

      .kb-live-dot {
        width:6px;
        height:6px;
        border-radius:50%;
        background:white;
        animation: kbDotPulse 1s ease-in-out infinite;
        position:relative;
        z-index:1;
      }

      @keyframes kbDotPulse {
        0%, 100% { opacity:1; transform: scale(1); }
        50% { opacity:0.3; transform: scale(0.8); }
      }

      .kb-player-area {
        position:relative;
        width:100%;
        aspect-ratio:16/9;
        background:#000;
        overflow:hidden;
        z-index:1;
      }

      .kb-player-area::before {
        content: '';
        position:absolute;
        inset:0;
        background: linear-gradient(45deg, transparent 40%, rgba(255,20,147,0.03) 100%);
        pointer-events:none;
        z-index:5;
      }

      .kb-video {
        width:100%;
        height:100%;
        display:block;
        object-fit:contain;
        background:#000;
        transition: opacity 0.5s ease;
      }

      .kb-video.fade-out {
        opacity:0;
      }

      .kb-video.fade-in {
        opacity:1;
      }

      /* Switching Animation Overlay */
      .kb-switch-overlay {
        position:absolute;
        inset:0;
        display:none;
        align-items:center;
        justify-content:center;
        background: rgba(0,0,0,0.7);
        z-index:6;
        backdrop-filter: blur(5px);
      }

      .kb-switch-overlay.active {
        display:flex;
        animation: kbSwitchIn 0.4s ease-out;
      }

      @keyframes kbSwitchIn {
        0% { opacity:0; transform: scale(1.1); }
        100% { opacity:1; transform: scale(1); }
      }

      .kb-switch-content {
        text-align:center;
      }

      .kb-switch-spinner {
        width:50px;
        height:50px;
        margin:0 auto 15px;
        border: 3px solid rgba(255,20,147,.15);
        border-top-color: #ff1493;
        border-right-color: #ff4db8;
        border-radius:50%;
        animation: kbSpin 0.8s linear infinite;
      }

      .kb-switch-text {
        font-size:12px;
        color:#ff82c8;
        letter-spacing:2px;
      }

      @keyframes kbSpin {
        to { transform:rotate(360deg); }
      }

      .kb-center-play {
        position:absolute;
        inset:0;
        display:flex;
        align-items:center;
        justify-content:center;
        pointer-events:none;
        z-index:3;
      }

      .kb-big-play {
        width:72px;
        height:72px;
        border:0;
        border-radius:50%;
        color:#fff;
        background: linear-gradient(135deg, #ff1493, #b00062);
        font-size:25px;
        cursor:pointer;
        pointer-events:auto;
        box-shadow: 0 0 50px rgba(255,20,147,.6);
        transition: all 0.3s ease;
        position:relative;
        overflow:hidden;
      }

      .kb-big-play::before {
        content: '';
        position:absolute;
        inset:-2px;
        border-radius:50%;
        background: linear-gradient(135deg, #ff1493, #ff6bcb, #ff1493);
        background-size: 200% 200%;
        animation: kbGradientBorder 3s ease-in-out infinite;
        z-index:-1;
        padding:2px;
        -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
        -webkit-mask-composite: xor;
        mask-composite: exclude;
      }

      @keyframes kbGradientBorder {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
      }

      .kb-big-play:hover {
        transform: scale(1.1);
        box-shadow: 0 0 70px rgba(255,20,147,.8);
      }

      .kb-loading {
        position:absolute;
        inset:0;
        display:none;
        flex-direction:column;
        align-items:center;
        justify-content:center;
        gap:12px;
        background: rgba(0,0,0,.45);
        z-index:10;
        font-size:12px;
        backdrop-filter: blur(3px);
      }

      .kb-loading.active {
        display:flex;
        animation: kbLoadingFade 0.3s ease-out;
      }

      @keyframes kbLoadingFade {
        0% { opacity:0; }
        100% { opacity:1; }
      }

      .kb-spinner {
        width:38px;
        height:38px;
        border: 3px solid rgba(255,255,255,.15);
        border-top-color: #ff1493;
        border-right-color: #ff4db8;
        border-radius:50%;
        animation: kbSpin .8s linear infinite;
      }

      .kb-error {
        position:absolute;
        inset:0;
        display:none;
        align-items:center;
        justify-content:center;
        text-align:center;
        background: radial-gradient(circle, #280018, #030003 70%);
        z-index:12;
        animation: kbErrorFade 0.3s ease-out;
      }

      @keyframes kbErrorFade {
        0% { opacity:0; transform: scale(0.95); }
        100% { opacity:1; transform: scale(1); }
      }

      .kb-error-title {
        color:#ff4db8;
        font-weight:900;
        margin-bottom:10px;
        font-size:16px;
      }

      .kb-retry {
        border:0;
        padding: 8px 20px;
        border-radius:20px;
        color:white;
        background: linear-gradient(135deg, #ff1493, #b00062);
        cursor:pointer;
        transition: all 0.3s ease;
        font-family: 'Orbitron', Arial, sans-serif;
        font-size:11px;
      }

      .kb-retry:hover {
        transform: scale(1.05);
        box-shadow: 0 0 30px rgba(255,20,147,.4);
      }

      .kb-controls {
        position:absolute;
        left:0;
        right:0;
        bottom:0;
        display:flex;
        align-items:center;
        gap:5px;
        padding: 32px 10px 9px;
        background: linear-gradient(transparent, rgba(0,0,0,.95));
        z-index:8;
        opacity:0;
        transition: opacity 0.3s ease;
      }

      .kb-player-area:hover .kb-controls,
      .kb-controls:hover {
        opacity:1;
      }

      .kb-btn {
        width:34px;
        height:34px;
        border:0;
        border-radius:8px;
        color:white;
        background: rgba(255,255,255,.06);
        cursor:pointer;
        font-size:15px;
        transition: all 0.3s ease;
        backdrop-filter: blur(5px);
        border: 1px solid transparent;
      }

      .kb-btn:hover {
        background: rgba(255,20,147,.3);
        transform: scale(1.05);
        border-color: rgba(255,20,147,.3);
      }

      .kb-btn:active {
        transform: scale(0.95);
      }

      .kb-volume {
        width:75px;
        accent-color: #ff1493;
        transition: all 0.3s ease;
      }

      .kb-volume::-webkit-slider-thumb {
        background: #ff1493;
        box-shadow: 0 0 20px rgba(255,20,147,.3);
      }

      .kb-live-text {
        margin-left:auto;
        color:#ff4db8;
        font-size:10px;
        font-weight:900;
        animation: kbTextPulse 2s ease-in-out infinite;
      }

      @keyframes kbTextPulse {
        0%, 100% { opacity:1; }
        50% { opacity:0.5; }
      }

      .kb-quality-menu {
        position:absolute;
        right:45px;
        bottom:55px;
        display:none;
        min-width:100px;
        z-index:20;
        background: rgba(15,2,11,.98);
        border: 1px solid rgba(255,20,147,.3);
        border-radius:12px;
        overflow:hidden;
        box-shadow: 0 15px 40px rgba(0,0,0,.7);
        backdrop-filter: blur(10px);
        animation: kbMenuSlide 0.2s ease-out;
      }

      @keyframes kbMenuSlide {
        0% { opacity:0; transform: translateY(-10px) scale(0.95); }
        100% { opacity:1; transform: translateY(0) scale(1); }
      }

      .kb-quality-menu.show {
        display:block;
      }

      .kb-quality-menu div {
        padding: 10px 14px;
        font-size:11px;
        cursor:pointer;
        transition: all 0.3s ease;
        font-family: 'Orbitron', Arial, sans-serif;
      }

      .kb-quality-menu div:hover {
        background: linear-gradient(135deg, #ff1493, #b00062);
        transform: scale(1.02);
      }

      .kb-channel-area {
        padding:12px;
        position:relative;
        z-index:1;
        background: linear-gradient(180deg, rgba(8,1,8,0.9), rgba(22,0,14,0.95));
        backdrop-filter: blur(10px);
      }

      .kb-search {
        width:100%;
        box-sizing:border-box;
        padding: 12px 14px;
        border-radius:12px;
        outline:none;
        border: 1px solid var(--glass-border);
        background: rgba(13,2,10,0.8);
        color:white;
        font-size:13px;
        margin-bottom:10px;
        transition: all 0.3s ease;
        font-family: 'Orbitron', Arial, sans-serif;
        backdrop-filter: blur(5px);
      }

      .kb-search:focus {
        border-color: #ff1493;
        box-shadow: 0 0 25px rgba(255,20,147,.15);
        transform: scale(1.01);
      }

      .kb-search::placeholder {
        color: rgba(255,255,255,0.3);
      }

      .kb-categories {
        display:flex;
        gap:6px;
        overflow-x:auto;
        padding-bottom:10px;
        scrollbar-width:none;
      }

      .kb-categories::-webkit-scrollbar {
        display:none;
      }

      .kb-cat {
        flex:none;
        border:1px solid var(--glass-border);
        background: rgba(16,3,12,0.6);
        color:#ff9bd2;
        padding: 7px 14px;
        border-radius:20px;
        cursor:pointer;
        font-size:10px;
        white-space:nowrap;
        transition: all 0.3s ease;
        font-family: 'Orbitron', Arial, sans-serif;
        backdrop-filter: blur(5px);
      }

      .kb-cat.active,
      .kb-cat:hover {
        color:white;
        background: linear-gradient(135deg, #ff1493, #b00062);
        border-color: transparent;
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(255,20,147,.3);
      }

      .kb-channels {
        display:grid;
        grid-template-columns: repeat(auto-fill, minmax(145px,1fr));
        gap:8px;
        max-height:430px;
        overflow-y:auto;
        padding-right:3px;
      }

      .kb-channels::-webkit-scrollbar {
        width:4px;
      }

      .kb-channels::-webkit-scrollbar-track {
        background: rgba(255,20,147,.05);
        border-radius:10px;
      }

      .kb-channels::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #ff1493, #b00062);
        border-radius:10px;
      }

      .kb-channel {
        display:flex;
        align-items:center;
        gap:9px;
        min-height:48px;
        padding:8px 10px;
        border: 1px solid var(--glass-border);
        border-radius:12px;
        background: rgba(19,3,14,0.6);
        color:white;
        cursor:pointer;
        text-align:left;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        backdrop-filter: blur(5px);
        position:relative;
        overflow:hidden;
      }

      .kb-channel::before {
        content: '';
        position:absolute;
        inset:0;
        background: linear-gradient(135deg, rgba(255,20,147,0.05), transparent);
        opacity:0;
        transition: opacity 0.3s ease;
      }

      .kb-channel:hover {
        transform: translateY(-2px);
        border-color: rgba(255,20,147,.55);
        box-shadow: 0 5px 25px rgba(255,20,147,.15);
      }

      .kb-channel:hover::before {
        opacity:1;
      }

      .kb-channel:active {
        transform: scale(0.98);
      }

      .kb-channel.active {
        border-color: #ff1493;
        background: linear-gradient(135deg, rgba(255,20,147,.15), rgba(19,3,14,0.8));
        box-shadow: 0 0 30px rgba(255,20,147,.1);
        animation: kbChannelActive 0.4s ease-out;
      }

      @keyframes kbChannelActive {
        0% { transform: scale(0.95); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
      }

      .kb-channel img {
        width:32px;
        height:32px;
        object-fit:contain;
        border-radius:8px;
        background: rgba(0,0,0,0.5);
        padding:2px;
        transition: all 0.3s ease;
        position:relative;
        z-index:1;
      }

      .kb-channel:hover img {
        transform: scale(1.05);
      }

      .kb-channel-name {
        font-size:10px;
        font-weight:700;
        line-height:1.25;
        word-break:break-word;
        position:relative;
        z-index:1;
        font-family: 'Orbitron', Arial, sans-serif;
        letter-spacing:0.3px;
      }

      .kb-empty {
        padding:30px;
        text-align:center;
        color:#ff8ccc;
        font-size:12px;
        grid-column: 1 / -1;
        animation: kbEmptyFade 0.5s ease-out;
      }

      @keyframes kbEmptyFade {
        0% { opacity:0; transform: translateY(10px); }
        100% { opacity:1; transform: translateY(0); }
      }

      /* Channel switch animation */
      .kb-channel-switching {
        animation: kbSwitchGlow 0.6s ease-out;
      }

      @keyframes kbSwitchGlow {
        0% { box-shadow: 0 0 0 rgba(255,20,147,0); }
        50% { box-shadow: 0 0 50px rgba(255,20,147,0.3); }
        100% { box-shadow: 0 0 0 rgba(255,20,147,0); }
      }

      @media(max-width:600px) {
        .kbcyber {
          margin:7px auto;
          border-radius:11px;
        }
        .kb-name {
          font-size:13px;
        }
        .kb-logo {
          width:32px;
          height:32px;
        }
        .kb-volume {
          display:none;
        }
        .kb-btn {
          width:30px;
          height:30px;
          font-size:13px;
        }
        .kb-big-play {
          width:58px;
          height:58px;
          font-size:20px;
        }
        .kb-channels {
          grid-template-columns: repeat(2,1fr);
          max-height:360px;
        }
        .kb-channel {
          min-height:44px;
          padding:6px 8px;
        }
        .kb-channel img {
          width:28px;
          height:28px;
        }
        .kb-channel-name {
          font-size:9px;
        }
        .kb-controls {
          opacity:1;
          padding: 20px 8px 8px;
        }
        .kb-search {
          font-size:12px;
          padding:10px 12px;
        }
        .kb-cat {
          font-size:9px;
          padding:5px 10px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  /* =========================
     PARSE M3U
  ========================= */

  function parseM3U(text) {
    const lines = text.replace(/\r/g, "").split("\n").map(x => x.trim()).filter(Boolean);
    const result = [];
    let info = null;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      if (line.startsWith("#EXTINF")) {
        const nameMatch = line.match(/,([^,]*)$/);
        const namePart = nameMatch ? nameMatch[1].trim() : "Unknown Channel";
        
        const groupMatch = line.match(/group-title="([^"]*)"/i);
        const logoMatch = line.match(/tvg-logo="([^"]*)"/i);
        const tvgNameMatch = line.match(/tvg-name="([^"]*)"/i);

        info = {
          name: namePart || (tvgNameMatch ? tvgNameMatch[1] : "Unknown Channel"),
          group: groupMatch ? groupMatch[1] : "Other",
          logo: logoMatch ? logoMatch[1] : ""
        };
        continue;
      }

      if (!line.startsWith("#") && /^https?:\/\//i.test(line)) {
        if (info) {
          result.push({
            name: info.name,
            group: info.group,
            logo: info.logo,
            url: line
          });
          info = null;
        } else {
          result.push({
            name: "Live Channel",
            group: "Other",
            logo: "",
            url: line
          });
        }
      }
    }

    return result;
  }

  /* =========================
     CREATE UI
  ========================= */

  function createUI() {
    addCSS();

    const root = document.createElement("div");
    root.className = "kbcyber";
    root.innerHTML = `
      <div class="kb-header">
        <div class="kb-brand">
          <img class="kb-logo" src="${escapeHTML(LOGO)}">
          <div>
            <div class="kb-name">${escapeHTML(TITLE)}</div>
            <div class="kb-small">⚡ LIVE IPTV</div>
          </div>
        </div>
        <div class="kb-live">
          <span class="kb-live-dot"></span>
          LIVE
        </div>
      </div>
      <div class="kb-player-area">
        <video class="kb-video" playsinline preload="metadata"></video>
        
        <!-- Switching Overlay -->
        <div class="kb-switch-overlay">
          <div class="kb-switch-content">
            <div class="kb-switch-spinner"></div>
            <div class="kb-switch-text">SWITCHING CHANNEL...</div>
          </div>
        </div>
        
        <div class="kb-center-play">
          <button class="kb-big-play">▶</button>
        </div>
        <div class="kb-loading">
          <div class="kb-spinner"></div>
          <span>CONNECTING...</span>
        </div>
        <div class="kb-error">
          <div>
            <div class="kb-error-title">⚠ STREAM UNAVAILABLE</div>
            <button class="kb-retry">↻ RETRY</button>
          </div>
        </div>
        <div class="kb-quality-menu"></div>
        <div class="kb-controls">
          <button class="kb-btn kb-play">▶</button>
          <button class="kb-btn kb-mute">🔊</button>
          <input class="kb-volume" type="range" min="0" max="1" step="0.05" value="1">
          <span class="kb-live-text">● LIVE</span>
          <button class="kb-btn kb-quality-btn">⚙</button>
          <button class="kb-btn kb-pip">▣</button>
          <button class="kb-btn kb-fullscreen">⛶</button>
        </div>
      </div>
      <div class="kb-channel-area">
        <input class="kb-search" type="search" placeholder="🔎 SEARCH CHANNELS...">
        <div class="kb-categories"></div>
        <div class="kb-channels"></div>
      </div>
    `;

    script.parentNode.insertBefore(root, script);
    return root;
  }

  /* =========================
     PLAYER
  ========================= */

  function setupPlayer(root) {
    const video = root.querySelector(".kb-video");
    const play = root.querySelector(".kb-play");
    const bigPlay = root.querySelector(".kb-big-play");
    const mute = root.querySelector(".kb-mute");
    const volume = root.querySelector(".kb-volume");
    const qualityButton = root.querySelector(".kb-quality-btn");
    const qualityMenu = root.querySelector(".kb-quality-menu");
    const fullscreen = root.querySelector(".kb-fullscreen");
    const pip = root.querySelector(".kb-pip");
    const loading = root.querySelector(".kb-loading");
    const error = root.querySelector(".kb-error");
    const retry = root.querySelector(".kb-retry");
    const switchOverlay = root.querySelector(".kb-switch-overlay");

    function playPause() {
      if (video.paused) {
        video.play().catch(() => {});
      } else {
        video.pause();
      }
    }

    play.onclick = playPause;
    bigPlay.onclick = playPause;

    video.addEventListener("play", updateButtons);
    video.addEventListener("pause", updateButtons);

    function updateButtons() {
      play.textContent = video.paused ? "▶" : "❚❚";
      bigPlay.style.display = video.paused ? "flex" : "none";
    }

    mute.onclick = function () {
      video.muted = !video.muted;
      updateMute();
    };

    volume.oninput = function () {
      video.volume = Number(volume.value);
      video.muted = video.volume === 0;
      updateMute();
    };

    function updateMute() {
      mute.textContent = video.muted || video.volume === 0 ? "🔇" : "🔊";
    }

    fullscreen.onclick = function () {
      if (!document.fullscreenElement) {
        root.querySelector(".kb-player-area").requestFullscreen?.();
      } else {
        document.exitFullscreen?.();
      }
    };

    pip.onclick = async function () {
      try {
        if (document.pictureInPictureElement) {
          await document.exitPictureInPicture();
        } else {
          await video.requestPictureInPicture();
        }
      } catch (e) {
        console.log("PiP unavailable");
      }
    };

    qualityButton.onclick = function (e) {
      e.stopPropagation();
      qualityMenu.classList.toggle("show");
    };

    document.addEventListener("click", function (e) {
      if (!qualityMenu.contains(e.target) && !qualityButton.contains(e.target)) {
        qualityMenu.classList.remove("show");
      }
    });

    retry.onclick = function () {
      const current = video.dataset.url;
      if (current) {
        loadStream(current);
      }
    };

    function loadStream(url, isAutoPlay = true) {
      if (!url) return;
      
      // Show switching animation
      if (video.dataset.url && video.dataset.url !== url) {
        switchOverlay.classList.add("active");
        setTimeout(() => {
          switchOverlay.classList.remove("active");
        }, 600);
      }
      
      video.dataset.url = url;
      loading.classList.add("active");
      error.style.display = "none";
      
      if (hls) {
        hls.destroy();
        hls = null;
      }

      // Video fade animation
      video.classList.add("fade-out");
      setTimeout(() => {
        video.classList.remove("fade-out");
      }, 300);

      if (video.canPlayType("application/vnd.apple.mpegurl")) {
        video.src = url;
        video.addEventListener("loadedmetadata", function () {
          loading.classList.remove("active");
          video.classList.add("fade-in");
          if (isAutoPlay) {
            video.play().catch(() => {});
          }
        }, { once: true });
        video.addEventListener("error", function () {
          loading.classList.remove("active");
          error.style.display = "flex";
        }, { once: true });
        return;
      }

      if (window.Hls && Hls.isSupported()) {
        hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
          liveSyncDurationCount: 3,
          maxBufferLength: 20,
          maxMaxBufferLength: 30
        });

        hls.loadSource(url);
        hls.attachMedia(video);

        hls.on(Hls.Events.MANIFEST_PARSED, function () {
          loading.classList.remove("active");
          video.classList.add("fade-in");
          if (isAutoPlay) {
            video.play().catch(() => {});
          }
          buildQuality();
        });

        hls.on(Hls.Events.ERROR, function (event, data) {
          if (data.fatal) {
            loading.classList.remove("active");
            error.style.display = "flex";
          }
        });
      } else {
        video.src = url;
        video.addEventListener("loadedmetadata", function () {
          loading.classList.remove("active");
          video.classList.add("fade-in");
          if (isAutoPlay) {
            video.play().catch(() => {});
          }
        }, { once: true });
        video.addEventListener("error", function () {
          loading.classList.remove("active");
          error.style.display = "flex";
        }, { once: true });
      }
    }

    function buildQuality() {
      qualityMenu.innerHTML = "";
      
      const auto = document.createElement("div");
      auto.textContent = "AUTO";
      auto.onclick = function () {
        if (hls) hls.currentLevel = -1;
        qualityMenu.classList.remove("show");
      };
      qualityMenu.appendChild(auto);

      if (!hls) return;

      hls.levels.forEach(function (level, index) {
        const item = document.createElement("div");
        item.textContent = level.height ? level.height + "P" : "Quality " + (index + 1);
        item.onclick = function () {
          hls.currentLevel = index;
          qualityMenu.classList.remove("show");
        };
        qualityMenu.appendChild(item);
      });
    }

    return { loadStream };
  }

  /* =========================
     CHANNEL LIST
  ========================= */

  function setupChannels(root, player) {
    const search = root.querySelector(".kb-search");
    const categories = root.querySelector(".kb-categories");
    const channelBox = root.querySelector(".kb-channels");
    let activeCategory = "All";

    function getCategories() {
      const set = new Set(["All"]);
      channels.forEach(c => set.add(c.group));
      return [...set];
    }

    function renderCategories() {
      categories.innerHTML = "";
      getCategories().forEach(function (cat) {
        const button = document.createElement("button");
        button.className = "kb-cat" + (cat === activeCategory ? " active" : "");
        button.textContent = cat;
        button.onclick = function () {
          activeCategory = cat;
          renderCategories();
          renderChannels();
        };
        categories.appendChild(button);
      });
    }

    function renderChannels() {
      const query = search.value.toLowerCase().trim();
      channelBox.innerHTML = "";

      const filtered = channels.filter(function (channel) {
        const categoryOK = activeCategory === "All" || channel.group === activeCategory;
        const searchOK = !query || channel.name.toLowerCase().includes(query);
        return categoryOK && searchOK;
      });

      if (!filtered.length) {
        channelBox.innerHTML = `<div class="kb-empty">🚫 NO CHANNELS FOUND</div>`;
        return;
      }

      filtered.forEach(function (channel, index) {
        const button = document.createElement("button");
        button.className = "kb-channel";
        button.style.animationDelay = (index * 0.05) + "s";
        button.innerHTML = `
          ${channel.logo ? `<img src="${escapeHTML(channel.logo)}" loading="lazy">` : `<img src="${escapeHTML(LOGO)}">`}
          <span class="kb-channel-name">${escapeHTML(channel.name)}</span>
        `;
        button.onclick = function () {
          root.querySelectorAll(".kb-channel").forEach(x => x.classList.remove("active"));
          button.classList.add("active");
          player.loadStream(channel.url);
        };
        channelBox.appendChild(button);
        
        // Small entrance animation
        button.style.opacity = "0";
        button.style.transform = "translateY(10px)";
        setTimeout(() => {
          button.style.transition = "all 0.3s ease-out";
          button.style.opacity = "1";
          button.style.transform = "translateY(0)";
        }, index * 30);
      });
    }

    search.oninput = renderChannels;
    renderCategories();
    renderChannels();
  }

  /* =========================
     LOAD PLAYLIST
  ========================= */

  async function loadPlaylist(root, player) {
    try {
      const response = await fetch(PLAYLIST, {
        cache: "no-store"
      });

      if (!response.ok) {
        throw new Error("Playlist HTTP " + response.status);
      }

      const text = await response.text();
      channels = parseM3U(text);

      if (!channels.length) {
        throw new Error("No channels found in playlist");
      }

      setupChannels(root, player);
      console.log("KB CYBER TV:", channels.length, "channels loaded.");

      if (channels.length > 0) {
        // Auto-play first channel
        player.loadStream(channels[0].url);
      }

    } catch (e) {
      console.error("KB CYBER TV playlist error:", e);
      root.querySelector(".kb-channels").innerHTML = `
        <div class="kb-empty">
          ⚠ UNABLE TO LOAD PLAYLIST<br><br>
          <span style="font-size:10px;opacity:0.6;">${escapeHTML(e.message)}</span>
        </div>
      `;
    }
  }

  /* =========================
     ESCAPE
  ========================= */

  function escapeHTML(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  /* =========================
     INIT
  ========================= */

  loadHLS(function () {
    const root = createUI();
    const player = setupPlayer(root);
    loadPlaylist(root, player);
  });

})();
