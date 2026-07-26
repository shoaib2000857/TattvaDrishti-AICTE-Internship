# TattvaDrishti

**Prototype platform to detect and mitigate malign information operations powered by large language models.**

Combines advanced AI detection with multi-layered analysis:
- 🤖 **Ollama Semantic Analysis** (40% weight) - Deep contextual risk assessment using local LLMs
- 🔍 **Hugging Face AI Detection** (35% weight) - State-of-the-art AI-generated content detection
- 🎯 **Behavioral Analysis** (15% weight) - Metadata, urgency, and manipulation tactics
- 📊 **Stylometric Analysis** (10% weight) - Linguistic fingerprinting and patterns

Plus threat graph intelligence, provenance checks, and federated sharing scaffolding.

---

## ⚠️ Python Version Requirement

**This project requires Python 3.11.x**

Python 3.12+ is **not supported** due to FastAPI + Pydantic v1 compatibility issues. The codebase enforces this requirement at runtime.

### Install Python 3.11

**macOS (Homebrew)**
```bash
brew install python@3.11
```

**macOS (pyenv)**
```bash
brew install pyenv
pyenv install 3.11.9
pyenv local 3.11.9  # Uses .python-version file
```

**Windows (Chocolatey)**
```powershell
choco install python --version=3.11.9 -y
```

**Ubuntu/Debian**
```bash
sudo apt update
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
```

**Fedora/RHEL**
```bash
sudo dnf install -y python3.11 python3.11-venv
```

---

## 🚀 Quick Start

### 1. Install Ollama (Required for Semantic Analysis)

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# macOS
brew install ollama

# Windows - Download from https://ollama.com/download/windows
```

Start Ollama and download the model:
```bash
# Start Ollama server
ollama serve

# In another terminal, download the recommended model
ollama pull llama3.2:3b
```

📖 **Detailed Ollama setup**: See [docs/OLLAMA_SETUP.md](docs/OLLAMA_SETUP.md)

### 2. Backend (FastAPI)

```bash
# Clone the repo
git clone https://github.com/Team-ASHTOJ/TattvaDrishti.git
cd TattvaDrishti

# Create virtual environment with Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Create .env file (copy from example)
cp .env.example .env

# Start the backend server
uvicorn app.main:app --reload
```

Backend will be available at: **http://127.0.0.1:8000**

### Frontend (Next.js)

```bash
cd frontend

# Create environment file
echo 'NEXT_PUBLIC_API_BASE_URL=http://localhost:8000' > .env.local

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## 📁 Project Structure

```
TattvaDrishti/
├── app/                      # FastAPI backend
│   ├── main.py              # API routes and server
│   ├── config.py            # Settings and environment config
│   ├── schemas.py           # Pydantic models
│   ├── integrations/        # HuggingFace, Ollama clients
│   ├── models/              # Detection, graph, watermark engines
│   ├── services/            # Orchestrator
│   └── storage/             # SQLite database layer
├── frontend/                # Next.js dashboard
│   ├── app/                 # Pages and layouts
│   ├── components/          # React components
│   └── lib/                 # API client
├── templates/               # Jinja2 templates
├── tests/                   # Unit tests
├── .python-version          # Python version for pyenv/asdf
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## 🔧 Configuration

### Backend Environment Variables

Create a `.env` file in the project root (optional):

```bash
APP_ENV=dev
DATABASE_URL=sqlite:///./data/app.db
WATERMARK_SEED=your-secret-seed
HF_MODEL_NAME=roberta-base-openai-detector
HF_TOKENIZER_NAME=roberta-base-openai-detector
HF_DEVICE=-1  # -1 for CPU, 0+ for GPU
OLLAMA_ENABLED=true
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_KEEP_ALIVE=10m
OLLAMA_NUM_CTX=4096
OLLAMA_MICRO_BATCH_SIZE=4
OLLAMA_MICRO_BATCH_CHARS=8000
BATCH_OLLAMA_PARALLELISM=1

# Routine partner transfer (replace this demo key in every real deployment)
SECURE_TRANSFER_KEY=LULSnIHlBjTSfWDfqVl0kTV9qXUFN0EpGbynAB_34TM=
SECURE_TRANSFER_KEY_ID=agency-shared-key-v1
SECURE_TRANSFER_NODE_ID=analyst-node
SECURE_TRANSFER_NODES=USA=https://usa.example.gov,EU=https://eu.example.gov,IN=https://in.example.gov,AUS=https://aus.example.gov
SECURE_TRANSFER_REQUIRE_TLS=true
```

The dashboard defaults to an authenticated AES-256-GCM envelope. HTTPS partner
endpoints are restricted to TLS 1.3; the blockchain path remains selectable as
a demonstration. Use a secret manager or HSM-managed 32-byte key in production,
rotate the key identifier with the key, and never deploy the sample key above.

Example sharing request:

```json
{
  "intake_id": "replace-with-a-case-id",
  "destination": "IN",
  "justification": "Partner fusion cell review",
  "include_personal_data": false,
  "transfer_mode": "encrypted"
}
```

### Frontend Environment Variables

The frontend requires `.env.local` (already gitignored):

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# Use an internal Nominatim-compatible service for sensitive deployments.
NEXT_PUBLIC_REVERSE_GEOCODER_URL=https://nominatim.openstreetmap.org/reverse
```

---

## 🧪 Running Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest
```

## Batch message archives

Bulk chat/message collections can be submitted as a versioned JSON envelope or as JSON Lines. The batch path uses vectorized Hugging Face inference, bounded Ollama micro-batches, ordered persistence, and per-record error reporting. Ollama groups up to four messages into one structured generation by default and retries only malformed or omitted items individually. See [Batch Message Ingestion](docs/BATCH_INGESTION.md) and the files in [`samples/`](samples/).

---

## 📦 Dependencies

### Backend
- **FastAPI** 0.104.1 - Web framework
- **Pydantic** 1.10.13 - Data validation (v1 for Python 3.11 compatibility)
- **Uvicorn** 0.23.2 - ASGI server
- **NetworkX** 3.1 - Graph intelligence
- **Transformers** - HuggingFace models
- **PyTorch** - ML framework
- **Jinja2** 3.1.2 - Template engine

### Frontend
- **Next.js** 14.2.3 - React framework
- **React** 18.2.0
- **Tailwind CSS** 3.4.4 - Styling
- **SWR** 2.2.4 - Data fetching

---

## 👥 For Teammates

### First Time Setup

1. **Ensure Python 3.11 is installed** (see above)
2. **Clone the repo**
   ```bash
   git clone https://github.com/Team-ASHTOJ/TattvaDrishti.git
   cd TattvaDrishti
   ```
3. **Backend setup**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. **Frontend setup**
   ```bash
   cd frontend
   echo 'NEXT_PUBLIC_API_BASE_URL=http://localhost:8000' > .env.local
   npm install
   ```

### Daily Development

**Terminal 1 - Backend**
```bash
cd TattvaDrishti
source .venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend**
```bash
cd TattvaDrishti/frontend
npm run dev
```

---

## 🛡️ Security Notes

- Database file (`data/app.db`) is gitignored
- Environment files (`.env`, `.env.local`) are gitignored
- Virtual environments (`.venv`) are gitignored
- Node modules are gitignored

---

## 📝 License

[Add your license here]

---

## 🤝 Contributing

1. Ensure Python 3.11.x is installed
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

---

## ❓ Troubleshooting

### "Python 3.11.x is required" error
- Install Python 3.11 (see installation instructions above)
- Recreate your virtual environment with Python 3.11

### Backend won't start
- Verify Python version: `python --version` (should show 3.11.x)
- Reinstall dependencies: `pip install -r requirements.txt`

### Frontend API connection errors
- Ensure backend is running on port 8000
- Check `.env.local` has correct `NEXT_PUBLIC_API_BASE_URL`

---

**Built with ❤️ by Team ASHTOJ**


```bash
cd frontend
npm install
npm run dev
```

The app expects the API to be reachable at `http://localhost:8000` by default. To point at a different backend, set `NEXT_PUBLIC_API_BASE_URL` before running `npm run dev`:

```bash
NEXT_PUBLIC_API_BASE_URL=https://shield.example.com npm run dev
```

Key experiences showcased:

- Live ingestion form that posts to `/api/v1/intake`
- Real-time event stream over `/api/v1/events/stream`
- Case drill-down that hydrates via `/api/v1/cases/{intake_id}`
- One-click sharing package generation via `/api/v1/share`

### Sample Intake

```bash
curl -X POST http://127.0.0.1:8000/api/v1/intake \
  -H "Content-Type: application/json" \
  -d @samples/intake_example.json
```

## Hugging Face GPU Detector

1. **Model prep** (offline-friendly): download once and cache locally.
   ```bash
   python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
tokenizer = AutoTokenizer.from_pretrained('roberta-base-openai-detector'); \
model = AutoModelForSequenceClassification.from_pretrained('roberta-base-openai-detector')"
   ```
   To point at a custom or fine-tuned model directory, set environment variables:
   ```bash
   export HF_MODEL_NAME=/path/to/model
   export HF_TOKENIZER_NAME=/path/to/model
   export HF_DEVICE=0  # GPU id or -1 for CPU
   ```

2. **Run with GPU**: ensure PyTorch detects your CUDA device (`python -c "import torch; print(torch.cuda.is_available())"`).

3. **Threshold tuning** (default 0.6):
   ```bash
   export HF_SCORE_THRESHOLD=0.55
   ```

## Optional Ollama Integration

Enable qualitative risk scoring through a local Ollama model (e.g., `mistral`, `codellama`, or a fine-tuned guard model).

```bash
ollama pull mistral
export OLLAMA_ENABLED=true
export OLLAMA_MODEL=mistral
export OLLAMA_TIMEOUT=20  # seconds
```

The detector will prompt the model for a JSON risk rating (0-1) and blend it with heuristics/Hugging Face probabilities.

## Testing

```bash
pytest
```

## API Reference

- `POST /api/v1/intake` — analyse content.
- `GET /api/v1/cases/{intake_id}` — retrieve stored case summary.
- `POST /api/v1/share` — generate a federated sharing package.
- `GET /api/v1/events/stream` — Server-Sent Events feed for live updates.

## Data & Storage

SQLite database stored at `data/app.db` (configurable via `DATABASE_URL`).

## Extending the MVP

- Swap the Hugging Face model for a proprietary fine-tuned detector.
- Enrich graph intelligence with live social telemetry.
- Integrate blockchain-backed sharing receipts.
- Add automated remediation playbooks triggered by high-risk scores.
