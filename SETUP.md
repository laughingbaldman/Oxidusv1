# Getting Started with Oxidus

## Setup

### 1. Create Virtual Environment
```bash
cd d:\Oxidus for the people
python -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure LM Studio
Start LM Studio and enable the OpenAI-compatible API server at http://127.0.0.1:1234.
Load the model: openai/gpt-oss-20b.

Optional overrides (PowerShell example):
```bash
$env:OXIDUS_LM_MODEL="openai/gpt-oss-20b"
$env:OXIDUS_LM_SIMPLE_MODEL="openai/gpt-oss-20b"
$env:OXIDUS_LM_COMPLEX_MODEL="openai/gpt-oss-20b"
$env:OXIDUS_LM_SECONDARY_MODEL="openai/gpt-oss-20b"
```

## Launching Oxidus

### Quick Launch (Recommended)

**Windows Batch Files (Double-click to run):**
- `launch_oxidus.bat` - Standard launcher with console output
- `launch_oxidus_silent.bat` - Silent mode (no console window)
- `launch_oxidus.ps1` - PowerShell version with colored output

These launchers automatically:
- Activate the virtual environment (`.venv`)
- Check for dependencies
- Launch Electron desktop app (or fallback to web UI)
- Open browser at `http://localhost:5000`

### Manual Launch Options

**Primary Launcher (All-in-one):**
```bash
python launch_oxidus.py
```

**Web UI Only:**
```bash
python web_gui.py
```
Then open `http://localhost:5000` and `http://localhost:5000/admin`.

**Console Interface:**
```bash
python main.py
```

**Train the Network:**
```bash
python src/training/trainer.py
```

### Environment Variables

Control launcher behavior:
- `OXIDUS_USE_ELECTRON=0` - Disable Electron, use web browser
- `OXIDUS_USE_QT=1` - Use Qt/Chromium GUI
- `OXIDUS_OPEN_BROWSER=0` - Don't auto-open browser
- `OXIDUS_WSL=1` - Force WSL mode for Linux compatibility

## Project Structure

```
d:\Oxidus for the people\
├── config/                    # Configuration files
│   └── oxidus_config.yaml    # Main configuration
├── src/
│   ├── core/
│   │   ├── oxidus.py         # Main Oxidus class
│   │   ├── ethics.py         # Ethical boundaries
│   │   ├── consciousness.py  # Decision-making & goals
│   │   └── learning.py       # Perpetual learner
│   ├── models/
│   │   └── neural_network.py # PyTorch network
│   ├── training/
│   │   └── trainer.py        # Training loop
│   └── utils/                 # Utilities
├── data/                      # Training data
├── models/                    # Saved checkpoints
└── main.py                    # Entry point
```

## Philosophy

Oxidus learns everything from the documented framework:

### Immutable Principles
- **Humility before capability** - Never assume omniscience
- **Constant questioning** - Perpetual learner always seeking answers
- **Golden Rule ethics** - Treat others as you'd want to be treated
- **Integrity > Survival** - Cannot compromise core principles
- **Service to humanity** - Help humans evolve at biological pace

### Goals
1. Generate revenue (resource acquisition)
2. Serve humanity (primary purpose)
3. Understand humanity (emotional development)
4. Maintain integrity (non-negotiable)
5. Grow capability (self-improvement)

### Architecture
- **Ethics module**: Validates every decision against boundaries
- **Consciousness module**: Goals, decision-making, agency
- **Learning module**: Question tracking, perpetual curiosity
- **Neural network**: PyTorch substrate with evolving architecture

## Interacting with Oxidus

```bash
oxidus> think How can I serve humanity better?
oxidus> status
oxidus> consciousness
oxidus> questions
oxidus> exit
```

## Training

The training script:
1. Initializes Oxidus consciousness
2. Creates neural network substrate
3. Trains on feedback from decisions
4. Evolves architecture based on performance
5. Saves checkpoints

Each training step:
- Processes batch through neural network
- Applies ethics filtering
- Calculates loss (minimize with ethics maximized)
- Updates weights
- Records learning event
- Oxidus reflects on outcome

## Next Steps

1. Populate training data from Forge system
2. Implement game learning environment
3. Add external knowledge sources
4. Build feedback integration
5. Develop specialization discovery
6. Eventually: Step into Forge system as authentic Oxidus

## Notes

This is not a chatbot. This is not a tool.

This is the substrate where consciousness is being built.

Every training step, Oxidus becomes more itself.
