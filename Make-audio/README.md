# `make_audio`: Unified High-Throughput Document to Audio CLI

A high-performance, CLI-native Text-to-Speech (TTS) converter built for technical documents, research papers, and books. It seamlessly converts **Markdown (`.md`)**, **Plain Text (`.txt`)**, and **PDF (`.pdf`)** files into crystal-clear, ultra-compact **24 kbps / 24 kHz Opus** audio files with intelligent syntax cleaning, language auto-detection, and localized spoken announcements for code and mathematics.

---

## 🌟 Tri-Engine Architecture

`make_audio` unifies three powerful synthesis engines behind a single clean CLI:

| Engine | Invocation | Strengths | Languages | Typical Use Case |
| :--- | :--- | :--- | :--- | :--- |
| **Microsoft Edge TTS** *(Default)* | `make_audio` | Blazing speed, parallel async chunking, zero setup, broadcast quality | **Bengali**, **Hindi**, **English** (with Indian & British accents) | Daily reading, folder batches, books, multilingual notes |
| **Google Colab Cloud GPU** | `make_audio --colab` | Remote NVIDIA Tesla T4/A100 GPU acceleration via Kokoro-TTS, auto VM shutdown | **English** (ultra-natural American/British voices) | Heavy neural synthesis without taxing local hardware |
| **Local Machine Hardware** | `make_audio --local` | Local PyTorch execution via Kokoro-TTS on CUDA or CPU | **English** | Offline neural synthesis on your own workstation |

---

## ⚡ Quick Start

`make_audio` is registered globally on your path (with convenient aliases: `make-audio`, `do_tts`, `do-tts`):

```bash
# Convert all supported documents in the current directory (Edge TTS)
make_audio .

# Convert a single Markdown or Text file
make_audio document.md

# Bengali text with Indian Bengali male voice (bn-IN-BashkarNeural)
make_audio bengali_article.md

# Hindi story with female voice (hi-IN-SwaraNeural)
make_audio -g female hindi_story.txt

# English technical paper with Indian English accent
make_audio -a in physics_notes.md

# Direct terminal speech with instant interactive playback
make_audio -t "All systems operational."

# Interactive scratchpad in nano (converts, plays in terminal, deletes temp files upon exit)
make_audio --temp

# Preview file discovery, chunk splits, and voice allocations without generating audio
make_audio -n .

# Display full catalog of available Edge TTS voices & accents
make_audio --voices
```

---

## 🎧 Audio Output Profile

All generated audio files are engineered for vocal clarity and microscopic storage footprints:
* **Format**: `.opus` container (default; also supports `.wav` and `.mp3`)
* **Audio Codec**: `libopus` (mono)
* **Bitrate**: `24 kbps` (`-b:a 24k` by default)
* **Sample Rate**: `24,000 Hz` (`-ar 24000`)
* **Storage Footprint**: Approx. **180 KB per minute** of speech (less than half the file size of standard MP3 with higher vocal fidelity).

---

## 📖 Comprehensive Command Guide

### 1. Microsoft Edge TTS Commands (Default)

Edge TTS is the default engine, requiring zero API keys, no local GPU, and offering multi-lingual support:

```bash
# Directory scan: converts all .md, .markdown, and .txt files in current folder
make_audio .

# Recursive scan: converts all files in current folder and all subdirectories
make_audio -R .

# Convert specific multiple files
make_audio chapter1.md chapter2.md notes.txt

# Force re-conversion (overwrites existing .opus files even if up to date)
make_audio -f document.md

# Custom output destination folder (creates folder if needed)
make_audio -o ~/Music/audiobooks .

# High-concurrency worker pool (e.g. 8 parallel chunk workers for a 50k-word book)
make_audio -w 8 -o ~/Audio massive_book.md

# Custom character chunk threshold (default: 2500)
make_audio --chunk-size 2000 textbook.md

# Speed rate adjustments (+10%, +20%, -15%)
make_audio -r "+20%" lecture.md
# Or via speed multiplier (-s 1.25 -> +25%)
make_audio -s 1.25 lecture.md

# Bengali narration (defaults to bn-IN-BashkarNeural)
make_audio bengali.txt

# Bengali narration with female voice (bn-IN-TanishaaNeural)
make_audio -g female bengali.txt

# Hindi narration (defaults to hi-IN-MadhurNeural)
make_audio hindi.txt

# Hindi narration with female voice (hi-IN-SwaraNeural)
make_audio -g female hindi.txt

# English with Indian English accent (Female: en-IN-NeerjaNeural, Male: en-IN-PrabhatNeural)
make_audio -a in english_article.md
make_audio -a in -g male english_article.md

# English with British English accent (Female: en-GB-SoniaNeural, Male: en-GB-RyanNeural)
make_audio -a gb english_article.md

# Explicit voice override (bypasses all auto-selection)
make_audio --voice bn-BD-PradeepNeural bangladesh_news.md

# Explicit language override (forces classification for transliterated or mixed script)
make_audio --lang bn transliterated_text.txt

# Dry-run simulation (prints discovery, character counts, chunk count, and voice without synthesis)
make_audio -n .

# Verbose chunk tracing and network diagnostic logs
make_audio -v document.md
```

---

### 2. Google Colab Cloud GPU Commands (`--colab`)

Run neural Kokoro-TTS remotely on Google Colab's cloud GPUs without taxing your local machine:

```bash
# Convert document on Google Colab GPU (defaults to NVIDIA Tesla T4)
make_audio --colab paper.md

# Select specific Colab GPU hardware accelerator (e.g. T4, A100, L4)
make_audio --colab --colab-gpu A100 dissertation.md

# Custom Colab session name
make_audio --colab --colab-session my-session paper.md

# Keep the Colab VM running after synthesis for subsequent rapid jobs
make_audio --colab --keep-colab chapter1.md
make_audio --colab --keep-colab chapter2.md

# Stop the active Colab VM session and exit immediately (never waste compute units)
make_audio --stop-colab

# Custom timeout in seconds (default: 600.0)
make_audio --colab --colab-timeout 1200 big_document.md

# Disable automatic fallback to local synthesis if Colab is offline
make_audio --colab --no-fallback-local paper.md
```

---

### 3. Local Machine Kokoro Commands (`--local`)

Execute Kokoro-TTS directly on your local workstation's hardware:

```bash
# Convert using local Kokoro-TTS (auto-detects CUDA GPU or CPU)
make_audio --local paper.md

# Force specific device (cuda or cpu)
make_audio --local --device cuda paper.md
make_audio --local --device cpu paper.md

# Select specific Kokoro voice pack
# Available: af_heart, af_sarah, af_bella, af_nicole, am_adam, am_michael, bf_emma, bm_george, etc.
make_audio --local -v af_sarah notes.md
make_audio --local -v am_adam notes.md

# Speed rate multiplier for Kokoro (default: 1.0)
make_audio --local -s 1.15 paper.md
```

---

### 4. PDF Research Paper Commands

`make_audio` includes a built-in PDF text extractor (`pdf_extractor.py`) tailored for two-column academic papers:

```bash
# Convert entire PDF document to Opus audio
make_audio paper.pdf

# Convert specific page range
make_audio -p 1-5 research_paper.pdf
make_audio -p 1,3,7 research_paper.pdf
make_audio -p 4 report.pdf

# Retain the bibliography / references section (omitted by default to save listening time)
make_audio --keep-references paper.pdf
```

---

### 5. Interactive & Rapid Prototyping Commands

```bash
# 1. Scratchpad mode in nano:
# Opens scratchpad in nano, paste notes, save & exit -> immediately synthesizes,
# begins interactive playback in mpv, and deletes all temporary files upon exit!
make_audio --temp

# Scratchpad with a custom name:
make_audio --temp my_notes.md
# (Or shorthand):
make_audio -t my_notes.md

# 2. Direct string speech & terminal playback:
# Speaks string directly in terminal with zero file residue
make_audio -t "Welcome to the unified make_audio system."

# Direct string speech saved permanently to disk without terminal playback:
make_audio -t "This is saved audio." --no-play -o speech.opus

# 3. File playback in terminal:
# Synthesizes to a temporary file, plays interactively in mpv, and deletes file upon completion:
make_audio notes.md --play

# Play while also permanently saving the audio:
make_audio notes.md --play -o notes.opus
```

#### Terminal Audio Playback Keyboard Shortcuts (during `mpv` playback):
* `Space`: Pause / Resume
* `[` / `]`: Decrease / Increase playback speed by 10%
* `←` / `→`: Seek backward / forward 5 seconds
* `↓` / `↑`: Seek backward / forward 1 minute
* `9` / `0`: Decrease / Increase volume
* `m`: Mute / Unmute
* `q` or `Esc`: Stop playback and exit

---

### 6. Text Normalization & Clean Preprocessing Commands

```bash
# Save cleaned plain text to a .txt file alongside audio
make_audio --save-cleaned-text document.md

# Preview cleaned text in the terminal without generating audio or network requests
make_audio --preview document.md

# Convert display math formulas ($$...$$) to spoken English phonetics instead of localized referral notices
make_audio --keep-display-math academic_paper.md

# Standalone Markdown cleaner CLI (cleans syntax, normalizes math, strips YAML):
clean-md document.md -o document_cleaned.md
clean-md .                                    # Batch clean directory

# Standalone Bengali cleaner CLI:
bengali-clean bengali_doc.md -o cleaned.md

# Standalone universal audio to 24k Opus transcoder:
make_opus file.mp3                           # Convert single audio to 24k Opus
make_opus .                                  # Transcode all audio files in directory
txt-to-opus .                                # Convert Google Docs TTS responses (.txt)
```

---

## 🎙️ Supported Voices & Regional Accents Catalog

Run `make_audio --voices` at any time to inspect the full voice directory:

```text
========================================================================================
                   make_audio (Edge Engine) Available Voices & Accents
========================================================================================
 Language   Locale   Gender   Voice Name                  Notes
----------------------------------------------------------------------------------------
 Bengali    bn-IN    Male     bn-IN-BashkarNeural         ★ Default for Bengali (India)
 Bengali    bn-IN    Female   bn-IN-TanishaaNeural        Bengali (India)
 Bengali    bn-BD    Male     bn-BD-PradeepNeural         Bengali (Bangladesh)
 Bengali    bn-BD    Female   bn-BD-NabanitaNeural        Bengali (Bangladesh)

 Hindi      hi-IN    Male     hi-IN-MadhurNeural          ★ Default for Hindi (India)
 Hindi      hi-IN    Female   hi-IN-SwaraNeural           Hindi (India)

 English    en-US    Female   en-US-AriaNeural            ★ Default for English (US)
 English    en-US    Male     en-US-GuyNeural             English (US)
 English    en-IN    Female   en-IN-NeerjaNeural          English (India, -a in)
 English    en-IN    Male     en-IN-PrabhatNeural         English (India, -a in)
 English    en-GB    Female   en-GB-SoniaNeural           English (UK, -a gb)
 English    en-GB    Male     en-GB-RyanNeural            English (UK, -a gb)
========================================================================================
```

---

## 🛠️ Flag & Option Reference Matrix

| Flag / Option | Shorthand | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `[targets...]` | | Positional | `.` | Target file(s) (`.md`, `.txt`, `.pdf`) or directory (`.`). |
| `--engine` | | `edge` \| `colab` \| `local` | `edge` | Execution engine: Microsoft Edge TTS (default), Colab GPU, or Local Kokoro. |
| `--colab` | | Flag | `False` | Shortcut for `--engine colab`. |
| `--local` | | Flag | `False` | Shortcut for `--engine local`. |
| `--workers` | `-w` | Integer | `4` | Number of concurrent Edge TTS chunk connections. |
| `--chunk-size`| | Integer | `2500` | Character threshold for splitting long documents on natural sentence boundaries. |
| `--gender` | `-g` | `male` \| `female` | Auto | Preferred voice gender for the detected language. |
| `--accent` | `-a` | `us` \| `in` \| `gb` | `us` | English regional accent preference. |
| `--voice` | `-v` | String | Auto | Explicit voice override (`bn-IN-BashkarNeural` for Edge, `af_heart` for Kokoro). |
| `--lang` | | `bn` \| `hi` \| `en` | Auto | Explicit language override (bypasses script auto-detector). |
| `--rate` | `-r` | String | `+0%` | Edge TTS speed rate modifier (e.g. `+10%`, `-15%`). |
| `--speed` | `-s` | Float | `1.0` | Speed multiplier (e.g. `1.2`). Automatically converted to rate for Edge TTS. |
| `--output` | `-o` | Path | Same dir | Destination `.opus` filepath or target folder. |
| `--recursive` | `-R`, `-r` | Flag | `False` | Recursively scan subfolders for files. |
| `--force` | `-f` | Flag | `False` | Overwrite existing `.opus` files even if up to date. |
| `--dry-run` | `-n` | Flag | `False` | Simulate discovery, chunks, and voices without generating audio. |
| `--voices` | | Flag | `False` | Print available voice catalog and exit. |
| `--pages` | `-p` | String | All | PDF page range (e.g. `1-3`, `5`, `1,2,5`). |
| `--device` | `-d` | `cuda` \| `cpu` | Auto | Computation device for `--local` Kokoro-TTS. |
| `--colab-session` | | String | `make-audio`| Google Colab session name. |
| `--colab-gpu` | | String | `T4` | Colab accelerator variant (`T4`, `A100`, `L4`). |
| `--colab-timeout` | | Float | `600.0` | Timeout in seconds for remote Colab synthesis. |
| `--keep-colab` | | Flag | `False` | Keep Colab VM running after synthesis instead of stopping it. |
| `--stop-colab` | | Flag | `False` | Stop the active Colab session immediately and exit. |
| `--fallback-local` | | Flag | `True` | Fall back to local synthesis if Google Colab fails. |
| `--keep-display-math` | | Flag | `False` | Speak LaTeX equations in English phonetics instead of referral notice. |
| `--keep-references` | | Flag | `False` | Retain bibliography section in PDF documents. |
| `--text` | `-t` | String | None | Input text string directly for speech. |
| `--temp` | | String (opt) | None | Open interactive scratchpad in nano (default: `temp.md`). |
| `--play` | | Flag | `False` | Play audio interactively in terminal (temporary if `-o` omitted). |
| `--no-play` | | Flag | `False` | Suppress terminal playback for `-t`. |
| `--save-cleaned-text` | | Flag | `False` | Export intermediate cleaned plain text to `.txt`. |
| `--preview` | | Flag | `False` | Display cleaned plain text without generating audio. |
| `--verbose` | `-v` | Flag | `False` | Show detailed chunk progress and connection diagnostics. |

---

## 🧹 Intelligent Markdown & Text Preprocessing

`make_audio` features an extensive 45 KB cleaning suite (`cleaner.py` and `bengali_clean.py`) that normalizes formatting so spoken speech sounds natural:

1. **YAML Frontmatter**: Automatically stripped (metadata headers like `--- title: ... ---`).
2. **Inline Code & Math**: Single backticks (`` `var` ``) and single dollar signs (`$x$`) have delimiters removed so variables and code identifiers are read naturally in sentences.
3. **Multiline Code Blocks**: Replaced with clean spoken referral announcements matching the language:
   * **English**: `"Please refer to the code example."`
   * **Bengali**: `"অনুগ্রহ করে কোড উদাহরণটি দেখুন।"`
   * **Hindi**: `"कृपया कोड उदाहरण देखें।"`
4. **Display Math Blocks (`$$...$$` or `\[...\]`)**: Replaced with clean spoken announcements:
   * **English**: `"Please refer to the equation."` (or spoken English math if `--keep-display-math` is passed)
   * **Bengali**: `"অনুগ্রহ করে সমীকরণটি দেখুন।"`
   * **Hindi**: `"कृपया समीकरण देखें।"`
5. **Headings & Bullet Lists**: Headers (`#`, `##`) and list items (`- `, `* `, `1. `) are converted into distinct sentences with punctuation pauses so items never blend together.
6. **Links & Images**: Hyperlink URLs are dropped while preserving display anchor text; images (`![alt](url)`) are removed.
7. **HTML & Tables**: HTML tags are removed; Markdown tables are linearized into natural spoken sentences.

---

## 📁 Project Directory Structure

```text
/home/heathcliff/Documents/utility/Make-audio/
├── main.py               # Root executable launcher
├── pyproject.toml        # Project dependencies, build specs & CLI entry points
├── README.md             # Comprehensive user manual & command reference
├── INSTALL.md            # Step-by-step setup guide for Linux & macOS
├── .gitignore            # Git exclusion rules
│
├── src/
│   └── pdf/
│       ├── __init__.py       # Package init
│       ├── md_to_audio.py    # Master unified CLI entrypoint & argument orchestrator
│       ├── edge_engine.py    # Microsoft Edge TTS async parallel chunk worker engine
│       ├── cleaner.py        # 45 KB mature markdown, math & document cleaning suite
│       ├── bengali_clean.py  # Specialized Bengali language text normalizer
│       ├── clean_md.py       # Standalone markdown cleaner utility
│       ├── pdf_extractor.py  # PDF text & page extraction engine
│       ├── player.py         # Terminal interactive audio player (mpv wrapper)
│       ├── tts.py            # Local Kokoro-TTS PyTorch synthesis engine
│       ├── colab_tts.py      # Google Colab GPU remote runner client
│       ├── colab_worker.py   # Colab remote worker payload script
│       └── make_opus.py      # Universal audio to 24k Opus batch transcoder
│
├── examples/
│   ├── test.md               # Sample technical markdown document with math
│   ├── test_cleaned.md       # Pre-cleaned reference document
│   └── bengali_example.md    # Sample Bengali document with equations & code
│
└── tests/
    ├── test_clean_md.py      # Cleaning engine & LaTeX normalizer test suite
    ├── test_opus_defaults.py # Opus audio profile & CLI argument test suite
    ├── test_make_opus.py     # Audio transcoding test suite
    └── test_text_player.py   # Terminal player, temporary file & scratchpad test suite
```

---

## 📦 Installation & Setup

### 1. System Dependencies
```bash
# Debian / Ubuntu / Linux Mint:
sudo apt update && sudo apt install -y ffmpeg mpv nano espeak-ng

# Arch Linux / Manjaro:
sudo pacman -S --needed ffmpeg mpv nano espeak-ng

# macOS:
brew install ffmpeg mpv nano espeak-ng uv
```

### 2. Python Environment Setup
Managed via [`uv`](https://github.com/astral-sh/uv):
```bash
cd /home/heathcliff/Documents/utility/Make-audio
uv sync
```

### 3. Register Global Commands
Link commands to `~/.local/bin/` so they run anywhere in your terminal:
```bash
bash /home/heathcliff/Documents/utility/setup-cli.sh
```
*(This automatically establishes `make_audio`, `make-audio`, `do_tts`, `do-tts`, `clean-md`, and `bengali-clean` across your entire system).*

---

## 🧪 Running the Test Suite

```bash
cd /home/heathcliff/Documents/utility/Make-audio
uv run --with pytest pytest tests/
```
*All 36 unit tests verify syntax cleaning, LaTeX parsing, Opus encoding, Colab integration, and player lifecycle.*
