# OT Translator: Real-time Translation Display

A real-time translation system that uses Gladia STT with code switching to translate between multiple languages (French, English, Chinese) and displays the translations on a web interface.

## Features

- **Multi-language Support**: Supports French, English, and Chinese input
- **Code Switching**: Automatically detects and switches between languages
- **Real-time Translation**: Translates non-Chinese speech to Chinese in real-time
- **Web Interface**: Displays original text and translations on a web frontend
- **RPC Communication**: Uses LiveKit RPC for real-time updates from backend to frontend

## Architecture

- **Backend Agent**: Python agent that handles speech recognition and translation using Gladia STT
- **Frontend**: Next.js application displaying original text and translations in real-time
- **Communication**: Uses LiveKit RPC (WebRTC DataChannel) for real-time updates

## Running the Application

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

