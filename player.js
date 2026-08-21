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

  /* =========================
     LOAD HLS.JS
  ========================= */

  function loadHLS(callback) {

    if (window.Hls) {
      callback();
      return;
    }

    const s = document.createElement("script");

    s.src =
      "https://cdn.jsdelivr.net/npm/hls.js@latest";

    s.onload = callback;

    s.onerror = function () {
      console.error("KB CYBER TV: HLS.js failed.");
    };

    document.head.appendChild(s);
  }

  /* =========================
     CSS
  ========================= */

  function addCSS() {

    if (document.getElementById("kbcyber-css")) {
      return;
    }

    const style = document.createElement("style");

    style.id = "kbcyber-css";

    style.textContent = `

      .kbcyber {
        --pink:#ff1493;
        --pink2:#ff4db8;
        --dark:#080108;
        --panel:#12030e;

        width:100%;
        max-width:1150px;
        margin:15px auto;

        color:white;
        font-family:
          Arial,
          Helvetica,
          sans-serif;

        background:
          linear-gradient(
            145deg,
            #080108,
            #16000e
          );

        border:
          1px solid
          rgba(255,20,147,.25);

        border-radius:18px;

        overflow:hidden;

        box-shadow:
          0 20px 70px
          rgba(255,20,147,.18);
      }

      /* HEADER */

      .kb-header {
        display:flex;

        align-items:center;

        justify-content:space-between;

        padding:13px 15px;

        background:
          linear-gradient(
            135deg,
            #17000f,
            #080108
          );

        border-bottom:
          1px solid
          rgba(255,20,147,.15);
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

        border:
          1px solid
          rgba(255,20,147,.5);

        box-shadow:
          0 0 20px
          rgba(255,20,147,.3);
      }

      .kb-name {
        font-size:16px;
        font-weight:900;

        letter-spacing:.4px;
      }

      .kb-small {
        margin-top:2px;

        color:#ff82c8;

        font-size:8px;

        letter-spacing:2px;
      }

      .kb-live {
        display:flex;

        align-items:center;

        gap:5px;

        padding:
          6px 10px;

        border-radius:7px;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        font-size:10px;

        font-weight:900;

        box-shadow:
          0 0 20px
          rgba(255,20,147,.3);
      }

      .kb-live-dot {
        width:6px;
        height:6px;

        border-radius:50%;

        background:white;

        animation:
          kbPulse 1s infinite;
      }

      @keyframes kbPulse {
        50% {
          opacity:.2;
        }
      }

      /* PLAYER */

      .kb-player-area {
        position:relative;

        width:100%;

        aspect-ratio:16/9;

        background:#000;

        overflow:hidden;
      }

      .kb-video {
        width:100%;
        height:100%;

        display:block;

        object-fit:contain;

        background:#000;
      }

      .kb-center-play {
        position:absolute;

        inset:0;

        display:flex;

        align-items:center;

        justify-content:center;

        pointer-events:none;
      }

      .kb-big-play {
        width:72px;
        height:72px;

        border:0;

        border-radius:50%;

        color:#fff;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        font-size:25px;

        cursor:pointer;

        pointer-events:auto;

        box-shadow:
          0 0 50px
          rgba(255,20,147,.6);
      }

      .kb-loading {
        position:absolute;

        inset:0;

        display:none;

        flex-direction:column;

        align-items:center;

        justify-content:center;

        gap:12px;

        background:
          rgba(0,0,0,.45);

        z-index:10;

        font-size:12px;
      }

      .kb-spinner {
        width:38px;
        height:38px;

        border:
          3px solid
          rgba(255,255,255,.15);

        border-top-color:
          #ff1493;

        border-right-color:
          #ff4db8;

        border-radius:50%;

        animation:
          kbSpin .8s linear infinite;
      }

      @keyframes kbSpin {
        to {
          transform:rotate(360deg);
        }
      }

      /* ERROR */

      .kb-error {
        position:absolute;

        inset:0;

        display:none;

        align-items:center;

        justify-content:center;

        text-align:center;

        background:
          radial-gradient(
            circle,
            #280018,
            #030003 70%
          );

        z-index:12;
      }

      .kb-error-title {
        color:#ff4db8;

        font-weight:900;

        margin-bottom:10px;
      }

      .kb-retry {
        border:0;

        padding:
          8px 15px;

        border-radius:7px;

        color:white;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        cursor:pointer;
      }

      /* CONTROLS */

      .kb-controls {
        position:absolute;

        left:0;
        right:0;
        bottom:0;

        display:flex;

        align-items:center;

        gap:5px;

        padding:
          32px 10px 9px;

        background:
          linear-gradient(
            transparent,
            rgba(0,0,0,.95)
          );

        z-index:8;
      }

      .kb-btn {
        width:34px;
        height:34px;

        border:0;

        border-radius:7px;

        color:white;

        background:
          rgba(255,255,255,.06);

        cursor:pointer;

        font-size:15px;
      }

      .kb-btn:hover {
        background:
          rgba(255,20,147,.3);
      }

      .kb-volume {
        width:75px;

        accent-color:
          #ff1493;
      }

      .kb-live-text {
        margin-left:auto;

        color:#ff4db8;

        font-size:10px;

        font-weight:900;
      }

      /* QUALITY */

      .kb-quality-menu {
        position:absolute;

        right:45px;
        bottom:55px;

        display:none;

        min-width:100px;

        z-index:20;

        background:
          rgba(15,2,11,.98);

        border:
          1px solid
          rgba(255,20,147,.3);

        border-radius:9px;

        overflow:hidden;

        box-shadow:
          0 15px 40px
          rgba(0,0,0,.7);
      }

      .kb-quality-menu.show {
        display:block;
      }

      .kb-quality-menu div {
        padding:
          10px 14px;

        font-size:12px;

        cursor:pointer;
      }

      .kb-quality-menu div:hover {
        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );
      }

      /* CHANNEL AREA */

      .kb-channel-area {
        padding:12px;
      }

      .kb-search {
        width:100%;

        box-sizing:border-box;

        padding:
          12px 14px;

        border-radius:10px;

        outline:none;

        border:
          1px solid
          rgba(255,20,147,.2);

        background:
          #0d020a;

        color:white;

        font-size:13px;

        margin-bottom:10px;
      }

      .kb-search:focus {
        border-color:
          #ff1493;

        box-shadow:
          0 0 15px
          rgba(255,20,147,.15);
      }

      .kb-categories {
        display:flex;

        gap:6px;

        overflow-x:auto;

        padding-bottom:8px;

        scrollbar-width:none;
      }

      .kb-categories::-webkit-scrollbar {
        display:none;
      }

      .kb-cat {
        flex:none;

        border:1px solid
          rgba(255,20,147,.2);

        background:#10030c;

        color:#ff9bd2;

        padding:
          7px 11px;

        border-radius:20px;

        cursor:pointer;

        font-size:11px;

        white-space:nowrap;
      }

      .kb-cat.active,
      .kb-cat:hover {
        color:white;

        background:
          linear-gradient(
            135deg,
            #ff1493,
            #b00062
          );

        border-color:
          transparent;
      }

      /* CHANNEL GRID */

      .kb-channels {
        display:grid;

        grid-template-columns:
          repeat(
            auto-fill,
            minmax(145px,1fr)
          );

        gap:8px;

        max-height:430px;

        overflow-y:auto;

        padding-right:3px;
      }

      .kb-channel {
        display:flex;

        align-items:center;

        gap:9px;

        min-height:48px;

        padding:8px;

        border:
          1px solid
          rgba(255,20,147,.12);

        border-radius:10px;

        background:
          linear-gradient(
            145deg,
            #13030e,
            #080108
          );

        color:white;

        cursor:pointer;

        text-align:left;

        transition:
          .2s;
      }

      .kb-channel:hover {
        transform:
          translateY(-1px);

        border-color:
          rgba(255,20,147,.55);

        box-shadow:
          0 0 20px
          rgba(255,20,147,.12);
      }

      .kb-channel.active {
        border-color:
          #ff1493;

        background:
          linear-gradient(
            135deg,
            rgba(255,20,147,.22),
            #13030e
          );
      }

      .kb-channel img {
        width:32px;
        height:32px;

        object-fit:contain;

        border-radius:7px;

        background:#000;
      }

      .kb-channel-name {
        font-size:11px;

        font-weight:700;

        line-height:1.25;
      }

      .kb-empty {
        padding:30px;

        text-align:center;

        color:#ff8ccc;

        font-size:12px;
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
        }

        .kb-big-play {
          width:58px;
          height:58px;
        }

        .kb-channels {
          grid-template-columns:
            repeat(2,1fr);

          max-height:360px;
        }

        .kb-channel {
          min-height:44px;
        }

        .kb-channel img {
          width:28px;
          height:28px;
        }
      }

    `;

    document.head.appendChild(style);
  }

  /* =========================
     PARSE M3U
  ========================= */

  function parseM3U(text) {

    const lines =
      text
        .replace(/\r/g, "")
        .split("\n")
        .map(x => x.trim())
        .filter(Boolean);

    const result = [];

    let info = null;

    for (let i = 0; i < lines.length; i++) {

      const line = lines[i];

      if (
        line.startsWith("#EXTINF")
      ) {

        const namePart =
          line.substring(
            line.lastIndexOf(",") + 1
          ).trim();

        const groupMatch =
          line.match(
            /group-title="([^"]*)"/i
          );

        const logoMatch =
          line.match(
            /tvg-logo="([^"]*)"/i
          );

        info = {
          name:
            namePart ||
            "Unknown Channel",

          group:
            groupMatch
              ? groupMatch[1]
              : "Other",

          logo:
            logoMatch
              ? logoMatch[1]
              : ""
        };

        continue;
      }

      if (
        !line.startsWith("#") &&
        /^https?:\/\//i.test(line)
      ) {

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

    const root =
      document.createElement("div");

    root.className = "kbcyber";

    root.innerHTML = `

      <div class="kb-header">

        <div class="kb-brand">

          <img
            class="kb-logo"
            src="${escapeHTML(LOGO)}">

          <div>

            <div class="kb-name">
              ${escapeHTML(TITLE)}
            </div>

            <div class="kb-small">
              LIVE IPTV
            </div>

          </div>

        </div>

        <div class="kb-live">
          <span class="kb-live-dot"></span>
          LIVE
        </div>

      </div>

      <div class="kb-player-area">

        <video
          class="kb-video"
          playsinline
          preload="metadata">
        </video>

        <div class="kb-center-play">

          <button class="kb-big-play">
            ▶
          </button>

        </div>

        <div class="kb-loading">

          <div class="kb-spinner"></div>

          <span>
            Connecting...
          </span>

        </div>

        <div class="kb-error">

          <div>

            <div class="kb-error-title">
              STREAM UNAVAILABLE
            </div>

            <button class="kb-retry">
              ↻ Retry
            </button>

          </div>

        </div>

        <div class="kb-quality-menu"></div>

        <div class="kb-controls">

          <button class="kb-btn kb-play">
            ▶
          </button>

          <button class="kb-btn kb-mute">
            🔊
          </button>

          <input
            class="kb-volume"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value="1">

          <span class="kb-live-text">
            ● LIVE
          </span>

          <button
            class="kb-btn kb-quality-btn">
            ⚙
          </button>

          <button
            class="kb-btn kb-pip">
            ▣
          </button>

          <button
            class="kb-btn kb-fullscreen">
            ⛶
          </button>

        </div>

      </div>

      <div class="kb-channel-area">

        <input
          class="kb-search"
          type="search"
          placeholder="🔎 Search channels...">

        <div class="kb-categories"></div>

        <div class="kb-channels"></div>

      </div>
    `;

    script.parentNode.insertBefore(
      root,
      script
    );

    return root;
  }

  /* =========================
     PLAYER
  ========================= */

  function setupPlayer(root) {

    const video =
      root.querySelector(".kb-video");

    const play =
      root.querySelector(".kb-play");

    const bigPlay =
      root.querySelector(".kb-big-play");

    const mute =
      root.querySelector(".kb-mute");

    const volume =
      root.querySelector(".kb-volume");

    const qualityButton =
      root.querySelector(
        ".kb-quality-btn"
      );

    const qualityMenu =
      root.querySelector(
        ".kb-quality-menu"
      );

    const fullscreen =
      root.querySelector(
        ".kb-fullscreen"
      );

    const pip =
      root.querySelector(".kb-pip");

    const loading =
      root.querySelector(".kb-loading");

    const error =
      root.querySelector(".kb-error");

    const retry =
      root.querySelector(".kb-retry");

    function playPause() {

      if (video.paused) {
        video.play().catch(() => {});
      } else {
        video.pause();
      }
    }

    play.onclick = playPause;

    bigPlay.onclick = playPause;

    video.addEventListener(
      "play",
      updateButtons
    );

    video.addEventListener(
      "pause",
      updateButtons
    );

    function updateButtons() {

      play.textContent =
        video.paused
          ? "▶"
          : "❚❚";

      bigPlay.style.display =
        video.paused
          ? "flex"
          : "none";
    }

    mute.onclick = function () {

      video.muted =
        !video.muted;

      updateMute();
    };

    volume.oninput = function () {

      video.volume =
        Number(volume.value);

      video.muted =
        video.volume === 0;

      updateMute();
    };

    function updateMute() {

      mute.textContent =
        video.muted ||
        video.volume === 0
          ? "🔇"
          : "🔊";
    }

    fullscreen.onclick =
      function () {

        if (!document.fullscreenElement) {

          root
            .querySelector(
              ".kb-player-area"
            )
            .requestFullscreen?.();

        } else {

          document
            .exitFullscreen?.();

        }
      };

    pip.onclick =
      async function () {

        try {

          if (
            document.pictureInPictureElement
          ) {

            await document
              .exitPictureInPicture();

          } else {

            await video
              .requestPictureInPicture();

          }

        } catch (e) {
          console.log("PiP unavailable");
        }
      };

    qualityButton.onclick =
      function (e) {

        e.stopPropagation();

        qualityMenu
          .classList
          .toggle("show");
      };

    document.addEventListener(
      "click",
      function (e) {

        if (
          !qualityMenu.contains(e.target) &&
          !qualityButton.contains(e.target)
        ) {

          qualityMenu
            .classList
            .remove("show");
        }
      }
    );

    retry.onclick =
      function () {

        const current =
          video.dataset.url;

        if (current) {
          loadStream(current);
        }
      };

    function loadStream(url) {

      video.dataset.url = url;

      loading.style.display =
        "flex";

      error.style.display =
        "none";

      if (hls) {

        hls.destroy();

        hls = null;
      }

      if (
        window.Hls &&
        Hls.isSupported()
      ) {

        hls =
          new Hls({
            enableWorker:true,
            lowLatencyMode:true,
            liveSyncDurationCount:3,
            maxBufferLength:20,
            maxMaxBufferLength:30
          });

        hls.loadSource(url);

        hls.attachMedia(video);

        hls.on(
          Hls.Events.MANIFEST_PARSED,
          function () {

            loading.style.display =
              "none";

            video.play().catch(
              () => {}
            );

            buildQuality();
          }
        );

        hls.on(
          Hls.Events.ERROR,
          function (
            event,
            data
          ) {

            if (!data.fatal) {
              return;
            }

            loading.style.display =
              "none";

            error.style.display =
              "flex";
          }
        );

      } else if (
        video.canPlayType(
          "application/vnd.apple.mpegurl"
        )
      ) {

        video.src = url;

        video.addEventListener(
          "loadedmetadata",
          function () {

            loading.style.display =
              "none";

            video.play().catch(
              () => {}
            );

          },
          { once:true }
        );

      } else {

        loading.style.display =
          "none";

        error.style.display =
          "flex";
      }
    }

    function buildQuality() {

      qualityMenu.innerHTML = "";

      const auto =
        document.createElement("div");

      auto.textContent = "AUTO";

      auto.onclick =
        function () {

          if (hls) {
            hls.currentLevel = -1;
          }

          qualityMenu
            .classList
            .remove("show");
        };

      qualityMenu.appendChild(auto);

      if (!hls) {
        return;
      }

      hls.levels.forEach(
        function (
          level,
          index
        ) {

          const item =
            document.createElement("div");

          item.textContent =
            level.height
              ? level.height + "P"
              : "Quality " +
                (index + 1);

          item.onclick =
            function () {

              hls.currentLevel =
                index;

              qualityMenu
                .classList
                .remove("show");
            };

          qualityMenu.appendChild(item);
        }
      );
    }

    return {
      loadStream
    };
  }

  /* =========================
     CHANNEL LIST
  ========================= */

  function setupChannels(
    root,
    player
  ) {

    const search =
      root.querySelector(
        ".kb-search"
      );

    const categories =
      root.querySelector(
        ".kb-categories"
      );

    const channelBox =
      root.querySelector(
        ".kb-channels"
      );

    let activeCategory =
      "All";

    function getCategories() {

      const set =
        new Set(["All"]);

      channels.forEach(
        c => set.add(c.group)
      );

      return [...set];
    }

    function renderCategories() {

      categories.innerHTML = "";

      getCategories()
        .forEach(
          function (cat) {

            const button =
              document.createElement(
                "button"
              );

            button.className =
              "kb-cat" +
              (
                cat === activeCategory
                  ? " active"
                  : ""
              );

            button.textContent =
              cat;

            button.onclick =
              function () {

                activeCategory =
                  cat;

                renderCategories();
                renderChannels();
              };

            categories.appendChild(
              button
            );
          }
        );
    }

    function renderChannels() {

      const query =
        search.value
          .toLowerCase()
          .trim();

      channelBox.innerHTML = "";

      const filtered =
        channels.filter(
          function (channel) {

            const categoryOK =
              activeCategory === "All" ||
              channel.group ===
                activeCategory;

            const searchOK =
              !query ||
              channel.name
                .toLowerCase()
                .includes(query);

            return (
              categoryOK &&
              searchOK
            );
          }
        );

      if (!filtered.length) {

        channelBox.innerHTML =
          `
          <div class="kb-empty">
            No channels found
          </div>
          `;

        return;
      }

      filtered.forEach(
        function (channel) {

          const button =
            document.createElement(
              "button"
            );

          button.className =
            "kb-channel";

          button.innerHTML = `

            ${
              channel.logo
                ? `
                  <img
                    src="${escapeHTML(
                      channel.logo
                    )}"
                    loading="lazy">
                  `
                : `
                  <img
                    src="${escapeHTML(
                      LOGO
                    )}">
                  `
            }

            <span
              class="kb-channel-name">
              ${escapeHTML(
                channel.name
              )}
            </span>
          `;

          button.onclick =
            function () {

              root
                .querySelectorAll(
                  ".kb-channel"
                )
                .forEach(
                  x =>
                    x.classList
                      .remove("active")
                );

              button.classList.add(
                "active"
              );

              player.loadStream(
                channel.url
              );
            };

          channelBox.appendChild(
            button
          );
        }
      );
    }

    search.oninput =
      renderChannels;

    renderCategories();
    renderChannels();
  }

  /* =========================
     LOAD PLAYLIST
  ========================= */

  async function loadPlaylist(
    root,
    player
  ) {

    try {

      const response =
        await fetch(
          PLAYLIST,
          {
            cache:"no-store"
          }
        );

      if (!response.ok) {
        throw new Error(
          "Playlist HTTP " +
          response.status
        );
      }

      const text =
        await response.text();

      channels =
        parseM3U(text);

      if (!channels.length) {
        throw new Error(
          "No channels found"
        );
      }

      setupChannels(
        root,
        player
      );

      console.log(
        "KB CYBER TV:",
        channels.length,
        "channels loaded."
      );

      /* Auto play first channel */

      player.loadStream(
        channels[0].url
      );

    } catch (e) {

      console.error(
        "KB CYBER TV playlist error:",
        e
      );

      root.querySelector(
        ".kb-channels"
      ).innerHTML = `
        <div class="kb-empty">
          Unable to load playlist.
          <br><br>
          Please try again later.
        </div>
      `;
    }
  }

  /* =========================
     ESCAPE
  ========================= */

  function escapeHTML(value) {

    return String(value)

      .replace(
        /&/g,
        "&amp;"
      )

      .replace(
        /</g,
        "&lt;"
      )

      .replace(
        />/g,
        "&gt;"
      )

      .replace(
        /"/g,
        "&quot;"
      )

      .replace(
        /'/g,
        "&#039;"
      );
  }

  /* =========================
     INIT
  ========================= */

  loadHLS(
    function () {

      const root =
        createUI();

      const player =
        setupPlayer(root);

      loadPlaylist(
        root,
        player
      );
    }
  );

})();
