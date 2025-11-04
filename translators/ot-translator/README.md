# OT Translator: Real-time Translation Display

A real-time translation system with **two implementation options**:

## 📌 Available Versions

### 1. Gladia Version (`agent.py`) - All-in-One Solution
Uses Gladia STT with built-in translation capabilities. Best for quick prototyping.

### 2. Deepgram/Azure + Google Translate Version (`deepgram_translator_agent.py`) - Flexible Production Setup
Uses Deepgram STT or Azure Speech STT for speech recognition and Google Cloud Translate API for translation. Supports configurable STT providers and bidirectional translation. Best for production with configurable languages and cost optimization.

**👉 For detailed setup and usage of the Deepgram version, see [DEEPGRAM_README.md](./DEEPGRAM_README.md)**

#### STT Provider Options

The system supports two STT providers that can be switched via environment variable:

| Provider | Best For | Multi-language Detection | Chinese Accuracy | Configuration |
|----------|----------|-------------------------|-----------------|---------------|
| **Deepgram** (default) | General use, English-heavy content | Limited (Nova-2) | Good | `STT_PROVIDER=deepgram` |
| **Azure Speech** | Chinese-heavy content, bidirectional translation | Native streaming support | Excellent | `STT_PROVIDER=azure` |

**Environment Variable:**
```bash
STT_PROVIDER=deepgram  # or "azure"
```

---

## Gladia Version Quick Start

A real-time translation system that uses Gladia STT with code switching to translate between multiple languages (French, English, Chinese) and displays the translations on a web interface.

### Features

- **Multi-language Support**: Supports French, English, and Chinese input
- **Code Switching**: Automatically detects and switches between languages
- **Real-time Translation**: Translates non-Chinese speech to Chinese in real-time
- **Web Interface**: Displays original text and translations on a web frontend
- **RPC Communication**: Uses LiveKit RPC for real-time updates from backend to frontend

### Architecture

- **Backend Agent**: Python agent that handles speech recognition and translation using Gladia STT
- **Frontend**: Next.js application displaying original text and translations in real-time
- **Communication**: Uses LiveKit RPC (WebRTC DataChannel) for real-time updates

### Running the Gladia Version

### Backend Agent

1. Make sure you have Python dependencies installed:
```bash
pip install -r requirements.txt
```

2. Run the agent:
```bash
python translators/ot-translator/agent.py dev
```

### Frontend

1. Navigate to the frontend directory:
```bash
cd translators/ot-translator/ot-translator-frontend
```

2. Install dependencies:
```bash
pnpm install
```

3. Run the development server:
```bash
pnpm dev
```

4. Open your browser to http://localhost:3000

---

## Comparison: Gladia vs Deepgram/Azure + Google Translate

| Feature | Gladia Version | Deepgram + Google Translate | Azure Speech + Google Translate |
|---------|---------------|----------------------------|--------------------------------|
| **STT Provider** | Gladia | Deepgram (Nova-2/Nova-3) | Azure Speech |
| **Translation** | Gladia built-in | Google Cloud Translate | Google Cloud Translate |
| **Multi-language Detection** | Code switching | Limited (bidirectional mode) | Native streaming support |
| **Chinese Accuracy** | Good | Good (Nova-2) | Excellent |
| **Language Config** | Code only | UI + Code (dynamic) | UI + Code (dynamic) |
| **Debounce Optimization** | No | Yes (configurable) | Yes (configurable) |
| **Bidirectional Translation** | No | Yes (via Google Translate detection) | Yes (Azure + Google Translate) |
| **Language Support** | Limited | 100+ languages | 100+ languages |
| **Cost Structure** | All-in-one pricing | Separate STT + Translation | Separate STT + Translation |
| **Setup Complexity** | Simple | Moderate (requires Google Cloud) | Moderate (requires Azure + Google Cloud) |
| **Best For** | Quick prototyping | Production, English-heavy | Production, Chinese-heavy |

---

## Usage

1. Start both the backend agent and frontend
2. Connect to the room from the frontend interface
3. Start speaking in French, English, or Chinese
4. The frontend will display:
   - Original text with language detection
   - Translated text (for non-Chinese input)
   - Real-time updates as you speak

## How It Works

1. **Speech Recognition**: User speech is captured and transcribed using Gladia STT with multi-language support
2. **Language Detection**: Gladia automatically detects the language (fr/en/zh) and code switches accordingly
3. **Translation**: When non-Chinese speech is detected, Gladia provides translation to Chinese
4. **Event Processing**: The agent intercepts STT events to:
   - Identify original transcription events
   - Match translation events with their corresponding original text
   - Distinguish between interim (real-time) and final (confirmed) events
5. **RPC Updates**: The backend sends translation pairs to the frontend via RPC:
   - Original text with language code
   - Translated text (when available)
   - Event type (interim/final)
6. **Frontend Display**: The frontend receives and displays the translations in real-time

## Translation Flow

### Example: French to Chinese

1. User says "Bonjour" (French)
2. Gladia STT returns:
   - Original transcription: "Bonjour" (fr, FINAL)
   - Translation: "你好" (zh, FINAL)
3. Agent pairs them together
4. Frontend displays:
   - Original (fr): Bonjour
   - Translation (zh): 你好

### Example: Direct Chinese Input

1. User says "你好" (Chinese)
2. Gladia STT returns:
   - Transcription: "你好" (zh, FINAL)
3. Agent recognizes it as original Chinese (no translation needed)
4. Frontend displays:
   - Original (zh): 你好
   - (No translation shown)

## Technical Details

- **STT Provider**: Gladia with multi-language support
- **Translation Target**: Chinese (zh)
- **Transport**: WebRTC DataChannel (SCTP) for reliable data delivery
- **Frontend Framework**: Next.js 15 with React 19
- **Real-time Updates**: Uses LiveKit RPC for bidirectional communication

## Incremental Rendering Design

### Problem Statement

Real-time ASR systems (like Deepgram) and machine translation APIs (like Google Translate) continuously refine their output. They don't just append new content—they often revise previously transcribed or translated text. For example:
- ASR might change "纽约" (New York) to "牛月" as more context arrives
- Translation might rephrase earlier words for better fluency

A naive "append-only" approach would preserve these errors, creating a poor user experience.

### Solution Architecture

Our implementation uses a **full_text + delta** approach:

#### 1. Data Structure

```typescript
{
  type: 'interim' | 'final',
  original: {
    full_text: string,    // Complete current text
    delta: string,        // New/modified portion
    language: string
  },
  translation: {
    full_text: string,    // Complete translation
    delta: string,        // New/modified portion  
    language: string
  }
}
```

#### 2. Backend Logic (`deepgram_translator_agent.py`)

**Interim Updates:**
- Calculate delta using longest common prefix algorithm
- Send both `full_text` (for correction) and `delta` (for animation)
- Track last sent text to compute next delta

**Final Updates:**
- Send complete final text as `full_text`
- Reset tracking state for next sentence

#### 3. Frontend Rendering

**Display Strategy:**
- Always render using `full_text` to ensure correctness
- Use `delta` information to drive fade-in animations on new content
- Existing text automatically updates when revised by ASR/translation

**Benefits:**
- ✅ Smooth "typewriter" visual effect from delta animations
- ✅ Automatic correction when ASR/translation revises text
- ✅ No accumulated errors from append-only approach
- ✅ Works with any real-time ASR/translation provider

### Example Flow

```
Time 1 (interim):
  full_text: "今天纽约"
  delta: "今天纽约"
  → UI shows: "今天纽约" (with fade-in)

Time 2 (interim):  
  full_text: "今天牛月天气"  
  delta: "牛月天气"
  → UI updates: "今天牛月天气"
  → "纽约" corrected to "牛月", "天气" fades in

Time 3 (final):
  full_text: "今天纽约天气"
  → Historical record: "今天纽约天气"
  → Interim state cleared
```

This design ensures users see both smooth real-time updates AND accurate final results, regardless of how the underlying ASR or translation systems behave.

## Display Modes

The system supports two real-time display modes that control how interim (non-final) translations are shown:

### 1. Async Mode (Default) ⚡
- **Behavior**: Original text is displayed immediately, translation appears shortly after
- **Advantage**: Faster response time - users see original text instantly
- **Use Case**: When speed and responsiveness are critical
- **Setting**: `TRANSLATION_SYNC_DISPLAY_MODE=false` (backend)

### 2. Sync Mode 🔄  
- **Behavior**: System waits for translation to complete, then displays both original and translation together
- **Advantage**: Cleaner visual experience - no "translation lag" effect
- **Use Case**: When synchronized presentation is more important than instant feedback
- **Setting**: `TRANSLATION_SYNC_DISPLAY_MODE=true` (backend)

### Configuration

**Backend (Environment Variables):**
```bash
# Set default mode on startup
TRANSLATION_SYNC_DISPLAY_MODE=false  # false = async (default), true = sync
```

This setting is configured through backend environment variables and requires agent restart to take effect.

### Visual Comparison

**Async Mode:**
```
Time 1: "Hello"        [original appears]
Time 2: "Hello"        [translation appears]
        "你好"
```

**Sync Mode:**
```
Time 1: [waiting...]
Time 2: "Hello"        [both appear together]
        "你好"
```

