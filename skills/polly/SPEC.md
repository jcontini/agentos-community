# Polly — Spec

> "Polly wanna cracker?"
> Status: **Planned** — not yet implemented.
> Date: 2026-03-24

---

## What It Is

Polly is a Mac menu bar app that lets you trigger voice dictation using sounds instead of keyboard shortcuts. Click your tongue to start, click again to stop. Say "never mind" to cancel. No hands required.

It wraps [parrot.py](https://github.com/chaosparrot/parrot.py) (MIT) with a proper Mac app: menu bar icon, a guided training wizard, and a native-quality UI backed by a local webview.

---

## The Problem It Solves

Every voice dictation app on Mac requires a keyboard shortcut to start and stop. That means:
- Your hands have to leave what they're doing
- Shortcuts conflict with other apps
- You need a free hand or a free key

Polly replaces the keyboard shortcut with a sound you make — a mouth click, a pop, a hiss — trained specifically to your voice. Completely hands-free, no conflicts.

---

## Core Behavior

| Sound | State | Action |
|-------|-------|--------|
| Click (mouth) | Idle | Start dictation — send START key to dictation app |
| Click (mouth) | Recording | Stop + submit — send STOP key |
| "Never mind" | Recording | Cancel — send Escape |

Toggle state lives in memory. One boolean. No server.

```
idle → [click] → recording → [click] → idle
                           → [never mind] → idle
```

The dictation app (Vówen, Whisper, Apple Dictation, anything) is just receiving keystrokes. Polly doesn't care which one.

---

## Architecture

```
[mic always-on] → parrot.py classifier → sound detected
                                              │
                              ┌───────────────┤
                              ▼               ▼
                           "click"       "never_mind"
                              │               │
                         toggle state    send Escape
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
            was idle                was recording
          send START key           send STOP key
```

### Stack

| Layer | Tool | Notes |
|-------|------|-------|
| Menu bar icon | `rumps` | Takes macOS main thread; shows status dot |
| UI window | `pywebview` | Pre-created at startup, hidden; shown on demand |
| UI frontend | HTML / CSS / JS | Full modern web stack inside WKWebView |
| Python ↔ JS bridge | pywebview API | Page calls Python; Python pushes updates to page |
| Sound classification | parrot.py | Trains local `.pkl` models on your sounds |
| Keyboard output | pyautogui | Fires hotkeys to the active app |
| Auto-start | LaunchAgent plist | Generated on first setup, loads at login |

### Threading model

```
main thread:  rumps (menu bar, AppKit event loop)
              └── on click "Open Polly" → window.show()

background:   parrot.py audio loop (continuous mic capture + inference)
              └── on detection → dispatch action to main thread

webview:      pre-created with hidden=True at startup
              └── show/hide only — no new windows, no new threads
```

---

## App Structure

```
polly/
  polly.py           ← entry point, wires rumps + pywebview + parrot
  menu.py            ← rumps menu bar definition
  listener.py        ← parrot.py wrapper, audio loop, toggle logic
  config.py          ← reads/writes ~/.polly/config.yaml
  launch_agent.py    ← generates + loads/unloads the LaunchAgent plist
  ui/
    index.html       ← main window shell
    setup.html       ← training wizard
    src/             ← JS/CSS for the UI
  assets/
    polly.png        ← menu bar icon (parrot silhouette, 16x16 @2x)
    polly_active.png ← recording state icon (colored)
```

---

## UI — Main Window

Three tabs:

### Sounds tab
- List of trained sounds with enable/disable toggle
- "Retrain" button per sound → opens training wizard
- "Add sound" button → opens training wizard for a new sound
- Confidence threshold slider (global)

### Keys tab
- Which key to send on START (default: F13)
- Which key to send on STOP (default: F14)
- Which key to send on CANCEL (default: Escape)
- "Test" button per action — fires the key immediately without sound

### Log tab
- Last 20 detections: timestamp, sound name, confidence score
- Live level meter during active listening
- Clear button

---

## Training Wizard

Step-by-step modal flow:

```
Step 1: Name your sound
        "What should we call this?" → user types "click" or "never_mind"

Step 2: Record samples
        "Make the sound repeatedly for 10 seconds"
        [Live waveform / level meter]
        [Record] button → countdown → done

Step 3: Record background noise  (first time only)
        "Stay quiet for 5 seconds"
        [Record] → captures ambient baseline

Step 4: Train
        "Training model..." → spinner → done in <30 seconds

Step 5: Test
        "Make the sound — does Polly hear it?"
        [Live detection display with confidence score]
        [Looks good] / [Retrain]
```

No parrot.py settings UI is ever shown to the user. Polly owns the whole experience.

---

## Setup Flow (first launch)

1. Polly opens the training wizard automatically
2. User records "click" sound
3. User records "never mind"
4. User sets their dictation app's START/STOP keys in Polly's Keys tab
5. Polly generates and loads the LaunchAgent
6. Done — menu bar icon is now permanent

---

## Config File

`~/.polly/config.yaml`:

```yaml
version: 1

sounds:
  click:
    model: ~/.polly/models/click.pkl
    enabled: true
    action: toggle
  never_mind:
    model: ~/.polly/models/never_mind.pkl
    enabled: true
    action: cancel

keys:
  start: f13
  stop: f14
  cancel: escape

threshold: 0.85
launch_at_login: true
```

---

## Menu Bar

```
🦜  (grey = idle, green = recording, red = paused)

  ● Idle                   ← live status, not clickable
  ─────────────────
  Open Polly...
  ─────────────────
  Pause Listening
  Restart Listener
  ─────────────────
  Launch at Login  ✓
  ─────────────────
  Quit Polly
```

---

## Distribution

### Download

Polly ships as a `.dmg` containing the app bundle. User drags to `/Applications`. No installer.

The app bundle includes its own Python venv with all dependencies — user needs nothing pre-installed.

### Landing page: polly.app (or similar)

- Hero: "Hands-free voice input. Click to start."
- One-liner on what it does
- Download button
- Demo GIF or short video
- Full credit to parrot.py, prominently
- "Pay what you want" section (see below)

---

## Business Model: Pay What You Want

Polly is free. No license check, no feature gates, no expiry.

Users who want to support it can pay whatever they like — $0, $5, $10, $100. Suggested default: $10.

On payment, they receive a "license key" which is purely ceremonial:

```
Thank you for supporting Polly! 🦜

Your license key: CRACKERS

(This doesn't unlock anything — Polly is already fully yours.
It's just our way of saying thanks.)
```

Payments processed via Stripe (pay-what-you-want link, no subscription).
Revenue goes to the LLC.

### Legal basis

- parrot.py is MIT licensed — commercial use and redistribution explicitly allowed
- Required: include parrot.py copyright notice + MIT license text in the app
- Polly credits parrot.py on the landing page, in the app's About screen, and in a bundled `LICENSES.txt`
- "Pay what you want" with no feature restriction = donation, not a product sale — cleaner legally

---

## Credits (required by MIT license)

Displayed in: About screen, landing page footer, bundled `LICENSES.txt`.

```
Polly is built on parrot.py
Copyright (c) chaosparrot
https://github.com/chaosparrot/parrot.py
MIT License

Polly also uses: rumps, pywebview, pyautogui, scikit-learn, pyaudio, numpy
(see LICENSES.txt for full license texts)
```

---

## What Polly Is Not

- Not a transcription engine — it just fires keystrokes
- Not a replacement for parrot.py — it's a Mac-native wrapper around it
- Not subscription software — it's yours forever the moment you download it
- Not trying to prevent piracy — the license key is a joke and everyone knows it

---

## Key Mapping Rationale

Default keys are F13/F14 for start/stop. Why:
- They don't exist on any standard keyboard — zero conflicts with any app
- pyautogui can send them fine
- The user sets their dictation app (Vówen, SuperWhisper, Apple Dictation, etc.) to listen for these same keys
- Escape for cancel is universally understood

---

## Tuning Tips

| Problem | Fix |
|---------|-----|
| Click triggers too easily | Raise confidence threshold to 0.90–0.95 |
| Click not triggering | Lower threshold to 0.75, or re-record more samples |
| "Never mind" false-fires | Record more background noise samples, retrain |
| Fires while you're talking | Add a power threshold in parrot's pattern config |

---

## Troubleshooting

**pyaudio install fails on Apple Silicon (M1/M2/M3/M4):**
```bash
export CPATH=/opt/homebrew/include
export LIBRARY_PATH=/opt/homebrew/lib
pip install pyaudio
```

**Keystrokes not reaching dictation app:**
The process running Polly needs Accessibility permission in System Settings → Privacy & Security → Accessibility.

**Microphone not working:**
Grant Microphone access to Terminal (or the Polly app bundle) in System Settings → Privacy & Security → Microphone.

---

## Distribution Channels

| Channel | Audience | Mechanism |
|---------|----------|-----------|
| Landing page (.dmg) | Non-technical users | Download, drag to /Applications |
| Homebrew | Developers | `brew install --cask polly` |
| AgentOS | AgentOS users | `agent install polly` (uses skill registry) |

All three install the same thing. Homebrew and AgentOS handle dependencies automatically. The .dmg bundles its own Python venv.

---

## Open Questions

1. App bundle Python venv: `py2app` or manual venv + shell launcher?
2. Menu bar icon: parrot silhouette or something more abstract?
3. Should the webview window be resizable or fixed dimensions?
4. Domain: `polly.app`, `getpolly.app`, `heypolly.com`?
5. Should Polly support multiple sound profiles (work mode / home mode)?
6. How does Polly handle microphone permission prompt on first launch?
7. Should Polly eventually host under the AgentOS menu bar icon instead of its own?
