# 🎙️ Yap Editor

**Talk to the camera. Get back a clean video with captions.**

A free gift from **Benza** and **@thoseaiguys** 🎁

> 🔥 **Want AI to run ALL your marketing?** Join **Benza** live in the AI Marketing Sprint, or hire him to set it up for you.
> **[Join the Sprint →](https://sprint.benzamaman.com/?utm_source=github&utm_medium=owned&utm_campaign=sprint-close&utm_content=yap-editor-top)** · **Hire Benza: [benza@benzamaman.com](mailto:benza@benzamaman.com?subject=I%20want%20to%20work%20with%20you)**

![The Yap Editor](docs/editor.png)

---

## ✅ 3 steps. That's it.

### 1️⃣ Get Claude Code

You need a **Mac** and **Claude Code**. Don't have it? Get it here: **[claude.com/claude-code](https://claude.com/claude-code)**

### 2️⃣ Copy this. Paste it into Claude Code.

```
Install the Yap Editor from https://github.com/EnergySteve/yap-editor into ~/.claude/skills/yap-editor, run its setup.sh, then show me how to use it.
```

Claude sets it all up for you. It takes about 10 minutes the first time.

### 3️⃣ Drop in your video. Type: **yap this**

Claude listens to your video. Then a page opens with your video and your words.

> 💡 **Stuck?** Ask Benza. Reply to any of his emails, or write to **benza@benzamaman.com**.

---

## 🖱️ How to use the page

- ❌ **Crossed-out words are cut.** Claude already cut your "ums" and your redos.
- 🖱️ **Click a word** to cut it. **Click it again** to bring it back.
- ▶️ **Press "Preview the cut"** to watch it.
- 🎬 **Press "Render the cut"** to make your video.
- 💬 **Type a headline. Press "Add captions."** Now it has captions too. 🎉

Your new videos show up in a folder next to your old one.

> 🚀 **Made your first video?** Now let AI post it, write your emails and bring you leads. Benza shows you how. **[Join the Sprint →](https://sprint.benzamaman.com/?utm_source=github&utm_medium=owned&utm_campaign=sprint-close&utm_content=yap-editor-first-video)**

---

## 💡 Tips

- 🔁 **Messed up? Just say it again.** It keeps your last try.
- ⏸️ **Take a breath** before you try again.
- ✍️ **Short headlines work best.** 6 words or less.

---

## 🔥 Want AI to do ALL your marketing?

This editor is just one small thing AI can do for you. AI can also:

- ✍️ Write your posts and emails
- 🎬 Plan and edit your videos
- 📣 Run your ads
- 🤝 Follow up with your leads

### Two ways to get it done with Benza:

| | |
|---|---|
| 👥 **Join the Sprint** | Build it **with** Benza, live, step by step. Seats are limited. **[Join now →](https://sprint.benzamaman.com/?utm_source=github&utm_medium=owned&utm_campaign=sprint-close&utm_content=yap-editor-readme)** |
| 🤝 **Hire Benza** | Want it done **for** you? Email **[benza@benzamaman.com](mailto:benza@benzamaman.com?subject=I%20want%20to%20work%20with%20you)** and tell him about your business. |

---

## 💬 Questions?

**Ask Benza anything.** Reply to any of his emails, or write to **benza@benzamaman.com**. No question is too small.

---

<details>
<summary>🛠️ For techy people (you can skip this)</summary>

**What's inside:** WhisperX hears every word and when you said it. ffmpeg cuts the video. HyperFrames draws the captions. It all runs on your own computer. Nothing is uploaded. Your first video is never changed.

**Install by hand:**

```bash
git clone https://github.com/EnergySteve/yap-editor ~/.claude/skills/yap-editor
bash ~/.claude/skills/yap-editor/setup.sh
```

**Use it without Claude:**

```bash
python3 yap.py cut my-video.mov                              # cut + open the page
python3 yap.py edit my-video-yap                             # open the page again
python3 yap.py render my-video-yap                           # make the video
python3 yap.py captions my-video-yap --headline "Hook here"  # add captions
```

**If something goes wrong:**

| Problem | Fix |
|---|---|
| "WhisperX is not installed" | Run `bash setup.sh` |
| "Homebrew isn't installed" | Paste the line it shows you into Terminal. Then run `bash setup.sh` again. |
| The first video is slow | It's downloading about 1 GB, one time only. |
| "didn't hear any talking" | This is for talking videos only. |
| The page won't open | Go to **http://localhost:8765** |
| A cut word still sneaks through | Cut the word next to it too. |
| Anything else | Email **benza@benzamaman.com** |

Built with [WhisperX](https://github.com/m-bain/whisperX), [ffmpeg](https://ffmpeg.org) and [HyperFrames](https://github.com/heygen-com/hyperframes).

</details>

---

Made with ⚡ by **@thoseaiguys** for the Claude Content & Marketing Masterclass with **Benza**.
**[Join Benza's Sprint →](https://sprint.benzamaman.com/?utm_source=github&utm_medium=owned&utm_campaign=sprint-close&utm_content=yap-editor-footer)** · **[Hire Benza →](mailto:benza@benzamaman.com?subject=I%20want%20to%20work%20with%20you)**
