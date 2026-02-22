# ChatGPT Skill — Authentication & Discovery

**Status:** INVESTIGATION  
**Priority:** HIGH  
**Created:** 2026-02-21

---

## Problem

We want to connect ChatGPT to AgentOS (similar to how we connected Claude/Anthropic). This enables agents to use GPT models for tasks. Need to determine:
1. How ChatGPT Desktop stores auth tokens
2. Whether we can read them without Keychain
3. OpenAI API endpoint for message completion
4. Model discovery mechanism

---

## Three Potential Approaches

### Approach 1: ChatGPT Desktop (like claude-desktop)
- **Where:** `~/Library/Application Support/com.openai.chat/`
- **Questions:**
  - Does ChatGPT Desktop use SafeStorage (requires Keychain)?
  - Is there a plaintext config.json like Claude?
  - Can we read plist files directly (`com.openai.chat.plist`)?
  - Does it have an internal OAuth token we can extract?

### Approach 2: Firefox Cookies (no Keychain needed)
- **Mechanism:** Read plaintext `cookies.sqlite` from Firefox
- **Questions:**
  - If user is logged into ChatGPT web (chat.openai.com) in Firefox, what cookie name stores the session?
  - Does that cookie contain enough auth info to call OpenAI API?
  - Would need Firefox skill/resolver to extract

### Approach 3: OpenAI API Key
- **Like anthropic-api** — user provides API key manually
- **Questions:**
  - Is there an OpenAI Messages API compatible endpoint?
  - Do they support tool use like Anthropic?
  - Model listing endpoint?

---

## Research Questions

### Local Investigation
- [ ] What files are in `~/Library/Application Support/com.openai.chat/`?
- [ ] Can we parse the plist file (`com.openai.chat.plist`)?
- [ ] Are there any JSON config files?
- [ ] Are there SQLite databases with auth tokens?
- [ ] Can we read cookies.sqlite from Firefox if logged into ChatGPT?

### Web Research
- [ ] Does ChatGPT Desktop use Electron SafeStorage like Claude?
- [ ] What's the OpenAI Messages API endpoint (if it exists)?
- [ ] Does OpenAI support function calling / tool use like Anthropic?
- [ ] How does ChatGPT Desktop authenticate internally?
- [ ] What's the model listing API for OpenAI?

---

## Architecture Decision

Once we know how ChatGPT Desktop works:

**Option A: chatgpt-desktop skill** (parallel to claude-desktop)
- SafeStorage auth if it uses it
- Or direct plist parsing if plaintext

**Option B: chatgpt-api skill** (parallel to anthropic-api)  
- Manual API key
- OpenAI Messages API endpoint

**Option C: Firefox skill** (cross-cutting)
- Generic Firefox cookie extractor
- Works for ChatGPT, any other Firefox-logged-in service
- No Keychain needed

**Most likely:** We'll need both chatgpt-desktop AND a firefox skill to avoid Keychain dependency.

---

## Next Steps

1. **Local exploration:** What does ChatGPT Desktop actually have on disk?
2. **Web research:** How does it authenticate? What APIs exist?
3. **Decision:** Which approach is viable?
4. **Implementation:** Create 1-3 new skills
