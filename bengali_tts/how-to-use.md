# Bengali Audio Synthesizer: User Guide (`make_bengali_audio`)

`make_bengali_audio` is a high-throughput CLI tool for converting Bengali Markdown (`.md`) and Text (`.txt`) documents into high-quality speech audio (`.opus`). It runs Bodhan AI's 3.3B parameter [indic-speak](https://huggingface.co/bodhan-ai/indic-speak) model on a remote Google Colab GPU (Tesla T4 16GB VRAM) and automatically downloads the resulting audio to your local machine.

---

## Quick Start: The Essential Commands

### 1. Convert a Single File
```bash
make_bengali_audio story.md
```
* **Output:** Creates `story.opus` in the same directory.
* **Default Voice:** `Ishita` (Female, native Bengali).
* **Default Format:** High-efficiency Opus (`.opus`) at 24 kHz.

---

### 2. Convert All Files in the Current Directory
```bash
make_bengali_audio .
```
* Scans the current directory for all `.md`, `.markdown`, and `.txt` files.
* Converts each file sequentially using a warm Colab session.
* Creates `<stem>.opus` for every document alongside the original file.

---

### 3. Convert All Files Recursively (Including Subdirectories)
```bash
make_bengali_audio . -r
# OR:
make_bengali_audio . -R
```
* Recursively walks the directory tree and subfolders.
* Automatically ignores hidden directories (`.git`, `.venv`, `__pycache__`) and system files.

---

### 4. Convert Multiple Specific Files
```bash
make_bengali_audio chapter1.md chapter2.txt preface.md
```

---

### 5. Convert Raw Text Directly (CLI or Pipe)
```bash
# Direct argument:
make_bengali_audio "আমার সোনার বাংলা, আমি তোমায় ভালোবাসি।" -o anthem.opus

# Via flag:
make_bengali_audio -t "শুভ সকাল! আজকের আবহাওয়া কেমন?" -o morning.opus

# Via stdin pipe:
cat note.txt | make_bengali_audio -o note.opus
```

---

## Voice Selection (`-s` / `--speaker`)

Indic-Speak includes professionally recorded, consenting native speaker profiles:

```bash
# Use male voice (Sourav):
make_bengali_audio lesson.md -s Sourav

# Use female voice (Ishita - default):
make_bengali_audio audiobook.md -s Ishita
```

### Available Voices:

| Speaker | Gender | Language Focus | Best For |
| :--- | :--- | :--- | :--- |
| **`Ishita`** *(Default)* | Female | Native Bengali | Expressive narration, audiobooks, literature, conversational text. |
| **`Sourav`** | Male | Native Bengali | Clear, authoritative explanations, news, STEM lessons, documentaries. |
| **`Amit`** | Male | Cross-lingual (Bengali + English) | Technical content with mixed English terms and chemical/math equations. |
| **`Kavya`** | Female | Cross-lingual (Bengali + English) | Technical tutorials and bilingual explanations. |

To view the voice catalog in your terminal:
```bash
make_bengali_audio --list-speakers
```

---

## Vocal Emotions & Styles (`--style`)

The model supports conditioning delivery on vocal styles and emotions:

```bash
# Cheerful / Happy:
make_bengali_audio greeting.txt --style HAPPY

# Serious / Angry / Intense:
make_bengali_audio drama.md --style ANGER

# Sad / Melancholic:
make_bengali_audio poetry.md --style SAD

# Natural / Neutral (Default):
make_bengali_audio article.md --style NEUTRAL

# Descriptive natural phrases:
make_bengali_audio story.md --style "calm, bedtime storytelling"
```

To list supported style tags:
```bash
make_bengali_audio --list-styles
```

---

## Audio Formats and Quality

By default, files are encoded in **Opus (`.opus`)** at 24 kHz, providing superior audio quality at a fraction of the file size.

### Choosing Other Formats (`--format` or `-o`):
```bash
# Save explicitly as Opus:
make_bengali_audio doc.md --format opus

# Save as uncompressed WAV (24 kHz, 16-bit PCM):
make_bengali_audio doc.md --format wav

# Save as MP3:
make_bengali_audio doc.md --format mp3

# Custom destination path:
make_bengali_audio doc.md -o /home/user/Audiobooks/doc.opus
```

---

## Managing Google Colab Sessions

Colab instances are managed automatically, but understanding session lifecycle can save compute units:

### 1. Warm Sessions (Fast Consecutive Runs)
When you run `make_bengali_audio`, the Colab session stays alive. If you run multiple commands in a row, the model remains loaded in GPU VRAM, so subsequent generations start immediately without reloading the 3.3B model.

### 2. Check Colab Session Status
```bash
make_bengali_audio --status
```
*Shows whether the Colab session `bengali-tts` is active, idle, or disconnected.*

### 3. Stop the Colab VM (Save Compute Units)
When you have finished converting your files for the day, shut down the VM:
```bash
make_bengali_audio --stop
```

### 4. Auto-Stop After Conversion
If you are running a long batch overnight and want the VM to shut down automatically when done:
```bash
make_bengali_audio . -r --stop-after
```

### 5. Change Accelerator
By default, standard `T4` GPU (16 GB VRAM) is used. If your account has access to other GPUs:
```bash
make_bengali_audio chapter1.md --gpu L4
# OR:
make_bengali_audio chapter1.md --gpu A100
```

---

## Text Processing & Acoustic Chunking

The tool automatically preprocesses Bengali text:
- **Unicode Normalization:** Standardizes Bengali script, cleans up redundant diacritics.
- **Markdown Stripping:** Strips headers (`#`), bold (`**`), links (`[title](url)`), code blocks, and list asterisks so they are not read aloud literally.
- **Punctuation-Aware Chunking:** Long paragraphs are split naturally at Bengali Dari (`।`), double dari (`॥`), question marks (`?`), exclamation marks (`!`), or paragraph breaks.

### Customizing Chunking & Pacing:
```bash
# Change pause between sentences (default is 0.25 seconds):
make_bengali_audio article.md --pause 0.4

# Adjust max chunk character length (default is 200 chars):
make_bengali_audio book.txt --chunk-size 250

# Adjust temperature for speech variation (default is 0.6):
make_bengali_audio doc.md --temp 0.5
```

---

## Complete CLI Reference Cheat Sheet

| Flag | Short | Description | Example |
| :--- | :--- | :--- | :--- |
| `inputs` | | One or more `.md` / `.txt` files or directories | `make_bengali_audio .` |
| `--recursive` | `-r`, `-R` | Recursively scan folders and subfolders | `make_bengali_audio . -r` |
| `--speaker` | `-s` | Voice persona (`Ishita`, `Sourav`, `Amit`, `Kavya`) | `-s Sourav` |
| `--style` | | Vocal emotion (`NEUTRAL`, `HAPPY`, `SAD`, `ANGER`, `FEAR`) | `--style HAPPY` |
| `--output` | `-o` | Output file path or directory | `-o /path/to/out.opus` |
| `--format` | | Audio format (`opus`, `wav`, `mp3`; default: `opus`) | `--format mp3` |
| `--pause` | | Silence pause between sentences in seconds | `--pause 0.3` |
| `--temp` | | Sampling temperature (default: `0.6`) | `--temp 0.5` |
| `--stop-after` | | Tear down Colab VM once job finishes | `--stop-after` |
| `--stop` | | Stop active Colab session immediately | `make_bengali_audio --stop` |
| `--status` | | Display active Colab session info | `make_bengali_audio --status` |
| `--list-speakers` | | Print table of voices | `make_bengali_audio --list-speakers` |
| `--list-styles` | | Print available style tags | `make_bengali_audio --list-styles` |

---

## Running on Kaggle Dual GPUs (2x Faster Synthesis)

If you prefer running in Kaggle or have large book chapters, use the included **Dual-GPU Kaggle Notebook** (`bengali_tts_kaggle.ipynb`).

### Features:
- **Dual T4 Acceleration:** Automatically spins up workers on both `cuda:0` and `cuda:1`, synthesizing text chunks in parallel for an instant **2x speedup**.
- **Resumable Checkpoints:** Saves individual chunk waveforms (`chunk_0000.npy`, etc.). If interrupted, rerunning immediately resumes without repeating finished chunks.
- **Batch Processing:** Converts all `.txt` and `.md` files uploaded into `/kaggle/input` or `/kaggle/working`.
- **1-Click ZIP Download:** Packages all generated `.opus` audio into `bengali_audio_output.zip`.

### How to Run on Kaggle:
1. Open your Kaggle notebook: [https://www.kaggle.com/code/omega496/bengali-tts](https://www.kaggle.com/code/omega496/bengali-tts)
2. In the right sidebar:
   - **Accelerator:** Select **GPU T4 x 2**
   - **Internet:** Set to **ON**
3. Import the updated `bengali_tts_kaggle.ipynb` (`File` ➡️ `Upload Notebook`).
4. (Recommended) Add your Hugging Face token in `Add-ons` ➡️ `Secrets` with Key: `HF_TOKEN`.
5. Click **Run All**. All uploaded Bengali documents will be converted to high quality `.opus` audio.


---

## Troubleshooting

### Error: `🔒 HUGGING FACE REPOSITORY ACCESS REQUIRED`
* **Cause:** `bodhan-ai/indic-speak` is a gated model requiring a one-time license acknowledgement.
* **Fix:** Open [https://huggingface.co/bodhan-ai/indic-speak](https://huggingface.co/bodhan-ai/indic-speak), sign in, and click "Agree and request access". Approval is instant. Then re-run your command.

### Error: `Google Colab CLI ('colab') was not found in PATH`
* **Fix:** Install the CLI via `uv tool install google-colab-cli` or `pip install google-colab-cli`. Ensure `~/.local/bin` is in `$PATH`.

### Error: `No active sessions found` / Allocation Refused
* **Fix:** If another Colab session is consuming your account's single GPU slot, run `colab sessions` to view it and `colab stop -s <name>` to clear it.
