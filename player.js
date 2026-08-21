(function () {
  "use strict";

  const script = document.currentScript;

  const STREAM = script?.dataset.stream || "";
  const TITLE = script?.dataset.title || "KB CYBER TV";

  const LOGO =
    script?.dataset.logo ||
    "https://raw.githubusercontent.com/Mrbotrx/bdxi_tv/refs/heads/main/kbctlogo.png";

  if (!STREAM) {
    console.error("KB CYBER TV: data-stream is missing.");
    return;
  }

  function loadHLS(callback) {
    if (window.Hls) {
      callback();
      return;
    }

    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/hls.js@latest";
    s.onload = callback;
    s.onerror = () =>
      console.error("KB CYBER TV: HLS.js failed to load.");

    document.head.appendChild(s);
  }

  loadHLS(function () {
    injectCSS();

    const player = document.createElement("div");
    player.className = "kbcyber-player";

    player.innerHTML = `
      <div class="kb-video-wrap">

        <video
          class="kb-video"
          playsinline
          preload="metadata">
        </video>

        <!-- Top -->
        <div class="kb-top">

          <div class="kb-brand">
            <img
              class="kb-logo"
              src="${escapeHTML(LOGO)}"
              alt="KB CYBER TV">

            <div>
              <div class="kb-title">
                ${escapeHTML(TITLE)}
              </div>
              <div class="kb-subtitle">
                LIVE STREAM
              </div>
            </div>
          </div>

          <div class="kb-live">
            <span></span>
            LIVE
          </div>

        </div>

        <!-- Center -->
        <div class="kb-center">
          <button class="kb-big-play">
            ▶
          </button>
        </div>

        <!-- Loading -->
        <div class="kb-loading">
          <div class="kb-spinner"></div>
          <span>Connecting to live stream...</span>
        </div>

        <!-- Error -->
        <div class="kb-error">
          <div>
            <div class="kb-error-title">
              STREAM OFFLINE
            </div>
            <button class="kb-retry">
              ↻ Retry
            </button>
          </div>
        </div>

        <!-- Quality -->
        <div class="kb-quality-menu"></div>

        <!-- Controls -->
        <div class="kb-controls">

          <button
            class="kb-control kb-play"
            title="Play / Pause">
            ▶
          </button>

          <button
            class="kb-control kb-mute"
            title="Mute">
            🔊
          </button>

          <input
            class="kb-volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value="1">

          <div class="kb-live-status">
            <i></i>
            LIVE
          </div>

          <button
            class="kb-control kb-quality-btn"
            title="Quality">
            ⚙
          </button>

          <button
            class="kb-control kb-pip"
            title="Picture in Picture">
            ▣
          </button>

          <button
            class="kb-control kb-fullscreen"
            title="Fullscreen">
            ⛶
          </button>

        </div>

        <!-- Bottom glow -->
        <div class="kb-glow"></div>

      </div>
    `;

    script.parentNode.insertBefore(player, script);

    const video = player.querySelector(".kb-video");
    const play = player.querySelector(".kb-play");
    const bigPlay = player.querySelector(".kb-big-play");
    const mute = player.querySelector(".kb-mute");
    const volume = player.querySelector(".kb-volume");
    const qualityBtn =
      player.querySelector(".kb-quality-btn");
    const qualityMenu =
      player.querySelector(".kb-quality-menu");
    const fullscreen =
      player.querySelector(".kb-fullscreen");
    const pip = player.querySelector(".kb-pip");
    const loading =
      player.querySelector(".kb-loading");
    const error =
      player.querySelector(".kb-error");
    const retry =
      player.querySelector(".kb-retry");

    let hls = null;

    /* =========================
       START STREAM
    ========================= */

    function startStream() {
      loading.style.display = "flex";
      error.style.display = "none";

      if (hls) {
        hls.destroy();
        hls = null;
      }

      if (
        window.Hls &&
        Hls.isSupported()
      ) {
        hls = new Hls({
          enableWorker: true,
          lowLatencyMode: true,
          liveSyncDurationCount: 3,
          maxBufferLength: 20,
          maxMaxBufferLength: 30
        });

        hls.loadSource(STREAM);
        hls.attachMedia(video);

        hls.on(
          Hls.Events.MANIFEST_PARSED,
          function () {
            loading.style.display = "none";

            video.play().catch(() => {});

            buildQualityMenu();
            updateButtons();
          }
        );

        hls.on(
          Hls.Events.ERROR,
          function (event, data) {
            if (!data.fatal) return;

            console.error("HLS error:", data);

            loading.style.display = "none";
            error.style.display = "flex";
          }
        );

      } else if (
        video.canPlayType(
          "application/vnd.apple.mpegurl"
        )
      ) {
        video.src = STREAM;

        video.addEventListener(
          "loadedmetadata",
          function () {
            loading.style.display = "none";
            video.play().catch(() => {});
          },
          { once: true }
        );

        video.addEventListener(
          "error",
          function () {
            loading.style.display = "none";
            error.style.display = "flex";
          }
        );

      } else {
        loading.style.display = "none";
        error.style.display = "flex";
      }
    }

    /* =========================
       PLAY
    ========================= */

    function togglePlay() {
      if (video.paused) {
        video.play().catch(() => {});
      } else {
        video.pause();
      }
    }

    play.onclick = togglePlay;
    bigPlay.onclick = togglePlay;

    video.addEventListener(
      "play",
      updateButtons
    );

    video.addEventListener(
      "pause",
      updateButtons
    );

    function updateButtons() {
      if (video.paused) {
        play.textContent = "▶";
        bigPlay.style.display = "flex";
      } else {
        play.textContent = "❚❚";
        bigPlay.style.display = "none";
      }
    }

    /* =========================
       VOLUME
    ========================= */

    mute.onclick = function () {
      video.muted = !video.muted;
      updateVolumeIcon();
    };

    volume.oninput = function () {
      video.volume = Number(volume.value);

      if (video.volume === 0) {
        video.muted = true;
      } else {
        video.muted = false;
      }

      updateVolumeIcon();
    };

    function updateVolumeIcon() {
      mute.textContent =
        video.muted || video.volume === 0
          ? "🔇"
          : "🔊";
    }

    /* =========================
       FULLSCREEN
    ========================= */

    fullscreen.onclick = function () {
      if (!document.fullscreenElement) {
        if (player.requestFullscreen) {
          player.requestFullscreen();
        }
      } else {
        document.exitFullscreen?.();
      }
    };

    /* =========================
       PICTURE IN PICTURE
    ========================= */

    pip.onclick = async function () {
      try {
        if (document.pictureInPictureElement) {
          await document.exitPictureInPicture();
        } else if (
          document.pictureInPictureEnabled
        ) {
          await video.requestPictureInPicture();
        }
      } catch (e) {
        console.log("PiP unavailable");
      }
    };

    /* =========================
       QUALITY MENU
    ========================= */

    qualityBtn.onclick = function (e) {
      e.stopPropagation();
      qualityMenu.classList.toggle("show");
    };

    document.addEventListener(
      "click",
      function (e) {
        if (
          !qualityMenu.contains(e.target) &&
          !qualityBtn.contains(e.target)
        ) {
          qualityMenu.classList.remove("show");
        }
      }
    );

    function buildQualityMenu() {
      qualityMenu.innerHTML = "";

      const auto = document.createElement("div");
      auto.textContent = "AUTO";

      auto.onclick = function () {
        if (hls) hls.currentLevel = -1;
        qualityMenu.classList.remove("show");
      };

      qualityMenu.appendChild(auto);

      if (!hls || !hls.levels) return;

      hls.levels.forEach(
        function (level, index) {
          const item =
            document.createElement("div");

          item.textContent =
            level.height
              ? level.height + "P"
              : "Quality " + (index + 1);

          item.onclick = function () {
            hls.currentLevel = index;
            qualityMenu.classList.remove("show");
          };

          qualityMenu.appendChild(item);
        }
      );
    }

    /* =========================
       RETRY
    ========================= */

    retry.onclick = function () {
      startStream();
    };

    startStream();
  });

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
     MODERN PINK CSS
  ========================= */

  function injectCSS() {

    if (document.getElementById("kbcyber-css")) {
      return;
    }

    const style = document.createElement("style");
    style.id = "kbcyber-css";

    style.textContent = `

      .kbcyber-player {
        --pink: #ff1493;
        --pink2: #ff4db8;
        --pink-dark: #b00062;
        --bg: #070107;

        width: 100%;
        max-width: 1100px;
        margin: 15px auto;

        background: var(--bg);

        border-radius: 18px;

        overflow: hidden;

        font-family:
          Arial,
          Helvetica,
          sans-serif;

        box-shadow:
          0 20px 70px
          rgba(255,20,147,.22);

        border:
          1px solid
          rgba(255,20,147,.25);
      }

      .kb-video-wrap {
        position: relative;

        width: 100%;

        aspect-ratio: 16 / 9;

        background:
          radial-gradient(
            circle at 50% 50%,
            #210018 0%,
            #050005 65%,
            #000 100%
          );

        overflow: hidden;
      }

      .kb-video {
        width: 100%;
        height: 100%;

        display: block;

        object-fit: contain;

        background: #000;
      }

      /* TOP */

      .kb-top {
        position: absolute;

        top: 0;
        left: 0;
        right: 0;

        z-index: 5;

        display: flex;

        justify-content:
          space-between;

        align-items: center;

        padding:
          16px 17px 42px;

        background:
          linear-gradient(
            to bottom,
            rgba(0,0,0,.92),
            rgba(0,0,0,.15),
            transparent
          );
      }

      .kb-brand {
        display: flex;

        align-items: center;

        gap: 10px;

        color: white;
      }

      .kb-logo {
        width: 38px;
        height: 38px;

        object-fit: contain;

        border-radius: 50%;

        background: #080008;

        border:
          1px solid
          rgba(255,20,147,.5);

        box-shadow:
          0 0 18px
          rgba(255,20,147,.35);
      }

      .kb-title {
        font-size: 15px;

        font-weight: 800;

        letter-spacing: .4px;
      }

      .kb-subtitle {
        margin-top: 2px;

        font-size: 8px;

        letter-spacing: 2px;

        color:
          rgba(255,255,255,.55);
      }

      /* LIVE */

      .kb-live {
        display: flex;

        align-items: center;

        gap: 6px;

        padding:
          6px 10px;

        border-radius: 7px;

        color: white;

        font-size: 10px;

        font-weight: 900;

        letter-spacing: .7px;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #ff0066
          );

        box-shadow:
          0 0 18px
          rgba(255,20,147,.45);
      }

      .kb-live span {
        width: 6px;
        height: 6px;

        background: white;

        border-radius: 50%;

        animation:
          kbLive 1s infinite;
      }

      @keyframes kbLive {
        0%,100% {
          opacity: 1;
          transform: scale(1);
        }

        50% {
          opacity: .25;
          transform: scale(.65);
        }
      }

      /* CENTER */

      .kb-center {
        position: absolute;

        inset: 0;

        display: flex;

        align-items: center;

        justify-content: center;

        z-index: 4;

        pointer-events: none;
      }

      .kb-big-play {
        width: 76px;
        height: 76px;

        border: 1px solid
          rgba(255,255,255,.3);

        border-radius: 50%;

        color: white;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        font-size: 25px;

        cursor: pointer;

        pointer-events: auto;

        box-shadow:
          0 0 0 8px
            rgba(255,20,147,.08),
          0 0 45px
            rgba(255,20,147,.55);

        transition:
          transform .2s,
          box-shadow .2s;
      }

      .kb-big-play:hover {
        transform: scale(1.08);

        box-shadow:
          0 0 0 12px
            rgba(255,20,147,.08),
          0 0 65px
            rgba(255,20,147,.7);
      }

      /* LOADING */

      .kb-loading {
        position: absolute;

        inset: 0;

        z-index: 10;

        display: none;

        flex-direction: column;

        align-items: center;

        justify-content: center;

        gap: 12px;

        color: white;

        font-size: 12px;

        background:
          rgba(0,0,0,.4);
      }

      .kb-spinner {
        width: 40px;
        height: 40px;

        border:
          3px solid
          rgba(255,255,255,.15);

        border-top-color:
          var(--pink);

        border-right-color:
          var(--pink2);

        border-radius: 50%;

        animation:
          kbSpin 0.8s linear infinite;

        box-shadow:
          0 0 20px
          rgba(255,20,147,.4);
      }

      @keyframes kbSpin {
        to {
          transform: rotate(360deg);
        }
      }

      /* ERROR */

      .kb-error {
        position: absolute;

        inset: 0;

        z-index: 11;

        display: none;

        align-items: center;

        justify-content: center;

        text-align: center;

        color: white;

        background:
          radial-gradient(
            circle,
            #210018,
            #030003 70%
          );
      }

      .kb-error-title {
        font-size: 15px;

        font-weight: 900;

        letter-spacing: 1px;

        margin-bottom: 13px;

        color: #ff4db8;
      }

      .kb-retry {
        border: 0;

        border-radius: 7px;

        padding:
          8px 17px;

        color: white;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        cursor: pointer;

        font-weight: 700;
      }

      /* CONTROLS */

      .kb-controls {
        position: absolute;

        left: 0;
        right: 0;
        bottom: 0;

        z-index: 7;

        display: flex;

        align-items: center;

        gap: 4px;

        padding:
          35px 11px 10px;

        background:
          linear-gradient(
            transparent,
            rgba(0,0,0,.96)
          );
      }

      .kb-control {
        width: 34px;
        height: 34px;

        border: 0;

        border-radius: 8px;

        color: white;

        background:
          rgba(255,255,255,.05);

        cursor: pointer;

        font-size: 16px;

        transition:
          background .2s,
          transform .2s;
      }

      .kb-control:hover {
        background:
          rgba(255,20,147,.25);

        transform: translateY(-1px);
      }

      .kb-volume {
        width: 75px;

        accent-color:
          var(--pink);

        cursor: pointer;
      }

      .kb-live-status {
        margin-left: auto;

        display: flex;

        align-items: center;

        gap: 5px;

        color:
          #ff4db8;

        font-size: 10px;

        font-weight: 900;

        letter-spacing: .6px;
      }

      .kb-live-status i {
        width: 5px;
        height: 5px;

        border-radius: 50%;

        background:
          #ff1493;

        box-shadow:
          0 0 9px
          #ff1493;
      }

      /* QUALITY */

      .kb-quality-menu {
        position: absolute;

        right: 48px;

        bottom: 58px;

        z-index: 30;

        display: none;

        min-width: 105px;

        overflow: hidden;

        border:
          1px solid
          rgba(255,20,147,.3);

        border-radius: 10px;

        background:
          rgba(12,3,10,.98);

        box-shadow:
          0 15px 40px
          rgba(0,0,0,.7),
          0 0 25px
          rgba(255,20,147,.15);

        color: white;
      }

      .kb-quality-menu.show {
        display: block;
      }

      .kb-quality-menu div {
        padding:
          11px 15px;

        font-size: 12px;

        font-weight: 700;

        cursor: pointer;

        border-bottom:
          1px solid
          rgba(255,255,255,.05);
      }

      .kb-quality-menu div:last-child {
        border-bottom: 0;
      }

      .kb-quality-menu div:hover {
        color: white;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );
      }

      /* GLOW */

      .kb-glow {
        position: absolute;

        left: 15%;
        right: 15%;
        bottom: -20px;

        height: 35px;

        pointer-events: none;

        background:
          #ff1493;

        filter:
          blur(35px);

        opacity: .22;
      }

      /* MOBILE */

      @media(max-width:600px) {

        .kbcyber-player {
          margin: 7px auto;

          border-radius: 11px;
        }

        .kb-top {
          padding:
            10px 11px 35px;
        }

        .kb-logo {
          width: 30px;
          height: 30px;
        }

        .kb-title {
          font-size: 12px;
        }

        .kb-subtitle {
          font-size: 7px;
        }

        .kb-live {
          padding:
            5px 7px;

          font-size: 8px;
        }

        .kb-big-play {
          width: 58px;
          height: 58px;

          font-size: 20px;
        }

        .kb-volume {
          display: none;
        }

        .kb-control {
          width: 30px;
          height: 30px;

          font-size: 14px;
        }

        .kb-controls {
          padding:
            28px 7px 7px;
        }

        .kb-quality-menu {
          right: 42px;
          bottom: 49px;
        }
      }

    `;

    document.head.appendChild(style);
  }

})();
