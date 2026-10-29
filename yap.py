#!/usr/bin/env python3
"""Yap Editor - raw talking-head video in, tight clean cut out.

  python3 yap.py cut  my-video.mp4        transcribe (WhisperX), auto-cut, open the editor
  python3 yap.py edit my-video-yap         reopen the editor for a project
  python3 yap.py render my-video-yap       render the cut without the editor
  python3 yap.py captions my-video-yap --headline "Your headline"   captions + headline (HyperFrames)

Every cut is a word you can see and click. Nothing is deleted from your original file.
"""
from difflib import SequenceMatcher
from html import escape as esc
import argparse, http.server, json, math, os, re, shutil, socketserver, subprocess, sys, threading, webbrowser

KIT = os.path.dirname(os.path.abspath(__file__))
HF = "hyperframes@0.8.140"
FILLERS = {"um", "uh", "umm", "uhh", "erm", "er", "ah", "hmm", "mm", "mhm"}
PAD_IN, PAD_OUT, JOIN = 0.10, 0.22, 0.22   # seconds kept before / after each word; gaps shorter than JOIN stay
# Whisper tends to tidy up speech. This prompt nudges it to write down the ums, uhs and stutters so they can be cut.
VERBATIM = "Umm, so, uh, I- I mean, like, you know, I was, uh, thinking... Um, okay."


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    r = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
                                  capture_output=True, text=True, check=True).stdout)
    v = next(s for s in r["streams"] if s["codec_type"] == "video")
    # phones write odd average rates (276900/11537); the nominal rate is the clean one
    num, den = v["r_frame_rate"].split("/")
    if not (0 < int(num) / max(1, int(den)) <= 120):
        num, den = v["avg_frame_rate"].split("/")
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", 0) or 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    return dict(fps=int(num) / int(den), fps_str=f"{num}/{den}", w=w, h=h, dur=float(r["format"]["duration"]))


def whisperx_bin():
    for c in (os.path.join(KIT, ".venv", "bin", "whisperx"), shutil.which("whisperx")):
        if c and os.path.exists(c):
            return c
    sys.exit("WhisperX is not installed. Run:  bash setup.sh")


norm = lambda s: re.sub(r"[^a-z0-9']", "", s.lower())


# ---------- 1. transcribe ----------
def transcribe(video, proj):
    wav = os.path.join(proj, "audio.wav")
    print("1/3  pulling the audio ...")
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000", wav])
    # a light copy for the editor: plays in any browser and seeks instantly (phone .MOV / 4K often don't)
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale='if(gt(iw,ih),-2,720)':'if(gt(iw,ih),720,-2)'", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "26", "-g", "12", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        os.path.join(proj, "preview.mp4")])
    print("2/3  WhisperX is listening (a 1-minute video takes about a minute) ...")
    log = os.path.join(proj, "whisperx.log")
    with open(log, "w") as lf:
        r = subprocess.run([whisperx_bin(), wav, "--model", os.environ.get("YAP_MODEL", "small.en"), "--language", "en",
                            "--compute_type", "int8", "--output_format", "json", "--output_dir", proj,
                            "--print_progress", "False", "--suppress_numerals", "--initial_prompt", VERBATIM], stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode != 0 or not os.path.exists(os.path.join(proj, "audio.json")):
        print(open(log).read()[-3000:])
        sys.exit(f"WhisperX stopped with an error (full log: {log})")
    raw = json.load(open(os.path.join(proj, "audio.json")))
    words = []
    for seg_i, seg in enumerate(raw["segments"]):
        for w in seg.get("words", []):
            words.append(dict(w=w["word"].strip(), a=w.get("start"), b=w.get("end"), seg=seg_i))
    # a few words come back with no time (numbers, symbols): give them their neighbours' gap
    for i, w in enumerate(words):
        if w["a"] is None:
            prev = next((x["b"] for x in reversed(words[:i]) if x["b"] is not None), 0.0)
            nxt = next((x["a"] for x in words[i + 1:] if x["a"] is not None), prev + 0.3)
            w["a"], w["b"] = prev, max(prev + 0.05, nxt)
    return [w for w in words if w["w"]]


# ---------- 2. auto-cut ----------
def lines_of(words):
    """Split the words into lines: a new line after a full stop or a pause."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt is None or re.search(r"[.?!]$", w["w"]) or nxt["a"] - w["b"] > 0.55:
            out.append(cur)
            cur = []
    return out


def autocut(words):
    for w in words:
        w["keep"], w["why"] = True, ""
    # fillers
    for w in words:
        if norm(w["w"]) in FILLERS:
            w["keep"], w["why"] = False, "filler"
    # stutters: "I I think" / "the the" / "we can we can" -> keep the last one
    # (never across a full stop: "...reads it. It listens" is not a stutter)
    toks = [norm(w["w"]) for w in words]
    ends = [bool(re.search(r"[.?!]$", w["w"])) for w in words]
    for n in (3, 2, 1):
        for i in range(len(words) - 2 * n + 1):
            if toks[i:i + n] == toks[i + n:i + 2 * n] and all(toks[i:i + n]) and not ends[i + n - 1] \
                    and all(words[k]["keep"] for k in range(i, i + n)):
                for k in range(i, i + n):
                    words[k]["keep"], words[k]["why"] = False, "repeat"
    # retakes: a line that one of the next 3 lines says again -> keep the LAST take
    L = lines_of(words)
    content = lambda line: [toks[i] for i in line if toks[i] and toks[i] not in FILLERS]
    for x, line in enumerate(L):
        a = content(line)
        if len(a) < 2:
            continue
        for y in range(x + 1, min(x + 4, len(L))):
            b = content(L[y])
            k = min(6, len(a), len(b))
            started_over = SequenceMatcher(None, a, b[:len(a)]).ratio() >= 0.75        # false start, then the full line
            same_open = k >= 3 and SequenceMatcher(None, a[:k], b[:k]).ratio() >= 0.75  # same line, said again
            if started_over or same_open:
                for i in line:
                    if words[i]["keep"]:
                        words[i]["keep"], words[i]["why"] = False, "retake"
                break
    return words


def segments(words, fps, dur):
    """Kept words -> [start, end] ranges on the source, snapped to the frame grid.
    A cut word always splits the range, and padding never reaches into a cut word."""
    segs = []
    for i, w in enumerate(words):
        if not w["keep"]:
            continue
        prev_cut = i > 0 and not words[i - 1]["keep"]
        next_cut = i + 1 < len(words) and not words[i + 1]["keep"]
        a = max(0.0, w["a"] - PAD_IN, words[i - 1]["b"] if prev_cut else 0.0)
        b = min(dur, w["b"] + PAD_OUT, words[i + 1]["a"] if next_cut else dur)
        if segs and not prev_cut and a - segs[-1][1] < JOIN:
            segs[-1][1] = max(segs[-1][1], b)
        else:
            segs.append([a, max(a, b)])
    snap_in = lambda t: math.ceil(t * fps - 1e-6) / fps     # round inwards, so a cut word never leaks back in
    snap_out = lambda t: math.floor(t * fps + 1e-6) / fps
    out = []
    for a, b in segs:
        a, b = snap_in(a), snap_out(b)
        if b - a >= 2 / fps:
            out.append([round(a, 6), round(b, 6)])
    return out


def save_edit(proj, words, meta):
    json.dump(dict(meta=meta, words=words), open(os.path.join(proj, "edit.json"), "w"), indent=1)


def load_edit(proj):
    return json.load(open(os.path.join(proj, "edit.json")))


# ---------- 3. render the cut ----------
def out_size(m):
    """1080p for social (4K phone footage drops to 1080x1920); smaller footage stays as it is."""
    w, h = m["w"], m["h"]
    s = min(1.0, 1080 / min(w, h))
    return int(round(w * s / 2) * 2), int(round(h * s / 2) * 2)


def render(proj, log=print):
    E = load_edit(proj)
    m = E["meta"]
    segs = segments(E["words"], m["fps"], m["dur"])
    if not segs:
        raise SystemExit("Every word is cut, so there is nothing to render. Bring some words back first.")
    src = m["video"]
    W_, H_ = out_size(m)
    out = os.path.join(proj, "cut.mp4")
    log(f"rendering {len(segs)} pieces ...")
    parts, labels = [], []
    for i, (a, b) in enumerate(segs):
        d = b - a
        fo = max(0.0, d - 0.012)
        parts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];"
                     f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,afade=t=in:d=0.012,afade=t=out:st={fo:.4f}:d=0.012[a{i}];")
        labels.append(f"[v{i}][a{i}]")
    fc = "".join(parts) + "".join(labels) + f"concat=n={len(segs)}:v=1:a=1[vc][a];[vc]scale={W_}:{H_},setsar=1[v];[a]loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
    script = os.path.join(proj, ".filter.txt")
    open(script, "w").write(fc)
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-filter_complex_script", script,
        "-map", "[v]", "-map", "[ao]", "-r", m["fps_str"], "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out])
    before, after = m["dur"], sum(b - a for a, b in segs)
    log(f"done: {before:.1f}s -> {after:.1f}s  ({out})")
    return out


# ---------- 4. captions + headline (HyperFrames) ----------
def cut_time(segs):
    """source time -> time in the cut"""
    def f(t):
        acc = 0.0
        for a, b in segs:
            if t < a:
                return acc
            if t <= b:
                return acc + (t - a)
            acc += b - a
        return acc
    return f


def captions(proj, headline="", log=print):
    E = load_edit(proj)
    m = E["meta"]
    cut = os.path.join(proj, "cut.mp4")
    if not os.path.exists(cut) or os.path.getmtime(cut) < os.path.getmtime(os.path.join(proj, "edit.json")):
        render(proj, log)   # no cut yet, or words changed since the last render
    segs = segments(E["words"], m["fps"], m["dur"])
    f = cut_time(segs)
    dur = round(sum(b - a for a, b in segs), 3)
    W = [dict(w=w["w"], a=round(f(w["a"]), 3), b=round(f(w["b"]), 3)) for w in E["words"] if w["keep"]]
    # 3 words per caption, new caption at a full stop
    G, cur = [], []
    for i, w in enumerate(W):
        cur.append(w)
        if re.search(r"[.?!,]$", w["w"]) or len(cur) == 3 or i == len(W) - 1:
            G.append(cur)
            cur = []
    hf = os.path.join(proj, "hyperframes")
    os.makedirs(os.path.join(hf, "assets"), exist_ok=True)
    shutil.copy(cut, os.path.join(hf, "assets", "cut.mp4"))
    sh(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", cut, "-vn", "-ac", "2", "-ar", "48000", os.path.join(hf, "assets", "cut.wav")])
    W_, H_ = out_size(m)
    vertical = H_ > W_
    fs = int((W_ if vertical else H_) * (0.075 if vertical else 0.07))
    cap_top = int(H_ * (0.68 if vertical else 0.78))
    head_top = int(H_ * (0.12 if vertical else 0.07))
    caps_html, caps_js = [], []
    for gi, g in enumerate(G):
        a = g[0]["a"]
        b = min(g[-1]["b"] + 0.2, G[gi + 1][0]["a"]) if gi + 1 < len(G) else dur
        spans = "".join(f'<i id="w{gi}_{k}">{esc(x["w"].rstrip(","))}</i> ' for k, x in enumerate(g))
        caps_html.append(f'      <div class="cap" id="c{gi}"><span>{spans.strip()}</span></div>')
        caps_js.append(f'tl.set("#c{gi}",{{opacity:1}},{a});tl.set("#c{gi}",{{opacity:0}},{b:.3f});')
        for k, x in enumerate(g):
            caps_js.append(f'tl.set("#w{gi}_{k}",{{color:"#FFD43B"}},{x["a"]});'
                           f'tl.set("#w{gi}_{k}",{{color:"#ffffff"}},{min(x["b"], b):.3f});')
    head = ""
    if headline.strip():
        head = (f'      <div id="head" class="clip" data-start="0" data-duration="{dur}" data-track-index="3">'
                f'<div class="head"><span>{esc(headline.strip())}</span></div></div>')
    html = open(os.path.join(KIT, "hyperframes", "index.template.html")).read()
    for k, v in dict(DUR=dur, W=W_, H=H_, RES="portrait" if vertical else "landscape", FS=fs, CAPTOP=cap_top,
                     HEADTOP=head_top, HFS=int(fs * 1.05), HEAD=head, CAPS="\n".join(caps_html),
                     CAPSJS="\n      ".join(caps_js)).items():
        html = html.replace("{{%s}}" % k, str(v))
    open(os.path.join(hf, "index.html"), "w").write(html)
    for name in ("hyperframes.json", "package.json"):
        shutil.copy(os.path.join(KIT, "hyperframes", name), os.path.join(hf, name))
    out = os.path.join(proj, "final.mp4")
    log("HyperFrames is drawing the captions (takes a minute or two) ...")
    sh(["npx", "--yes", HF, "render", "-o", out, "--quiet", "--fps", m["fps_str"], "--crf", "20"], cwd=hf)
    log(f"done: {out}")
    return out


# ---------- the editor (a page on your own computer) ----------
class Handler(http.server.SimpleHTTPRequestHandler):
    proj = None
    status = {"busy": False, "msg": "ready"}

    def log_message(self, *a):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/":
            return self._file(os.path.join(KIT, "editor.html"), "text/html")
        if p == "/edit.json":
            return self._file(os.path.join(self.proj, "edit.json"), "application/json")
        if p == "/status":
            return self._json(self.status)
        if p in ("/source", "/cut.mp4", "/final.mp4"):
            if p == "/source":
                f = os.path.join(self.proj, "preview.mp4")
                if not os.path.exists(f):
                    f = load_edit(self.proj)["meta"]["video"]
            else:
                f = os.path.join(self.proj, p[1:])
            return self._file(f, "video/mp4")
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/save":
            E = load_edit(self.proj)
            for w, k in zip(E["words"], body["keep"]):
                w["keep"] = bool(k)
            save_edit(self.proj, E["words"], E["meta"])
            return self._json({"ok": True})
        if self.path in ("/render", "/captions"):
            if self.status["busy"]:
                return self._json({"ok": False, "msg": "already working"})
            job = self.path[1:]

            def run():
                Handler.status = {"busy": True, "msg": "working ..."}
                try:
                    log = lambda s: Handler.status.update(msg=s)
                    out = render(self.proj, log) if job == "render" else captions(self.proj, body.get("headline", ""), log)
                    Handler.status = {"busy": False, "msg": "done", "file": "/" + os.path.basename(out)}
                except BaseException as e:
                    Handler.status = {"busy": False, "msg": f"failed: {e}"}
            threading.Thread(target=run, daemon=True).start()
            return self._json({"ok": True})
        self.send_error(404)

    def _json(self, d):
        b = json.dumps(d).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _file(self, path, ctype):
        if not os.path.exists(path):
            return self.send_error(404)
        size = os.path.getsize(path)
        rng = self.headers.get("Range")
        a, b = 0, size - 1
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            a = int(m.group(1) or 0)
            b = int(m.group(2)) if m.group(2) else size - 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with open(path, "rb") as fh:
            fh.seek(a)
            left = b - a + 1
            try:
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass


def edit(proj, port=8765, open_browser=True):
    Handler.proj = os.path.abspath(proj)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler) as srv:
        url = f"http://localhost:{port}"
        print(f"\nThe editor is open at {url}   (press Ctrl+C here to close it)\n")
        if open_browser:
            webbrowser.open(url)
        srv.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="Yap Editor")
    ap.add_argument("cmd", choices=["cut", "edit", "render", "captions"])
    ap.add_argument("target")
    ap.add_argument("--headline", default="")
    ap.add_argument("--no-editor", action="store_true", help="just render the auto-cut, skip the editor")
    ap.add_argument("--no-browser", action="store_true", help="start the editor without opening a browser tab")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.cmd == "cut":
        video = os.path.abspath(a.target)
        proj = os.path.splitext(video)[0] + "-yap"
        os.makedirs(proj, exist_ok=True)
        m = probe(video)
        words = transcribe(video, proj)
        if not words:
            sys.exit("WhisperX didn't hear any talking in this video. Yap Editor is for talking-to-camera videos.")
        words = autocut(words)
        m.update(video=video, name=os.path.basename(video))
        save_edit(proj, words, m)
        cut = sum(1 for w in words if not w["keep"])
        print(f"3/3  auto-cut: {len(words)} words, {cut} marked to cut (fillers, repeats, retakes)")
        if a.no_editor:
            render(proj)
        else:
            edit(proj, a.port, not a.no_browser)
    elif a.cmd == "edit":
        edit(a.target, a.port, not a.no_browser)
    elif a.cmd == "render":
        render(a.target)
    else:
        captions(a.target, a.headline)


if __name__ == "__main__":
    main()
