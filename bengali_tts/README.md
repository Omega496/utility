# Bengali Audio Synthesizer (`make_bengali_audio`)

A high-performance Bengali Text and Markdown to Speech solution powered by Bodhan AI's [indic-speak](https://huggingface.co/bodhan-ai/indic-speak) (~3.3B parameter speech language model built on Llama-3.2-3B and Vocos neural vocoder).

Because running a 3.3B parameter model in full fidelity requires 8GB–16GB of GPU VRAM, this package orchestrates execution seamlessly on **Google Colab's cloud GPU (Tesla T4 16GB VRAM)** using the native `colab` CLI. All heavy model loading and neural synthesis happen remotely in the cloud, and the rendered high-fidelity audio is automatically downloaded to your local machine as **Opus (`.opus`)** by default.

---

## Quick Navigation

* 📖 **[Installation Guide (Agent Prompt + Manual Setup)](file:///home/heathcliff/Documents/utility/bengali_tts/INSTALLATION.md)**
* 🚀 **[Comprehensive User Guide & Command Cheat Sheet](file:///home/heathcliff/Documents/utility/bengali_tts/how-to-use.md)**

---

## Supported Commands & Examples

### 1. Convert a Single File to Opus
```bash
make_bengali_audio story.md
# -> Creates story.opus in the same directory
```

### 2. Convert All Files in Current Directory
```bash
make_bengali_audio .
# -> Finds and converts all .md and .txt files in the current folder
```

### 3. Convert All Files in Folder and Subfolders Recursively
```bash
make_bengali_audio . -r
# -> Recursively converts all .md and .txt files in current folder & all subdirectories
```

### 4. Custom Voice & Emotion Delivery
```bash
# Male voice (Sourav) with happy delivery
make_bengali_audio chapter1.txt -s Sourav --style HAPPY

# Female voice (Ishita - default)
make_bengali_audio chapter1.txt -s Ishita --style NEUTRAL
```

### 5. Convert Raw Text String Directly
```bash
make_bengali_audio -t "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি।" -o national_anthem.opus
```

---

## Architecture Overview

```
                      +---------------------------------------+
                      |             Local Machine             |
                      |  - make_bengali_audio CLI             |
                      |  - Target discovery (.md, .txt)       |
                      |  - Unicode normalization & chunking   |
                      +-------------------+-------------------+
                                          |
                                          | Google Colab CLI (colab exec / download)
                                          v
                      +---------------------------------------+
                      |         Google Colab VM (GPU)         |
                      |  - Tesla T4 (16 GB VRAM)              |
                      |  - bodhan-ai/indic-speak (Cached)     |
                      |  - SNAC Audio Codec + Vocos Vocoder   |
                      |  - Multi-chunk acoustic concatenation |
                      |  - Fast FFmpeg encoding (Opus default)|
                      +-------------------+-------------------+
                                          |
                                          | Downloads audio
                                          v
                      +---------------------------------------+
                      |           <filename>.opus             |
                      +---------------------------------------+
```

---

## Supported Voices & Styles

| Speaker | Language | Gender | Description |
| :--- | :--- | :--- | :--- |
| **`Ishita`** *(Default)* | Bengali | Female | Natural, expressive Bengali voice. Excellent for narration, audiobooks, and literature. |
| **`Sourav`** | Bengali | Male | Clear, confident male voice. Ideal for instructional text, stories, and dialogues. |
| **`Amit`** | Cross-lingual | Male | Supports Bengali text code-mixed with English terms and STEM content. |
| **`Kavya`** | Cross-lingual | Female | Supports Bengali text code-mixed with English terms and STEM content. |

### Vocal Styles
- `NEUTRAL` (Default)
- `HAPPY`
- `SAD`
- `ANGER`
- `FEAR`
- Descriptive natural phrases (e.g. `"calm, explanatory tone"`)

---

## Python API Usage

You can also import and use `bengali_tts` directly in Python scripts:

```python
from bengali_tts import BengaliTTS

# Initialize Colab client (connects to or creates 'bengali-tts' session with T4 GPU)
tts = BengaliTTS(session_name="bengali-tts", gpu="T4")

# Synthesize Bengali text (defaults to .opus)
result = tts.synthesize(
    text="বিজ্ঞান এবং প্রযুক্তির উন্নয়নের ফলে আমাদের জীবনযাত্রা অনেক সহজ হয়েছে।",
    output_path="technology.opus",
    speaker="Ishita",
    style="NEUTRAL",
    stop_session_after=False  # Keep VM warm for next requests
)

print(f"Audio generated: {result['local_file']}")
print(f"Duration: {result['duration_seconds']}s")
```

---

## Testing

Run unit tests locally:
```bash
PYTHONPATH=bengali_tts/src python3 -m unittest discover -s bengali_tts/tests
```
