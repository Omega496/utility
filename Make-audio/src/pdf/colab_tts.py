"""
Google Colab TTS Engine Orchestrator.

Manages remote VM lifecycle, dependency setup, payload upload,
GPU-accelerated synthesis via Google Colab CLI, and audio retrieval.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional, Union

logger = logging.getLogger("colab_tts")


class ColabTTSError(Exception):
    """Custom exception raised when remote Colab TTS fails."""
    pass


def _get_colab_python() -> str:
    """Find the Python interpreter used by the installed colab CLI."""
    colab_bin = shutil.which("colab")
    if colab_bin:
        try:
            with open(colab_bin, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if first_line.startswith("#!"):
                    candidate = first_line[2:].strip()
                    if Path(candidate).exists():
                        return candidate
        except Exception:
            pass
    return sys.executable


def _reconcile_colab_session(session_name: str, target_gpu: Optional[str] = "T4", verbose: bool = False) -> str:
    """
    Check server assignments and local state:
    1. If a session named `session_name` is active with target GPU, keep and reuse it.
    2. If an orphan server session has target GPU, adopt it into local state as `session_name`.
    3. If any session has wrong accelerator (e.g. CPU when GPU wanted) or is an orphan blocking GPU, unassign it.
    Returns status line.
    """
    py_bin = _get_colab_python()
    script = """
import sys
try:
    from colab_cli.common import state
    from colab_cli.state import SessionState

    session_name = sys.argv[1]
    target_gpu = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "None" else None

    local_sessions, assignments = state.sync_sessions()

    # Check if session_name already exists locally and on server
    if session_name in local_sessions:
        s = local_sessions[session_name]
        if target_gpu:
            if s.accelerator.upper() == target_gpu.upper():
                print(f"REUSED:{session_name}:{s.endpoint}:{s.accelerator}")
                sys.exit(0)
            else:
                try:
                    state.client.unassign(s.endpoint)
                except Exception:
                    pass
                state.store.remove(session_name)
        else:
            print(f"REUSED:{session_name}:{s.endpoint}:{s.accelerator}")
            sys.exit(0)

    # Check if an orphan assignment exists on the server
    for a in assignments:
        acc = a.accelerator.value if hasattr(a.accelerator, 'value') else str(a.accelerator)
        var = a.variant.name if hasattr(a.variant, 'name') else str(a.variant)
        if target_gpu and acc.upper() == target_gpu.upper():
            s = SessionState(
                name=session_name,
                token=a.runtime_proxy_info.token,
                url=a.runtime_proxy_info.url,
                endpoint=a.endpoint,
                token_expires_at=a.runtime_proxy_info.expires_at() if hasattr(a.runtime_proxy_info, 'expires_at') else None,
                variant=var,
                accelerator=acc,
                machine_shape=a.machine_shape.name if hasattr(a.machine_shape, 'name') else "STANDARD",
            )
            state.store.add(s)
            print(f"ADOPTED:{session_name}:{a.endpoint}:{acc}")
            sys.exit(0)
        else:
            try:
                state.client.unassign(a.endpoint)
                print(f"UNASSIGNED:{a.endpoint}")
            except Exception:
                pass

    print("CLEAN")
except Exception as e:
    print(f"ERROR:{e}")
"""
    try:
        res = subprocess.run(
            [py_bin, "-c", script, session_name, str(target_gpu)],
            capture_output=True,
            text=True,
            timeout=25,
        )
        out = (res.stdout or "").strip()
        if verbose and out:
            print(f"[colab-client] Session reconciliation: {out}")
        return out
    except Exception as e:
        if verbose:
            print(f"[colab-client] Reconciliation warning: {e}")
        return "ERROR"


class ColabTTS:
    """
    Manages audio synthesis on a Google Colab GPU/CPU runtime via colab CLI.
    """

    def __init__(
        self,
        session_name: str = "make-audio",
        gpu: Optional[str] = "T4",
        timeout: float = 600.0,
        verbose: bool = False,
    ):
        self.session_name = session_name
        self.gpu = gpu if (gpu and gpu.lower() != "none") else None
        self.timeout = timeout
        self.verbose = verbose
        self._session_verified = False
        self._deps_installed = False
        self.worker_script = Path(__file__).resolve().parent / "colab_worker.py"

        if not self.worker_script.exists():
            raise ColabTTSError(f"Worker script not found at {self.worker_script}")

        self._check_colab_installed()

    def _check_colab_installed(self) -> None:
        """Verify the colab CLI binary is available."""
        if not shutil.which("colab"):
            raise ColabTTSError(
                "Google Colab CLI ('colab') was not found in PATH.\n"
                "Please ensure google-colab-cli is installed (e.g. 'uv tool install google-colab-cli' or 'pip install google-colab-cli')."
            )

    def is_session_active(self) -> bool:
        """Check if the designated session is currently running."""
        reconcile_res = _reconcile_colab_session(self.session_name, self.gpu, verbose=self.verbose)
        if reconcile_res.startswith("REUSED:") or reconcile_res.startswith("ADOPTED:"):
            return True

        try:
            res = subprocess.run(
                ["colab", "status", "-s", self.session_name],
                capture_output=True,
                text=True,
                timeout=15,
            )
            output = res.stdout + res.stderr
            if "not found" in output.lower() or "no active sessions" in output.lower():
                return False
            sessions_res = subprocess.run(
                ["colab", "sessions"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            return self.session_name in sessions_res.stdout
        except Exception as e:
            if self.verbose:
                print(f"[colab-client] Error checking session status: {e}")
            return False

    def ensure_session(self) -> None:
        """Ensure the Colab VM session is active and dependencies are installed."""
        if self._session_verified and self.session_name:
            return

        if self.is_session_active():
            print(f"[Colab] Connected to active session '{self.session_name}' ({self.gpu or 'CPU'}).")
        else:
            gpu_desc = f" ({self.gpu} GPU)" if self.gpu else ""
            print(f"[Colab] Provisioning session '{self.session_name}'{gpu_desc}...")
            cmd = ["colab", "new", "-s", self.session_name]
            if self.gpu:
                cmd.extend(["--gpu", self.gpu])

            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                err_msg = (res.stderr or res.stdout).strip()
                # If allocation refused or too many assignments, unassign stale sessions and retry once
                if "allocation refused" in err_msg.lower() or "precondition" in err_msg.lower() or "too many" in err_msg.lower():
                    if self.verbose:
                        print("[colab-client] Clearing existing assignments and retrying...")
                    _reconcile_colab_session(self.session_name, self.gpu, verbose=self.verbose)
                    res = subprocess.run(cmd, capture_output=True, text=True)

            if res.returncode != 0:
                err_msg = (res.stderr or res.stdout).strip()
                raise ColabTTSError(
                    f"Failed to create Google Colab session '{self.session_name}':\n{err_msg}\n"
                    "Tip: Check active sessions ('colab sessions') or use '--fallback-local'."
                )

            print(f"[Colab] Session '{self.session_name}' ready.")

        self._ensure_remote_dependencies()
        self._session_verified = True

    def _ensure_remote_dependencies(self) -> None:
        """Ensure kokoro, soundfile, and espeakng-loader are installed on the Colab VM."""
        if self._deps_installed:
            return

        check_proc = subprocess.run(
            ["colab", "exec", "-s", self.session_name, "--timeout", "35"],
            input="import kokoro, soundfile\n",
            capture_output=True,
            text=True,
        )
        if check_proc.returncode == 0 and "error" not in check_proc.stderr.lower():
            if self.verbose:
                print("[Colab] Remote dependencies verified.")
            self._deps_installed = True
            return

        print("[Colab] Installing remote TTS dependencies (kokoro, soundfile, espeakng-loader)...")
        install_proc = subprocess.run(
            ["colab", "install", "-s", self.session_name, "kokoro>=0.9.4", "soundfile>=0.14.0", "espeakng-loader"],
            capture_output=not self.verbose,
            text=True,
        )
        if install_proc.returncode != 0:
            err = install_proc.stderr if hasattr(install_proc, "stderr") else "Installation failed"
            raise ColabTTSError(f"Failed to install dependencies on Colab VM: {err}")
        print("[Colab] Remote dependencies installed successfully.")
        self._deps_installed = True

    def convert_to_audio_file(
        self,
        text: str,
        output_path: Union[str, Path],
        voice: str = "af_heart",
        speed: float = 1.0,
        pause_between_paragraphs: float = 0.25,
        stop_session_after: bool = False,
        bitrate: str = "24k",
    ) -> Path:
        """
        Upload text job to Colab, execute GPU Kokoro synthesis, and download audio.
        Defaults to 24k Opus audio format.
        """
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = output_path.suffix.lower()
        if not suffix:
            output_path = output_path.with_suffix(".opus")
            suffix = ".opus"

        # Step 1: Ensure active session
        self.ensure_session()

        # Step 2: Prepare temporary job JSON payload
        if suffix == ".opus":
            remote_output_file = "/content/make_audio_output.opus"
        elif suffix == ".mp3":
            remote_output_file = "/content/make_audio_output.mp3"
        else:
            remote_output_file = "/content/make_audio_output.wav"

        job_data = {
            "text": text,
            "voice": voice,
            "speed": speed,
            "pause_between_paragraphs": pause_between_paragraphs,
            "output_path": remote_output_file,
            "bitrate": bitrate,
            "verbose": self.verbose,
        }

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(job_data, f, ensure_ascii=False)
            local_job_path = f.name

        try:
            # Step 3: Upload job file to Colab
            if self.verbose:
                print("[colab-client] Uploading narration payload to Colab...")
            upload_res = subprocess.run(
                ["colab", "upload", "-s", self.session_name, local_job_path, "/content/make_audio_job.json"],
                capture_output=True,
                text=True,
            )
            if upload_res.returncode != 0:
                raise ColabTTSError(f"Failed to upload job to Colab: {upload_res.stderr or upload_res.stdout}")

            # Step 4: Run remote worker via colab exec
            word_count = len(text.split())
            estimated_timeout = max(self.timeout, float(word_count * 2.0))
            if self.verbose:
                print(f"[colab-client] Executing remote synthesis (timeout: {estimated_timeout:.0f}s)...")

            exec_cmd = [
                "colab", "exec",
                "-s", self.session_name,
                "-f", str(self.worker_script),
                "--timeout", str(estimated_timeout),
            ]

            proc = subprocess.Popen(
                exec_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            worker_success = False
            captured_lines = []
            for line in proc.stdout:
                line_str = line.strip()
                if not line_str:
                    continue
                captured_lines.append(line_str)
                if "[colab-worker] SUCCESS" in line_str:
                    worker_success = True
                elif "[colab-worker] [" in line_str:
                    clean_msg = line_str.replace("[colab-worker]", "[Colab]")
                    sys.stdout.write(f"\r{clean_msg[:85]}")
                    sys.stdout.flush()
                elif self.verbose:
                    print(line_str)

            proc.wait()
            # Clean newline after carriage return progress
            sys.stdout.write("\n")
            sys.stdout.flush()

            if proc.returncode != 0 or not worker_success:
                err_details = "\n".join(captured_lines)
                raise ColabTTSError(
                    f"Remote Kokoro synthesis failed (exit code {proc.returncode}):\n{err_details}"
                )

            # Step 5: Download generated audio
            if self.verbose:
                print(f"[colab-client] Downloading generated audio ({suffix}) from Colab...")

            download_res = subprocess.run(
                ["colab", "download", "-s", self.session_name, remote_output_file, str(output_path)],
                capture_output=True,
                text=True,
            )

            # Check if download succeeded
            if download_res.returncode != 0 or not output_path.exists() or output_path.stat().st_size == 0:
                # If remote opus was not downloaded, attempt fallback download of remote wav
                fallback_remote_wav = "/content/make_audio_output.wav"
                temp_local_wav = output_path.with_suffix(".temp.wav")
                wav_dl = subprocess.run(
                    ["colab", "download", "-s", self.session_name, fallback_remote_wav, str(temp_local_wav)],
                    capture_output=True,
                    text=True,
                )
                if wav_dl.returncode == 0 and temp_local_wav.exists() and temp_local_wav.stat().st_size > 0:
                    if suffix == ".opus":
                        encoded = False
                        if shutil.which("ffmpeg"):
                            try:
                                subprocess.run(
                                    [
                                        "ffmpeg", "-y",
                                        "-i", str(temp_local_wav),
                                        "-c:a", "libopus",
                                        "-b:a", str(bitrate),
                                        "-vbr", "on",
                                        "-application", "voip",
                                        str(output_path),
                                    ],
                                    check=True,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                )
                                encoded = True
                            except Exception:
                                encoded = False
                            finally:
                                temp_local_wav.unlink(missing_ok=True)
                        if not encoded:
                            temp_local_wav.rename(output_path.with_suffix(".wav"))
                            output_path = output_path.with_suffix(".wav")
                    elif suffix == ".mp3":
                        if shutil.which("ffmpeg"):
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", str(temp_local_wav), "-b:a", "192k", str(output_path)],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            temp_local_wav.unlink(missing_ok=True)
                        else:
                            temp_local_wav.rename(output_path.with_suffix(".wav"))
                            output_path = output_path.with_suffix(".wav")
                    else:
                        temp_local_wav.rename(output_path)
                else:
                    raise ColabTTSError(
                        f"Failed to download audio from Colab: {download_res.stderr or download_res.stdout}"
                    )

            return output_path

        except Exception:
            self._session_verified = False
            raise
        finally:
            # Clean up local temporary job file
            if os.path.exists(local_job_path):
                try:
                    os.unlink(local_job_path)
                except OSError:
                    pass

            # Step 6: Teardown session if requested
            if stop_session_after:
                self.stop_session(self.session_name, verbose=self.verbose)

    @classmethod
    def stop_session(cls, session_name: str = "make-audio", verbose: bool = False) -> bool:
        """Terminate a running Colab session and clean up remote state."""
        if verbose:
            print(f"[colab-client] Stopping Colab session '{session_name}'...")
        res = subprocess.run(
            ["colab", "stop", "-s", session_name],
            capture_output=True,
            text=True,
        )
        # Also ensure any lingering orphan server assignment is cleaned up
        _reconcile_colab_session(session_name, target_gpu=None, verbose=verbose)
        output = (res.stdout + res.stderr).strip()
        if verbose and output:
            print(f"[colab-client] {output}")
        return res.returncode == 0
