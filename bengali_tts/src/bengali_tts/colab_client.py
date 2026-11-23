"""
Colab Client for Bengali TTS.
Orchestrates remote Google Colab VM sessions, uploads payloads,
executes GPU synthesis with Indic-Speak, and downloads generated audio.
"""

import json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Dict, Any, List, Optional, Union

from bengali_tts.config import (
    DEFAULT_SESSION_NAME,
    DEFAULT_GPU,
    DEFAULT_MODEL_ID,
    DEFAULT_SPEAKER,
    DEFAULT_STYLE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_TOP_K,
    DEFAULT_MAX_NEW_TOKENS,
    DEFAULT_PAUSE_DURATION,
    REMOTE_WORKDIR,
    REMOTE_JOB_FILE,
    REMOTE_RESULT_FILE,
)

logger = logging.getLogger("bengali_tts.colab_client")


class ColabBengaliTTSError(Exception):
    """Custom exception raised when Colab TTS synthesis fails."""
    pass


class HuggingFaceAccessError(ColabBengaliTTSError):
    """Raised when Hugging Face repository access is restricted."""
    pass


def get_local_hf_token() -> Optional[str]:
    """Retrieves the Hugging Face token from environment or local cache."""
    env_token = os.environ.get("HF_TOKEN")
    if env_token:
        return env_token.strip()

    home = pathlib.Path.home()
    paths = [
        home / ".cache" / "huggingface" / "token",
        home / ".huggingface" / "token",
    ]
    for p in paths:
        if p.exists():
            try:
                t = p.read_text().strip()
                if t:
                    return t
            except Exception:
                pass
    return None


def get_colab_python() -> str:
    """Find the Python interpreter used by the installed colab CLI."""
    colab_bin = shutil.which("colab")
    if colab_bin:
        try:
            with open(colab_bin, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#!"):
                    cand = first_line[2:].strip()
                    if pathlib.Path(cand).exists():
                        return cand
        except Exception:
            pass
    return sys.executable


class BengaliTTSColabClient:
    """
    Manages Google Colab VM lifecycle and Bengali TTS synthesis jobs.
    """

    def __init__(
        self,
        session_name: str = DEFAULT_SESSION_NAME,
        gpu: str = DEFAULT_GPU,
        timeout: int = 900,
        verbose: bool = True,
    ):
        self.session_name = session_name
        self.gpu = gpu
        self.timeout = timeout
        self.verbose = verbose
        self.worker_script = pathlib.Path(__file__).resolve().parent / "remote_worker.py"

        self._check_prerequisites()

    def _check_prerequisites(self) -> None:
        """Verify that colab CLI is installed and available."""
        if not shutil.which("colab"):
            raise ColabBengaliTTSError(
                "Google Colab CLI ('colab') was not found in PATH.\n"
                "Please install it using:\n"
                "  uv tool install google-colab-cli\n"
                "  OR: pip install google-colab-cli"
            )

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"[bengali-tts] {msg}", flush=True)

    def is_session_active(self) -> bool:
        """Check if the designated session is running."""
        try:
            res = subprocess.run(
                ["colab", "sessions"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return self.session_name in res.stdout
        except Exception as e:
            self.log(f"Warning checking active sessions: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Returns details about the Colab session status."""
        try:
            res = subprocess.run(
                ["colab", "status", "-s", self.session_name],
                capture_output=True,
                text=True,
                timeout=20,
            )
            return {
                "active": self.is_session_active(),
                "session_name": self.session_name,
                "output": res.stdout.strip() or res.stderr.strip(),
            }
        except Exception as e:
            return {"active": False, "session_name": self.session_name, "error": str(e)}

    def ensure_session(self) -> None:
        """Provision or connect to the Colab session with GPU acceleration."""
        if self.is_session_active():
            self.log(f"Connected to active session '{self.session_name}' ({self.gpu} GPU).")
            return

        self.log(f"Provisioning Google Colab VM session '{self.session_name}' with {self.gpu} GPU...")
        cmd = ["colab", "new", "-s", self.session_name]
        if self.gpu:
            cmd.extend(["--gpu", self.gpu])

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            err = (res.stderr or res.stdout).strip()
            raise ColabBengaliTTSError(
                f"Failed to create Google Colab session '{self.session_name}':\n{err}"
            )

        self.log(f"Session '{self.session_name}' is ready.")

    def stop_session(self) -> bool:
        """Stops the Colab session to release compute resources."""
        self.log(f"Terminating Colab session '{self.session_name}'...")
        try:
            res = subprocess.run(
                ["colab", "stop", "-s", self.session_name],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if res.returncode == 0:
                self.log(f"Session '{self.session_name}' stopped successfully.")
                return True
            else:
                self.log(f"Stop output: {res.stderr or res.stdout}")
                return False
        except Exception as e:
            self.log(f"Error stopping session: {e}")
            return False

    def synthesize(
        self,
        chunks: List[str],
        output_path: Union[str, pathlib.Path],
        speaker: str = DEFAULT_SPEAKER,
        style: str = DEFAULT_STYLE,
        temperature: float = DEFAULT_TEMPERATURE,
        top_p: float = DEFAULT_TOP_P,
        top_k: int = DEFAULT_TOP_K,
        max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
        pause_duration: float = DEFAULT_PAUSE_DURATION,
        model_id: str = DEFAULT_MODEL_ID,
        stop_session_after: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes Bengali speech synthesis on the remote Colab GPU and downloads the output audio.
        """
        out_p = pathlib.Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        suffix = out_p.suffix.lower()
        if not suffix:
            suffix = f".{DEFAULT_OUTPUT_FORMAT}"
            out_p = out_p.with_suffix(suffix)

        fmt = suffix.lstrip(".").lower()
        if fmt not in ["wav", "opus", "mp3"]:
            fmt = DEFAULT_OUTPUT_FORMAT
            out_p = out_p.with_suffix(f".{fmt}")

        remote_out_path = f"{REMOTE_WORKDIR}/output.{fmt}"

        # 1. Ensure Colab session is active
        self.ensure_session()

        # 2. Retrieve HF token
        hf_token = get_local_hf_token()

        # 3. Create job configuration
        job_data = {
            "model_id": model_id,
            "hf_token": hf_token,
            "chunks": chunks,
            "speaker": speaker,
            "style": style,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_new_tokens": max_new_tokens,
            "pause_duration": pause_duration,
            "output_format": fmt,
            "remote_out_path": remote_out_path,
        }

        # 4. Upload job config to Colab VM via colab exec
        self.log(f"Uploading job config ({len(chunks)} chunks, speaker: {speaker}, style: {style})...")
        job_json_str = json.dumps(job_data)
        upload_script = f"""import os, json
os.makedirs('{REMOTE_WORKDIR}', exist_ok=True)
with open('{REMOTE_JOB_FILE}', 'w', encoding='utf-8') as f:
    f.write({repr(job_json_str)})
"""
        res_upload = subprocess.run(
            ["colab", "exec", "-s", self.session_name, "--timeout", "30"],
            input=upload_script,
            capture_output=True,
            text=True,
        )
        if res_upload.returncode != 0:
            err = res_upload.stderr or res_upload.stdout
            raise ColabBengaliTTSError(f"Failed to stage job on Colab VM:\n{err}")

        # 5. Execute remote worker script with live streaming & dynamic timeout
        exec_timeout = max(int(self.timeout), len(chunks) * 120)
        self.log(f"Running speech synthesis on Colab GPU (Timeout: {exec_timeout}s)...")

        cmd_exec = [
            "colab", "exec",
            "-s", self.session_name,
            "-f", str(self.worker_script),
            "--timeout", str(exec_timeout),
        ]

        full_output_lines = []
        result_payload = None

        try:
            proc = subprocess.Popen(
                cmd_exec,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            for line in proc.stdout:
                full_output_lines.append(line)
                line_str = line.strip()
                if line_str.startswith("__BENGALI_TTS_RESULT__:"):
                    json_part = line_str[len("__BENGALI_TTS_RESULT__:") :]
                    try:
                        result_payload = json.loads(json_part)
                    except Exception:
                        pass
                else:
                    if line_str:
                        print(f"  {line_str}", flush=True)

            proc.wait(timeout=exec_timeout + 60)
        except Exception as e:
            raise ColabBengaliTTSError(f"Execution error on Colab: {e}")

        full_output = "".join(full_output_lines)

        # Check for Hugging Face access restriction
        if "HUGGINGFACE_ACCESS_REQUIRED" in full_output or ("403" in full_output and "restricted" in full_output.lower()):
            msg = (
                "\n"
                "=================================================================================\n"
                "  🔒 HUGGING FACE REPOSITORY ACCESS REQUIRED\n"
                "=================================================================================\n"
                "  The model 'bodhan-ai/indic-speak' requires a one-time license acknowledgement.\n\n"
                "  Steps to enable access:\n"
                "  1. Open your browser and visit:\n"
                "     https://huggingface.co/bodhan-ai/indic-speak\n\n"
                "  2. Make sure you are signed in to Hugging Face.\n"
                "  3. Fill in the brief access request form and click 'Agree and request access'.\n"
                "     (Access is granted automatically and immediately upon submission).\n\n"
                "  4. Re-run your make_bengali_audio command.\n"
                "================================================================================="
            )
            raise HuggingFaceAccessError(msg)

        if proc.returncode != 0 or not result_payload or not result_payload.get("success"):
            err_details = result_payload.get("error") if result_payload else full_output.strip()
            raise ColabBengaliTTSError(f"Remote synthesis failed:\n{err_details}")

        # 6. Download the generated audio file
        self.log(f"Downloading rendered audio to '{out_p}'...")
        res_dl = subprocess.run(
            [
                "colab", "download",
                "-s", self.session_name,
                remote_out_path,
                str(out_p),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if res_dl.returncode != 0 or not out_p.exists() or out_p.stat().st_size == 0:
            err = res_dl.stderr or res_dl.stdout
            raise ColabBengaliTTSError(f"Failed to download audio from Colab VM:\n{err}")

        file_size_kb = round(out_p.stat().st_size / 1024, 2)
        result_payload["local_file"] = str(out_p)
        result_payload["file_size_kb"] = file_size_kb

        self.log(
            f"✔ Audio saved successfully: {out_p} "
            f"({result_payload.get('duration_seconds')}s, {file_size_kb} KB)"
        )

        # 7. Optionally stop the session
        if stop_session_after:
            self.stop_session()

        return result_payload
