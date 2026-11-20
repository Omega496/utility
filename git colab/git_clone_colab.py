#!/usr/bin/env python3
"""
git_clone_colab - Fast Git repository cloning via Google Colab CLI.

Clones a repository into a Google Colab virtual machine (leveraging Google Cloud's
high-speed datacenter connection), packages it into a zip archive, and downloads
it to your local computer.
"""

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from typing import Optional, Dict, Any

__version__ = "1.0.0"

# Styling & Output helpers
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    HAS_RICH = True
    console = Console()
    console_err = Console(stderr=True)
except ImportError:
    HAS_RICH = False
    console = None
    console_err = None


def print_info(msg: str):
    if HAS_RICH and console:
        console.print(f"[bold cyan]ℹ[/bold cyan] {msg}")
    else:
        print(f"[INFO] {msg}")


def print_success(msg: str):
    if HAS_RICH and console:
        console.print(f"[bold green]✔[/bold green] {msg}")
    else:
        print(f"[SUCCESS] {msg}")


def print_warn(msg: str):
    if HAS_RICH and console:
        console.print(f"[bold yellow]⚠[/bold yellow] {msg}")
    else:
        print(f"[WARNING] {msg}")


def print_error(msg: str):
    if HAS_RICH and console_err:
        console_err.print(f"[bold red]✖[/bold red] {msg}")
    else:
        sys.stderr.write(f"[ERROR] {msg}\n")
        sys.stderr.flush()


def format_bytes(size: float) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0 or unit == "TB":
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def parse_repo_name(url: str) -> str:
    """
    Extract a clean repository name from various git URL formats:
    - https://github.com/user/repo.git
    - https://github.com/user/repo/
    - git@github.com:user/repo.git
    - https://gitlab.com/user/repo
    """
    url = url.strip()
    # Handle scp-style SSH URLs: git@github.com:owner/repo.git
    if "@" in url and ":" in url and not url.startswith(("http://", "https://", "ssh://")):
        path = url.split(":", 1)[1]
    else:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path

    # Clean path
    path = path.rstrip("/")
    if not path:
        return "cloned_repo"

    name = path.split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    # Sanitize name
    name = re.sub(r"[^\w\.-]", "_", name)
    return name or "cloned_repo"


class ColabCloner:
    def __init__(
        self,
        repo_url: str,
        output_dir: str = ".",
        custom_name: Optional[str] = None,
        branch: Optional[str] = None,
        depth: Optional[int] = None,
        submodules: bool = False,
        no_git: bool = False,
        extract: bool = False,
        remove_zip: bool = False,
        session_name: Optional[str] = None,
        keep_session: bool = False,
        timeout: float = 1800.0,
        gpu: Optional[str] = None,
        high_mem: bool = False,
    ):
        self.repo_url = repo_url
        self.output_dir = os.path.abspath(output_dir)
        self.repo_name = custom_name or parse_repo_name(repo_url)
        self.branch = branch
        self.depth = depth
        self.submodules = submodules
        self.no_git = no_git
        self.extract = extract
        self.remove_zip = remove_zip
        self.custom_session = bool(session_name)
        self.session_name = session_name or f"clone-{int(time.time())}"
        self.keep_session = keep_session
        self.timeout = timeout
        self.gpu = gpu
        self.high_mem = high_mem

        self.session_created = False
        self.workdir_id = f"colab_git_{int(time.time())}"
        self.remote_workdir = f"/content/{self.workdir_id}"
        self.remote_zip = f"{self.remote_workdir}/{self.repo_name}.zip"
        self.local_zip = os.path.join(self.output_dir, f"{self.repo_name}.zip")
        self.local_extract_dir = os.path.join(self.output_dir, self.repo_name)

        # Register cleanup handlers
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        atexit.register(self.cleanup)

    def _handle_signal(self, signum, frame):
        print_warn("\nOperation interrupted by user. Cleaning up...")
        self.cleanup()
        sys.exit(130)

    def check_prerequisites(self):
        """Verify that colab CLI is installed and accessible."""
        if not shutil.which("colab"):
            print_error(
                "Google Colab CLI (`colab`) is not found in PATH.\n"
                "Please install it using:\n"
                "  uv tool install google-colab-cli\n"
                "  OR: pip install google-colab-cli"
            )
            sys.exit(1)

    def run_command(self, cmd: list, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
        """Run a local shell command."""
        return subprocess.run(
            cmd,
            check=check,
            text=True,
            capture_output=capture,
        )

    def ensure_session(self):
        """Create or connect to a Colab session."""
        if self.custom_session:
            print_info(f"Using existing Colab session: [bold]{self.session_name}[/bold]")
            return

        print_info(f"Initializing Google Colab session: [bold]{self.session_name}[/bold]...")
        cmd = ["colab", "new", "-s", self.session_name]
        if self.gpu:
            cmd.extend(["--gpu", self.gpu])
        if self.high_mem:
            cmd.append("--high-mem")

        res = self.run_command(cmd, check=False, capture=True)
        if res.returncode != 0:
            err = res.stderr or res.stdout
            print_error(f"Failed to create Colab session:\n{err}")
            sys.exit(1)

        self.session_created = True
        print_success(f"Colab session ready: [bold]{self.session_name}[/bold]")

    def execute_remote_clone_and_zip(self) -> Dict[str, Any]:
        """Execute the clone and zip script on the remote Colab VM."""
        print_info(f"Cloning [bold]{self.repo_url}[/bold] inside Colab VM...")

        config_dict = {
            "workdir": self.remote_workdir,
            "repo_url": self.repo_url,
            "repo_name": self.repo_name,
            "branch": self.branch,
            "depth": self.depth,
            "submodules": self.submodules,
            "no_git": self.no_git,
        }
        config_json_str = json.dumps(config_dict)

        remote_script = f"""import os, sys, subprocess, shutil, json

config = json.loads({repr(config_json_str)})

workdir = config['workdir']
repo_url = config['repo_url']
repo_name = config['repo_name']
branch = config.get('branch')
depth = config.get('depth')
submodules = config.get('submodules', False)
no_git = config.get('no_git', False)

if os.path.exists(workdir):
    shutil.rmtree(workdir, ignore_errors=True)
os.makedirs(workdir, exist_ok=True)

target_dir = os.path.join(workdir, repo_name)

# Build git clone command
cmd = ["git", "clone"]
if depth:
    cmd.extend(["--depth", str(depth)])
if branch:
    cmd.extend(["--branch", str(branch)])
if submodules:
    cmd.append("--recurse-submodules")
cmd.extend([repo_url, target_dir])

print(f"[colab] Running: {{' '.join(cmd)}}")
p_clone = subprocess.run(cmd, capture_output=True, text=True)
if p_clone.returncode != 0:
    err = p_clone.stderr.strip() or p_clone.stdout.strip()
    print("__COLAB_RESULT__:" + json.dumps({{"success": False, "error": err}}))
    sys.exit(0)

def get_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if not os.path.islink(fp) and os.path.exists(fp):
                total += os.path.getsize(fp)
    return total

raw_size = get_size(target_dir)

if no_git:
    git_dir = os.path.join(target_dir, ".git")
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir, ignore_errors=True)

zip_file = os.path.join(workdir, f"{{repo_name}}.zip")
print(f"[colab] Compressing repository into {{zip_file}}...")

# Fast zip compression via bash zip command
p_zip = subprocess.run(["zip", "-r", "-q", zip_file, repo_name], cwd=workdir, capture_output=True, text=True)
if p_zip.returncode != 0 or not os.path.exists(zip_file):
    base = os.path.join(workdir, repo_name)
    zip_file = shutil.make_archive(base, "zip", root_dir=workdir, base_dir=repo_name)

zip_size = os.path.getsize(zip_file)

result = {{
    "success": True,
    "repo_name": repo_name,
    "raw_size": raw_size,
    "zip_size": zip_size,
    "zip_path": zip_file
}}
print("__COLAB_RESULT__:" + json.dumps(result))
"""

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write(remote_script)
            temp_script_path = tf.name

        try:
            exec_cmd = [
                "colab", "exec",
                "-s", self.session_name,
                "-f", temp_script_path,
                "--timeout", str(self.timeout)
            ]

            p = subprocess.run(exec_cmd, capture_output=True, text=True)
        finally:
            if os.path.exists(temp_script_path):
                os.remove(temp_script_path)

        result = None
        for line in p.stdout.splitlines():
            line_str = line.strip()
            if line_str.startswith("__COLAB_RESULT__:"):
                json_str = line_str[len("__COLAB_RESULT__:"):].strip()
                try:
                    result = json.loads(json_str)
                except Exception as e:
                    print_error(f"Failed to parse result payload: {e}")
            elif line_str and not line_str.startswith("[colab]"):
                print(f"  [remote] {line_str}")

        if p.returncode != 0 or not result:
            err = p.stderr.strip() or p.stdout.strip()
            print_error(f"Execution failed on Colab VM:\n{err}")
            sys.exit(1)

        if not result.get("success"):
            print_error(f"Clone failed in Colab:\n{result.get('error')}")
            sys.exit(1)

        return result

    def download_zip(self, result: Dict[str, Any]):
        """Download the generated zip file from Colab VM."""
        os.makedirs(self.output_dir, exist_ok=True)
        zip_size = result.get("zip_size", 0)
        raw_size = result.get("raw_size", 0)

        saved_percent = 0.0
        if raw_size > 0:
            saved_percent = max(0.0, (1.0 - (zip_size / raw_size)) * 100.0)

        print_success(
            f"Repository cloned & zipped: "
            f"[bold cyan]{format_bytes(raw_size)}[/bold cyan] uncompressed → "
            f"[bold green]{format_bytes(zip_size)}[/bold green] zipped "
            f"({saved_percent:.1f}% space saved)"
        )

        print_info(f"Downloading [bold]{self.repo_name}.zip[/bold] to [bold]{self.output_dir}[/bold]...")
        t0 = time.time()

        dl_cmd = [
            "colab", "download",
            "-s", self.session_name,
            self.remote_zip,
            self.local_zip
        ]

        p = self.run_command(dl_cmd, check=False, capture=True)
        if p.returncode != 0 or not os.path.exists(self.local_zip):
            err = p.stderr or p.stdout
            print_error(f"Download failed from Colab:\n{err}")
            sys.exit(1)

        elapsed = time.time() - t0
        speed_mb = (zip_size / (1024 * 1024)) / elapsed if elapsed > 0 else 0

        print_success(
            f"Downloaded in [bold]{elapsed:.2f}s[/bold] "
            f"({speed_mb:.2f} MB/s) → [bold green]{self.local_zip}[/bold green]"
        )

    def extract_zip(self):
        """Extract the downloaded zip archive to destination."""
        if not self.extract:
            return

        print_info(f"Extracting archive to [bold]{self.local_extract_dir}[/bold]...")
        t0 = time.time()

        os.makedirs(self.local_extract_dir, exist_ok=True)
        with zipfile.ZipFile(self.local_zip, "r") as zf:
            for member in zf.infolist():
                target_path = os.path.abspath(os.path.join(self.output_dir, member.filename))
                if not target_path.startswith(self.output_dir):
                    raise RuntimeError(f"Unsafe path detected in zip: {member.filename}")
            zf.extractall(self.output_dir)

        elapsed = time.time() - t0
        print_success(f"Extracted in [bold]{elapsed:.2f}s[/bold] → [bold green]{self.local_extract_dir}[/bold green]")

        if self.remove_zip:
            if os.path.exists(self.local_zip):
                os.remove(self.local_zip)
                print_info(f"Removed intermediate zip archive: {self.local_zip}")

    def cleanup(self):
        """Clean up Colab VM files and stop session if ephemeral."""
        if self.session_created and not self.keep_session:
            print_info(f"Stopping Colab session [bold]{self.session_name}[/bold]...")
            self.run_command(["colab", "stop", "-s", self.session_name], check=False, capture=True)
            self.session_created = False
        elif self.custom_session:
            # Clean remote temp directory
            clean_cmd = f"import shutil; shutil.rmtree('{self.remote_workdir}', ignore_errors=True)"
            subprocess.run(
                ["colab", "exec", "-s", self.session_name, "--timeout", "30"],
                input=clean_cmd.encode(),
                capture_output=True,
                check=False
            )

    def print_summary(self, result: Dict[str, Any]):
        """Display a final summary report."""
        if HAS_RICH and console:
            table = Table(title="Git Colab Clone Summary", show_header=True, header_style="bold magenta")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Repository", self.repo_url)
            table.add_row("Branch/Tag", self.branch or "default")
            table.add_row("Clone Depth", str(self.depth) if self.depth else "full")
            table.add_row("Uncompressed Size", format_bytes(result.get("raw_size", 0)))
            table.add_row("Zip Size", format_bytes(result.get("zip_size", 0)))
            if os.path.exists(self.local_zip):
                table.add_row("Zip Archive", self.local_zip)
            if self.extract:
                table.add_row("Extracted Folder", self.local_extract_dir)

            console.print(Panel(table, expand=False))
        else:
            print("\n=== Summary ===")
            print(f"Repository:        {self.repo_url}")
            print(f"Uncompressed Size: {format_bytes(result.get('raw_size', 0))}")
            print(f"Zip Size:          {format_bytes(result.get('zip_size', 0))}")
            if os.path.exists(self.local_zip):
                print(f"Zip File:          {self.local_zip}")
            if self.extract:
                print(f"Extracted Folder:  {self.local_extract_dir}")
            print("================\n")

    def run(self):
        """Execute full clone -> zip -> download workflow."""
        self.check_prerequisites()
        self.ensure_session()
        result = self.execute_remote_clone_and_zip()
        self.download_zip(result)
        self.extract_zip()
        self.print_summary(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="git_clone_colab",
        description="Clone large Git repositories via Google Colab, package them as zip, and download to local machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  git_clone_colab https://github.com/torvalds/linux.git
  git_clone_colab https://github.com/huggingface/transformers --depth 1
  git_clone_colab https://github.com/pytorch/pytorch.git -o ~/Downloads --extract
  git_clone_colab git@github.com:user/repo.git -b main --no-git
        """
    )

    parser.add_argument("repo_link", help="Git repository URL to clone (HTTPS or SSH)")
    parser.add_argument("-o", "--output-dir", default=".", help="Local destination directory (default: current directory)")
    parser.add_argument("-n", "--name", help="Custom name for the downloaded zip and directory (default: inferred from repo URL)")
    parser.add_argument("-b", "--branch", help="Specific branch or tag to clone")
    parser.add_argument("--depth", type=int, help="Create a shallow clone with a history truncated to the specified depth")
    parser.add_argument("--submodules", action="store_true", help="Recursively clone git submodules")
    parser.add_argument("--no-git", action="store_true", help="Omit the .git folder from the zip to significantly reduce size")
    parser.add_argument("-x", "--extract", "--unzip", action="store_true", help="Automatically unzip archive to a folder upon download")
    parser.add_argument("--remove-zip", action="store_true", help="Remove the zip archive after extraction (requires -x/--extract)")
    parser.add_argument("-s", "--session", help="Reuse an existing Colab session instead of spinning up a new one")
    parser.add_argument("--keep-session", action="store_true", help="Do not stop the Colab session when finished")
    parser.add_argument("--gpu", choices=["T4", "L4", "A100"], help="Request a GPU runtime for the Colab session (default: CPU)")
    parser.add_argument("--high-mem", action="store_true", help="Request high-memory machine shape in Colab")
    parser.add_argument("--timeout", type=float, default=1800.0, help="Execution timeout in seconds for clone/zip (default: 1800s)")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    cloner = ColabCloner(
        repo_url=args.repo_link,
        output_dir=args.output_dir,
        custom_name=args.name,
        branch=args.branch,
        depth=args.depth,
        submodules=args.submodules,
        no_git=args.no_git,
        extract=args.extract,
        remove_zip=args.remove_zip,
        session_name=args.session,
        keep_session=args.keep_session,
        timeout=args.timeout,
        gpu=args.gpu,
        high_mem=args.high_mem,
    )
    cloner.run()


if __name__ == "__main__":
    main()
