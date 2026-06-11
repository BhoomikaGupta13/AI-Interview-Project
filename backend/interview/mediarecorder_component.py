import streamlit.components.v1 as components
import datetime


def media_recorder_component(
    session_id: str,
    question_no: int,
    recording: bool,
    max_seconds: int | None = None,
    proctoring_active: bool = True,
):
    q_key = f"{session_id}_q{question_no}"
    should_record = str(recording).lower()
    should_proctor = str(proctoring_active).lower()
    seconds = max_seconds or 0

    html = f"""
    <div id="interviewBox" style="display:flex;flex-direction:column;align-items:center;
                background:#111;border-radius:12px;padding:10px;
                width:100%;max-width:520px;margin:0 auto;position:relative;">
      <video id="preview" autoplay muted playsinline
        style="width:400px;height:300px;object-fit:cover;
               border-radius:10px;background:#000;display:block;">
      </video>

      <div id="overlay"
        style="display:none;position:absolute;inset:10px;background:rgba(0,0,0,0.88);
               color:#fff;border-radius:10px;align-items:center;justify-content:center;
               flex-direction:column;text-align:center;font-family:Arial,sans-serif;padding:18px;z-index:10;">
        <div id="overlayText" style="font-size:15px;line-height:1.4;margin-bottom:12px;"></div>
        <button id="fullscreenBtn"
          style="background:#f8fafc;color:#111;border:0;border-radius:6px;padding:9px 14px;
                 font-weight:700;cursor:pointer;">
          Enter fullscreen
        </button>
      </div>

      <div id="timerBar"
        style="width:400px;color:#fff;font-size:15px;font-family:monospace;
               padding:7px 10px;background:#7f1d1d;box-sizing:border-box;">
        Answer Time: {seconds}s
      </div>
      <div id="proctorBar"
        style="width:400px;color:#fff;font-size:12px;font-family:monospace;
               padding:6px 10px;background:#1f2937;box-sizing:border-box;">
        Proctoring ready
      </div>
      <div id="statusBar"
        style="width:400px;color:#fff;font-size:12px;font-family:monospace;
               padding:6px 10px;border-radius:0 0 10px 10px;min-height:26px;
               background:rgba(0,0,0,0.75);word-break:break-all;box-sizing:border-box;">
        Starting...
      </div>
      <button id="stopBtn"
        style="display:none;margin-top:8px;background:#f8fafc;color:#111;border:0;
               border-radius:6px;padding:8px 12px;font-weight:700;cursor:pointer;">
        Stop recording
      </button>
    </div>

    <script>
    (function() {{
      if (!window.__REC__) window.__REC__ = {{}};
      const KEY = "{q_key}";
      if (!window.__REC__[KEY]) {{
        window.__REC__[KEY] = {{
        stream:null,
        recorder:null,
        active:false,
        camReady:false,
        chunkNo:0,
      
        countdownTimer:null,
        stopTimer:null,
      
        started:false,
      
        lastTabEventAt:0,
      
        lastFullscreenEventAt:0,
      
        lastFullscreenReportAt:0,
        stableFaceState:"unknown",
        pendingFaceState:"ok",
        pendingFaceFrames:0,
        faceDetectInFlight:false,
        faceEventInFlight:false
      
      }};
      }}

      const R = window.__REC__[KEY];
      const SESSION = "{session_id}";
      const QUESTION = "{question_no}";
      const SHOULD_RECORD = {should_record};
      const SHOULD_PROCTOR = {should_proctor};
      const MAX_SECONDS = {seconds};
      const API = "http://127.0.0.1:5001";

      let faceTimer=null;
      const preview = document.getElementById("preview");
      const faceCanvas=document.createElement("canvas");
      const faceCtx=faceCanvas.getContext("2d");
      const timerBar = document.getElementById("timerBar");
      const proctorBar = document.getElementById("proctorBar");
      const statusBar = document.getElementById("statusBar");
      const stopBtn = document.getElementById("stopBtn");
      const overlay = document.getElementById("overlay");
      const overlayText = document.getElementById("overlayText");
      const fullscreenBtn = document.getElementById("fullscreenBtn");

      function status(msg, bg) {{
        if (!statusBar) return;
        statusBar.textContent = msg;
        statusBar.style.background = bg || "rgba(0,0,0,0.75)";
        console.log("[Recorder]", msg);
      }}

      function proctor(msg, bg) {{
        if (!proctorBar) return;
        proctorBar.textContent = msg;
        proctorBar.style.background = bg || "#1f2937";
      }}

      function updateProctorDisplay(p) {{
        if (!p) return;
        proctor(
          "Warnings | fullscreen: "
          + (p.fullscreen_warnings || 0)
          + "/2 | tab: "
          + (p.tab_warnings || 0)
          + "/3 | face: "
          + (p.face_warnings || 0)
          + " | device: "
          + (p.phone_warnings || 0), // Clear layout addition to track phone status live

          p.locked
          ?
          "#991b1b"
          :
          "#1f2937"
          );
      }}

      function showOverlay(msg, showButton) {{
        overlayText.textContent = msg;
        fullscreenBtn.style.display = showButton ? "block" : "none";
        overlay.style.display = "flex";
      }}

      function hideOverlay() {{
        overlay.style.display = "none";
      }}

      function appDocument() {{
        try {{
          if (window.parent && window.parent.document) return window.parent.document;
        }} catch(err) {{}}
        return document;
      }}

      function appFullscreenElement() {{
        const doc = appDocument();
        return doc.fullscreenElement ||
               doc.webkitFullscreenElement ||
               doc.msFullscreenElement ||
               null;
      }}

      async function requestAppFullscreen() {{
        const doc = appDocument();
        const target = doc.documentElement;
        if (appFullscreenElement()) return true;
        if (target.requestFullscreen) await target.requestFullscreen();
        else if (target.webkitRequestFullscreen) await target.webkitRequestFullscreen();
        else if (target.msRequestFullscreen) await target.msRequestFullscreen();
        else return false;
        return !!appFullscreenElement();
      }}

      function hidePageGate() {{
        try {{
          const gate = appDocument().getElementById("fullscreenGateOverlay");
          if (gate) gate.remove();
        }} catch(err) {{}}
      }}

      function showPageGate(message) {{
        try {{
          const doc = appDocument();
          let gate = doc.getElementById("fullscreenGateOverlay");
          if (!gate) {{
            gate = doc.createElement("div");
            gate.id = "fullscreenGateOverlay";
            gate.style.position = "fixed";
            gate.style.inset = "0";
            gate.style.zIndex = "2147483647";
            gate.style.background = "rgba(8, 13, 23, 0.96)";
            gate.style.color = "#fff";
            gate.style.display = "flex";
            gate.style.alignItems = "center";
            gate.style.justifyContent = "center";
            gate.style.flexDirection = "column";
            gate.style.textAlign = "center";
            gate.style.fontFamily = "Arial, sans-serif";
            gate.style.padding = "24px";

            const text = doc.createElement("div");
            text.id = "fullscreenGateText";
            text.style.maxWidth = "560px";
            text.style.fontSize = "18px";
            text.style.lineHeight = "1.45";
            text.style.marginBottom = "16px";

            const button = doc.createElement("button");
            button.textContent = "Enter fullscreen";
            button.style.background = "#f8fafc";
            button.style.color = "#111827";
            button.style.border = "0";
            button.style.borderRadius = "6px";
            button.style.padding = "10px 16px";
            button.style.fontWeight = "700";
            button.style.cursor = "pointer";
            button.addEventListener("click", enterFullscreenAndStart);

            gate.appendChild(text);
            gate.appendChild(button);
            doc.body.appendChild(gate);
          }}
          doc.getElementById("fullscreenGateText").textContent = message;
        }} catch(err) {{
          showOverlay(message, true);
        }}
      }}

      async function reportEvent(eventType, details) {{
        try {{
          const r = await fetch(API + "/proctor_event", {{
    method:"POST",

    keepalive:true,

    headers:{{
        "Content-Type":"application/json"
    }},

    body:JSON.stringify({{
        session:SESSION,
        question:QUESTION,
        event_type:eventType,
        details:details||{{}}
    }})
}});
          const j = await r.json();
          if (j.status === "success") {{
            const p = j.proctor;
            updateProctorDisplay(p);
        if (p.locked) {{
              stopRecording();
              stopCamera();
              hidePageGate();
              showOverlay(p.lock_reason || "Interview locked.", false);
            }}
          }}
        }} catch(err) {{
          console.error("[Proctor] event failed", err);
        }}
      }}

      async function getProctorStatus() {{
        try {{
          const r = await fetch(API + "/proctor_status?session=" + encodeURIComponent(SESSION));
          const j = await r.json();
          if (j.status === "success") {{
            updateProctorDisplay(j.proctor);
            if (j.proctor.locked) {{
              stopCamera();
              showOverlay(j.proctor.lock_reason || "Interview locked.", false);
              return false;
            }}
          }}
        }} catch(err) {{
          console.error("[Proctor] status failed", err);
        }}
        return true;
      }}

      function getBestMime() {{
        const candidates = [
          "video/webm;codecs=vp8,opus",
          "video/webm;codecs=vp9,opus",
          "video/webm;codecs=h264,opus",
          "video/webm"
        ];
        for (const m of candidates) {{
          if (MediaRecorder.isTypeSupported(m)) return m;
        }}
        return "";
      }}

      async function openCamera() {{
        if (R.camReady && R.stream) {{
          preview.srcObject = R.stream;
          return;
        }}
        try {{
          R.stream = await navigator.mediaDevices.getUserMedia({{
            video: {{ width: 640, height: 480, facingMode: "user" }},
            audio: {{
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
              channelCount: 1,
              sampleRate: 48000,
              sampleSize: 16
            }}
          }});
          preview.srcObject = R.stream;
          R.camReady = true;

          const aTracks = R.stream.getAudioTracks();
          if (aTracks.length === 0) {{
            status("Camera ready but no microphone track.", "rgba(150,80,0,0.85)");
          }} else {{
            status("Camera and microphone ready.", "rgba(0,100,0,0.85)");
          }}
        }} catch(err) {{
          status("Camera/Mic error: " + err.message, "rgba(150,0,0,0.85)");
        }}
      }}

      function stopCamera(){{

      if(faceTimer){{
      
      clearInterval(faceTimer);
      
      faceTimer=null;
      
      }}
      
      if(!R.stream)return;
      
      R.stream.getTracks().forEach(t=>t.stop());
      
      R.stream=null;
      
      R.camReady=false;
      
      }}

      async function uploadChunk(blob, n) {{
        const form = new FormData();
        form.append("session", SESSION);
        form.append("question", QUESTION);
        form.append("chunk_num", String(n));
        form.append("chunk", blob, "c.webm");

        try {{
          const r = await fetch(API + "/append_chunk", {{ method: "POST", body: form }});
          if (!r.ok) {{
            status("Upload failed: server " + r.status, "rgba(150,0,0,0.85)");
            return;
          }}
          const j = await r.json();
          if (j.status === "success") {{
            status("Chunk " + n + " saved | " + j.total_kb + " KB", "rgba(0,110,0,0.85)");
          }}
        }} catch(err) {{
          status("Upload failed. Is FastAPI running on 5001?", "rgba(150,0,0,0.85)");
        }}
      }}

      function updateCountdown(endAt) {{
        const left = Math.max(0, Math.ceil((endAt - Date.now()) / 1000));
        timerBar.textContent = "Answer Time Left: " + left + "s";
        if (left <= 10) timerBar.style.background = "#991b1b";
        else if (left <= 30) timerBar.style.background = "#92400e";
        else timerBar.style.background = "#166534";
      }}

      function startCountdown() {{
        if (!MAX_SECONDS) return;
        const endAt = Date.now() + MAX_SECONDS * 1000;
        updateCountdown(endAt);
        clearInterval(R.countdownTimer);
        R.countdownTimer = setInterval(() => updateCountdown(endAt), 250);
        clearTimeout(R.stopTimer);
        R.stopTimer = setTimeout(() => {{
          status("Time limit reached. Saving recording...", "rgba(120,80,0,0.85)");
          stopRecording();
        }}, MAX_SECONDS * 1000);
      }}

      function startRecording() {{
        if (R.active || !R.camReady) return;

        const aTracks = R.stream.getAudioTracks();
        if (aTracks.length > 0) aTracks[0].enabled = true;

        const options = {{}};
        const mime = getBestMime();
        if (mime) options.mimeType = mime;
        options.audioBitsPerSecond = 192000;
        options.videoBitsPerSecond = 2500000;

        try {{
          R.recorder = new MediaRecorder(R.stream, options);
        }} catch(err) {{
          R.recorder = new MediaRecorder(R.stream);
        }}

        R.active = true;
        R.started = true;
        if (R.chunkNo === 0) R.chunkNo = 0;

        R.recorder.ondataavailable = (e) => {{
          if (!e.data || e.data.size === 0) return;
          R.chunkNo += 1;
          uploadChunk(e.data, R.chunkNo);
        }};

        R.recorder.onstop = () => {{
          stopBtn.style.display = "none";
          clearInterval(R.countdownTimer);
          clearTimeout(R.stopTimer);
          timerBar.textContent = "Answer saved";
          timerBar.style.background = "#1f2937";
          status("Done. " + R.chunkNo + " chunks saved.", "rgba(0,80,0,0.85)");
        }};

        R.recorder.start(1000);
        hideOverlay();
        startCountdown();
        stopBtn.style.display = "block";
        status("Recording Q" + QUESTION + " | audio ON", "rgba(160,0,0,0.85)");
      }}

      function stopRecording() {{
        if (!R.active) return;
        R.active = false;
        if (R.recorder && R.recorder.state !== "inactive") {{
          try {{ R.recorder.requestData(); }} catch(err) {{}}
          R.recorder.stop();
        }}
      }}

      async function enterFullscreenAndStart() {{
        try {{
          await requestAppFullscreen();
        }} catch(err) {{
          showOverlay("Fullscreen is required for the interview. Please allow fullscreen.", true);
          return;
        }}
        if (appFullscreenElement()) {{
          hidePageGate();
          hideOverlay();
        }}
        if (appFullscreenElement() && SHOULD_RECORD) startRecording();
      }}

      fullscreenBtn.addEventListener("click", enterFullscreenAndStart);
      stopBtn.addEventListener("click", stopRecording);

      function onFullscreenChange() {{
        if (!SHOULD_PROCTOR) return;
        const now = Date.now();
        R.lastFullscreenEventAt = now;
        if (!appFullscreenElement()) {{
          if (now - R.lastFullscreenReportAt < 1500) return;
          R.lastFullscreenReportAt = now;
          reportEvent("fullscreen_exit", {{ message: "Candidate exited fullscreen" }});
          showPageGate("Warning: fullscreen was exited. Enter fullscreen to continue.");
          showOverlay("Warning: fullscreen was exited. Enter fullscreen to continue.", true);
          stopRecording();
        }} else {{
          hidePageGate();
          hideOverlay();
        }}
      }}

      document.addEventListener("fullscreenchange", onFullscreenChange);
      try {{
        appDocument().addEventListener("fullscreenchange", onFullscreenChange);
      }} catch(err) {{}}

      function reportTabSwitch(reason){{

      if(!SHOULD_PROCTOR)
      return;

      const now=Date.now();

      if(
      now-R.lastTabEventAt<2000
      )
      return;

      R.lastTabEventAt=now;

      reportEvent(
      "tab_switch",
      {{
      message:
      "Candidate switched tab, minimized window, or changed app focus",

      reason:reason
      }}
      );

      }}

      function onVisibilityChange(){{
      
      const doc=appDocument();

      if(doc.hidden){{
      
      reportTabSwitch(
      "document_hidden"
      );

      }}

      }}

      function onWindowBlur(){{
      
      setTimeout(()=>{{
      
      const doc=appDocument();

      if(
      doc.hasFocus
      &&
      !doc.hasFocus()
      ){{
      
      reportTabSwitch(
      "window_blur"
      );

      }}

      }},300);

      }}

      try{{
      
      appDocument().addEventListener(
      "visibilitychange",
      onVisibilityChange
      );

      window.addEventListener(
      "blur",
      onWindowBlur
      );

      }}catch(err){{}}

      
      async function detectFaces() {{
          if (!SHOULD_PROCTOR || !preview.videoWidth || R.faceDetectInFlight) return;
          R.faceDetectInFlight = true;

          faceCanvas.width = 320;
          faceCanvas.height = 240;
          faceCtx.drawImage(preview, 0, 0, 320, 240);

          faceCanvas.toBlob(async(blob) => {{
              if (!blob) {{
                  R.faceDetectInFlight = false;
                  return;
              }}
              const form = new FormData();
              form.append("session", SESSION);
              form.append("frame", blob, "f.jpg");

              try {{
                  const r = await fetch(API + "/detect_faces", {{
                      method: "POST",
                      body: form
                  }});

                  const j = await r.json();

                  if (j.status !== "success") {{
                      R.faceDetectInFlight = false;
                      return;
                  }}

                  // ── Phone detection (evaluated every frame, no debounce needed) ──
                  if (j.phone_detected) {{
                      proctor("⚠ Unauthorized device detected! (flags: " + (j.proctor.phone_warnings || 1) + ")", "#92400e");
                  }}

                  // ── Update full proctor display if server returned snapshot ──
                  if (j.proctor) {{
                      updateProctorDisplay(j.proctor);
                      if (j.proctor.locked && !j.phone_detected) {{
                          stopRecording();
                          stopCamera();
                          hidePageGate();
                          showOverlay(j.proctor.lock_reason || "Interview locked.", false);
                          R.faceDetectInFlight = false;
                          return;
                      }}
                  }}

                  // ── Face state machine (debounced to 4 stable frames) ──
                  let state = "ok";
                  if (j.faces === 0) state = "no_face";
                  else if (j.faces > 1) state = "multiple_faces";

                  // Correctly escaped braces here
                  if (state !== R.pendingFaceState) {{
                      R.pendingFaceState = state;
                      R.pendingFaceFrames = 1;
                  }} else {{
                      R.pendingFaceFrames++;
                  }}

                  if (R.pendingFaceFrames < 4) return;

                  if (state === R.stableFaceState) return;

                  R.stableFaceState = state;

                  if (state === "ok") {{
                      R.faceEventInFlight = true;
                      await reportEvent("face_ok", {{ count: j.faces }});
                      R.faceEventInFlight = false;
                  }} else if (state === "no_face") {{
                      R.faceEventInFlight = true;
                      await reportEvent("no_face", {{ count: j.faces }});
                      R.faceEventInFlight = false;
                  }} else if (state === "multiple_faces") {{
                      R.faceEventInFlight = true;
                      await reportEvent("multiple_faces", {{ count: j.faces }});
                      R.faceEventInFlight = false;
                  }}
              }} catch(e) {{
                  console.error("[Face] Detection failed", e);
              }} finally {{
                  R.faceEventInFlight = false;
                  R.faceDetectInFlight = false;
              }}
          }}, "image/jpeg", 0.7);
      }}


      async function setup() {{
        const allowed = await getProctorStatus();
        if (!allowed) return;

        await openCamera();
        if(!faceTimer)faceTimer=setInterval(detectFaces,300);
        if (SHOULD_PROCTOR) {{
          if (!appFullscreenElement()) {{
            showPageGate("Fullscreen is required before questions are shown. Reading and answering are both monitored.");
            showOverlay("Fullscreen is required before questions are shown.", true);
            try {{
              await requestAppFullscreen();
            }} catch(err) {{
              status("Click Enter fullscreen to continue.", "#92400e");
              return;
            }}
          }}
          hidePageGate();
          hideOverlay();
        }}

        if (SHOULD_RECORD) {{
          timerBar.textContent = "Answer Time Left: " + MAX_SECONDS + "s";
          if (appFullscreenElement()) {{
            startRecording();
          }} else {{
            showOverlay("Fullscreen is required before answering.", true);
            try {{
              await requestAppFullscreen();
              if (appFullscreenElement()) startRecording();
            }} catch(err) {{
              status("Click Enter fullscreen to begin recording.", "#92400e");
            }}
          }}
        }} else {{
          timerBar.textContent = "Answer Time: " + MAX_SECONDS + "s";
          if (R.active) stopRecording();
        }}
      }}

      setup();
    }})();
    </script>
    """

    components.html(html, height=430)
