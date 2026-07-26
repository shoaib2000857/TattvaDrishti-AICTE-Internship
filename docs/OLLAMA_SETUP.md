# Ollama Setup Guide

This guide will help you set up Ollama for semantic risk analysis in the RiskKiller-SIH project.

## What is Ollama?

Ollama is a tool that allows you to run large language models (LLMs) locally on your machine. In this project, we use Ollama to perform deep semantic analysis of content for disinformation risk detection.

## Installation

### Linux

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### macOS

```bash
brew install ollama
```

Or download from: https://ollama.com/download/mac

### Windows

Download the installer from: https://ollama.com/download/windows

## Starting the Ollama Server

The Ollama server needs to be running for the application to communicate with it.

```bash
# Start Ollama server (runs in background)
ollama serve
```

By default, Ollama listens on `http://localhost:11434`.

## Installing Models

The repository defaults to `qwen2.5:7b`, which provided the best accuracy /
warm-latency balance on the development RTX 4060. `gemma3n:e4b` was a close
second. Re-run the included benchmark on the deployment hardware before
changing the model:

```bash
ollama pull qwen2.5:7b
python scripts/benchmark_ollama_models.py \
  gemma3n:e4b qwen2.5:7b llama3.1:8b gemma4:26b
```

### Alternative Models

Choose based on your hardware:

| Model | Size | RAM Required | Best For |
|-------|------|-------------|----------|
| `llama3.2:1b` | ~1GB | 4GB+ | Testing, low-resource systems |
| `llama3.2:3b` | ~2GB | 8GB+ | **Recommended: Best balance** |
| `llama3.1:8b` | ~4.7GB | 12GB+ | Higher accuracy |
| `llama3.1:70b` | ~40GB | 64GB+ | Maximum accuracy |
| `mistral:7b` | ~4GB | 10GB+ | Fast alternative |
| `gemma2:9b` | ~5.5GB | 16GB+ | Google's model |

To install a different model:

```bash
ollama pull <model-name>
```

## Configuration

Update your `.env` file or environment variables:

```bash
# Enable Ollama
OLLAMA_ENABLED=true

# Set the model to use
OLLAMA_MODEL=qwen2.5:7b

# Ollama server URL (default is usually fine)
OLLAMA_HOST=http://localhost:11434

# Timeout settings (in seconds)
OLLAMA_TIMEOUT=30
OLLAMA_TIMEOUT_CEILING=90
OLLAMA_KEEP_ALIVE=10m
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=280
OLLAMA_TEMPERATURE=0.1
OLLAMA_MICRO_BATCH_SIZE=4
OLLAMA_MICRO_BATCH_CHARS=8000
BATCH_OLLAMA_PARALLELISM=1

# Maximum characters to send to model
OLLAMA_PROMPT_CHARS=2000
```

## Verifying Installation

### 1. Check Ollama is Running

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing available models.

### 2. Test Model Directly

```bash
ollama run qwen2.5:7b "Analyze this for disinformation: Breaking news - government hiding truth!"
```

### 3. Test from Python

```python
import ollama

response = ollama.generate(
    model='qwen2.5:7b',
    prompt='Hello! Can you analyze text for disinformation?'
)
print(response['response'])
```

### 4. Test via API

Start your FastAPI server and make a request:

```bash
# Start the backend
uvicorn app.main:app --reload

# In another terminal, test
curl -X POST http://localhost:8000/api/v1/detect \
  -H "Content-Type: application/json" \
  -d '{
    "text": "URGENT! Share this NOW before it gets deleted! The truth they dont want you to know!",
    "tags": ["test"]
  }'
```

Check the response for `ollama_risk` field in the breakdown.

## Performance Optimization

### GPU Acceleration (NVIDIA)

Ollama automatically uses GPU if available. Verify with:

```bash
ollama ps
```

### Memory Management

If running multiple models or having memory issues:

```bash
# Unload unused models
ollama rm <model-name>

# Or use smaller models
ollama pull llama3.2:1b
```

### Batch requests

The application packs up to `OLLAMA_MICRO_BATCH_SIZE` messages into one
structured generation, bounded by `OLLAMA_MICRO_BATCH_CHARS`. Concurrency is
applied between these groups rather than between every message. On a single
consumer GPU, keep `BATCH_OLLAMA_PARALLELISM=1`; increase it only when the
Ollama server has enough GPU capacity or serves multiple model replicas.

If context pressure or malformed batch responses occur, reduce the micro-batch
size. Missing results are automatically retried as isolated requests.

## Troubleshooting

### "Ollama server not accessible"

**Problem:** Application can't connect to Ollama.

**Solutions:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama server
ollama serve

# Check port is listening
netstat -tuln | grep 11434
```

### "Model not found"

**Problem:** The configured model isn't installed.

**Solution:**
```bash
# List installed models
ollama list

# Install missing model
ollama pull llama3.2:3b
```

### Slow Response Times

**Problem:** Risk assessment takes too long.

**Solutions:**
1. Use a smaller model: `OLLAMA_MODEL=llama3.2:1b`
2. Reduce prompt size: `OLLAMA_PROMPT_CHARS=1000`
3. Lower timeout: `OLLAMA_TIMEOUT=15`
4. Enable GPU acceleration

### High Memory Usage

**Problem:** Ollama consuming too much RAM.

**Solutions:**
```bash
# Use a smaller model
ollama pull llama3.2:1b

# Remove large models
ollama rm llama3.1:70b

# Restart Ollama to free memory
pkill ollama && ollama serve
```

### Connection Refused

**Problem:** Can't connect to `localhost:11434`.

**Solutions:**
1. Ensure Ollama is running: `ollama serve`
2. Check firewall settings
3. Verify `OLLAMA_HOST` in `.env` is correct
4. Try binding to all interfaces: `OLLAMA_HOST=0.0.0.0 ollama serve`

## How It Works in the Application

1. **Text Analysis Pipeline:**
   - Content is sent to `/api/v1/detect` endpoint
   - Ollama client truncates/samples long text (up to `OLLAMA_PROMPT_CHARS`)
   - Constructs a specialized prompt for disinformation analysis
   - Calls Ollama API with configured model
   - Parses JSON response for risk score (0.0-1.0)

2. **Score Integration:**
   - Ollama risk carries **40% weight** (highest priority)
   - Combined with HF AI detection (35%), behavioral (15%), stylometric (10%)
   - Missing signals are compensated automatically

3. **Error Handling:**
   - Graceful fallback if Ollama unavailable
   - Timeout protection
   - Multiple JSON parsing strategies
   - Detailed logging for debugging

## Best Practices

1. **Model Selection:**
   - Development: `llama3.2:1b` (fast, low memory)
   - Production: `llama3.2:3b` (recommended balance)
   - High-accuracy: `llama3.1:8b` (if you have resources)

2. **Resource Planning:**
   - Reserve 2-3x model size in RAM
   - GPU speeds up inference 10-50x
   - SSD storage recommended for model loading

3. **Monitoring:**
   - Watch application logs for Ollama warnings
   - Monitor response times
   - Track Ollama memory usage: `ollama ps`

4. **Updates:**
   ```bash
   # Update Ollama
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Update models
   ollama pull llama3.2:3b
   ```

## Integration Architecture

```
┌─────────────────┐
│  FastAPI Server │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ DetectorEngine  │
└────────┬────────┘
         │
         ├──► Stylometric Analysis (10%)
         ├──► Behavioral Analysis (15%)
         ├──► HF AI Detection (35%)
         └──► Ollama Risk (40%) ◄───┐
                                     │
                        ┌────────────┴────────────┐
                        │  OllamaClient (Python)  │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  Ollama Server (Rust)   │
                        │  http://localhost:11434 │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │  LLM (llama3.2:3b)      │
                        │  Local Inference        │
                        └─────────────────────────┘
```

## Security Considerations

1. **Local Processing:** All analysis happens locally - no data sent to external APIs
2. **Network Isolation:** Ollama only needs to be accessible on localhost
3. **Model Verification:** Download models only from official Ollama registry
4. **Access Control:** Restrict Ollama server port to localhost only

## Support

- Ollama Documentation: https://ollama.com/docs
- Model Library: https://ollama.com/library
- GitHub: https://github.com/ollama/ollama
- Discord: https://discord.gg/ollama

## Quick Reference

```bash
# Start server
ollama serve

# Install model
ollama pull llama3.2:3b

# List models
ollama list

# Test model
ollama run llama3.2:3b "Test message"

# Check running models
ollama ps

# Remove model
ollama rm <model-name>

# View model info
ollama show llama3.2:3b

# Update Ollama
curl -fsSL https://ollama.com/install.sh | sh
```
