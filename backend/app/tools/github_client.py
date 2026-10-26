"""GitHub API client for repository management and cloning."""
import base64
import os
import re
import shutil
import subprocess
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

from github import Github, GithubException, Repository as GithubRepo
from git import Repo, GitCommandError
from cryptography.fernet import Fernet, InvalidToken

from .redis_client import get_redis_client


class WorkspaceBusyError(RuntimeError):
    """Raised when another operation already holds the clone workspace."""


class GitHubClient:
    """Client for GitHub API operations and repository cloning."""
    
    def __init__(self, personal_access_token: Optional[str] = None):
        """
        Initialize GitHub client.
        
        Args:
            personal_access_token: GitHub PAT (optional, for public repos)
        """
        self.pat = personal_access_token
        self.github: Optional[Github] = None
        
        # Configuration from environment
        self.clone_base_path = os.getenv("CLONE_BASE_PATH", "./repos")
        self.clone_timeout = int(os.getenv("CLONE_TIMEOUT", "300"))
        self.max_clone_size_mb = int(os.getenv("MAX_CLONE_SIZE_MB", "500"))
        
        # Encryption key for PAT storage (resolved lazily so that public
        # repository operations never require a configured key)
        self._encryption_key = os.getenv("ENCRYPTION_KEY")
        self._cipher: Optional[Fernet] = None
        
        # Initialize GitHub connection if PAT provided
        if self.pat:
            self._connect()
    
    @property
    def cipher(self) -> Fernet:
        """Lazily built Fernet cipher for PAT encryption."""
        if self._cipher is None:
            if not self._encryption_key:
                raise ValueError("ENCRYPTION_KEY not set in environment")
            self._cipher = Fernet(self._encryption_key.encode())
        return self._cipher
    
    def _connect(self) -> None:
        """Establish GitHub API connection."""
        try:
            self.github = Github(self.pat, timeout=30)
            # Test connection
            user = self.github.get_user()
            print(f"✓ GitHub connected as: {user.login}")
        except GithubException as e:
            print(f"✗ GitHub connection failed: {e}")
            self.github = None
    
    def is_connected(self) -> bool:
        """Check if GitHub API is connected."""
        if self.github is None:
            return False
        try:
            self.github.get_user()
            return True
        except GithubException:
            return False
    
    # ========================================================================
    # PAT Encryption/Decryption
    # ========================================================================
    
    def encrypt_pat(self, pat: str) -> str:
        """
        Encrypt a GitHub Personal Access Token.
        
        Args:
            pat: Plain text GitHub PAT
            
        Returns:
            Encrypted PAT (base64 string)
        """
        try:
            encrypted = self.cipher.encrypt(pat.encode())
            return encrypted.decode()
        except Exception as e:
            raise ValueError(f"PAT encryption failed: {e}")
    
    def decrypt_pat(self, encrypted_pat: str) -> str:
        """
        Decrypt a GitHub Personal Access Token.
        
        Args:
            encrypted_pat: Encrypted PAT (base64 string)
            
        Returns:
            Plain text GitHub PAT
        """
        try:
            decrypted = self.cipher.decrypt(encrypted_pat.encode())
            return decrypted.decode()
        except InvalidToken:
            raise ValueError("Invalid encrypted PAT or encryption key")
        except Exception as e:
            raise ValueError(f"PAT decryption failed: {e}")
    
    # ========================================================================
    # Repository Information
    # ========================================================================
    
    def get_repo_info(self, repo_url: str) -> Dict[str, Any]:
        """
        Get repository information from GitHub API.
        
        Args:
            repo_url: GitHub repository URL or owner/repo format
            
        Returns:
            Dictionary with repository metadata
            
        Raises:
            ValueError: If repo URL is invalid or repo not found
        """
        if not self.is_connected():
            raise ValueError("GitHub client not connected (PAT required)")
        
        try:
            # Parse repo identifier
            repo_identifier = self._parse_repo_identifier(repo_url)
            
            # Fetch repository from GitHub
            repo: GithubRepo = self.github.get_repo(repo_identifier)
            
            # Extract metadata
            return {
                "github_id": repo.id,
                "full_name": repo.full_name,
                "owner_login": repo.owner.login,
                "repo_name": repo.name,
                "description": repo.description,
                "default_branch": repo.default_branch,
                "is_private": repo.private,
                "stars_count": repo.stargazers_count,
                "language": repo.language,
                "url": repo.html_url,
                "clone_url": repo.clone_url,
                "size_kb": repo.size,  # GitHub returns size in KB
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
            }
            
        except GithubException as e:
            if e.status == 404:
                raise ValueError(f"Repository not found: {repo_url}")
            elif e.status == 403:
                raise ValueError(f"Access denied (rate limit or private repo): {repo_url}")
            else:
                raise ValueError(f"GitHub API error: {e}")
    
    @staticmethod
    def _parse_repo_identifier(repo_url: str) -> str:
        """
        Parse repository identifier from URL or owner/repo format.
        
        Args:
            repo_url: GitHub URL or owner/repo
            
        Returns:
            Repository identifier in "owner/repo" format
            
        Examples:
            "https://github.com/owner/repo" -> "owner/repo"
            "github.com/owner/repo" -> "owner/repo"
            "owner/repo" -> "owner/repo"
        """
        raw = (repo_url or "").strip()
        
        # Strip scheme and host
        if "://" in raw:
            raw = raw.split("://", 1)[1]
        raw = raw.split("?", 1)[0].split("#", 1)[0]
        raw = raw.split("@")[-1]
        raw = raw.split(":", 1)[0]
        
        if raw.lower().startswith("www."):
            raw = raw[4:]
        if raw.lower().startswith("github.com/"):
            raw = raw[len("github.com/"):]
        
        raw = raw.rstrip("/")
        if raw.endswith(".git"):
            raw = raw[:-len(".git")]
        
        parts = raw.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError(f"Invalid repository identifier: {repo_url}")
        
        owner, repo_name = parts
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo_name):
            raise ValueError(f"Invalid repository identifier: {repo_url}")
        if owner in (".", "..") or repo_name in (".", ".."):
            raise ValueError(f"Invalid repository identifier: {repo_url}")
        
        return f"{owner}/{repo_name}"
    
    # ========================================================================
    # Repository Cloning
    # ========================================================================
    
    def clone_repository(
        self,
        repo_url: str,
        user_id: int,
        repo_id: int,
        branch: Optional[str] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Clone a GitHub repository with caching support.
        
        Args:
            repo_url: GitHub repository URL
            user_id: User ID (for path isolation)
            repo_id: Repository ID (for cache key)
            branch: Branch to clone (default: main/master)
            use_cache: Check Redis cache before cloning
            
        Returns:
            Dictionary with clone metadata
            
        Raises:
            ValueError: If cloning fails
        """
        redis_client = get_redis_client()
        
        # Check cache first
        if use_cache and redis_client.is_connected():
            cached = redis_client.get_clone_metadata(user_id, repo_id)
            if cached and cached.get("clone_status") == "cloned":
                # Verify local path still exists
                clone_path = cached.get("clone_path")
                if clone_path and os.path.exists(clone_path):
                    print(f"✓ Using cached clone: {clone_path}")
                    return cached
                else:
                    # Cache invalid, delete it
                    redis_client.delete_clone_metadata(user_id, repo_id)
        
        # Parse repo identifier
        repo_identifier = self._parse_repo_identifier(repo_url)
        owner, repo_name = repo_identifier.split("/")
        
        # Determine clone path
        clone_path = self._get_clone_path(user_id, owner, repo_name)
        
        # Ensure parent directory exists
        Path(clone_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Build clone URL (never carries credentials)
        clone_url = self._build_clone_url(repo_url)
        
        # Perform shallow clone
        lock_path = f"{clone_path}.lock"
        lock_fd = self._acquire_workspace_lock(lock_path)
        try:
            # Remove stale clone of the same repository only
            if os.path.exists(clone_path):
                print(f"⚠ Removing existing clone: {clone_path}")
                shutil.rmtree(clone_path)
            
            print(f"🔄 Cloning repository: {repo_identifier}")
            start_time = datetime.utcnow()
            
            # Clone with depth=1 for speed (shallow clone)
            try:
                self._run_git_clone(clone_url, clone_path, branch)
            except GitCommandError as e:
                error_msg = self._format_git_error(e)
                print(f"✗ {error_msg}")
                self._remove_partial_clone(clone_path)
                raise ValueError(error_msg)
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            # Verify the checkout and capture the actual commit SHA
            commit_sha, active_branch = self._verify_checkout(clone_path, branch)
            
            # Calculate clone size
            clone_size_mb = self._get_directory_size_mb(clone_path)
            
            print(f"✓ Clone completed: {clone_path} ({clone_size_mb:.2f} MB, {duration:.1f}s)")
            print(f"✓ Branch: {active_branch} @ {commit_sha[:12]}")
            
            # Prepare metadata
            metadata = {
                "user_id": user_id,
                "repo_id": repo_id,
                "clone_path": clone_path,
                "clone_status": "cloned",
                "cloned_at": end_time.isoformat(),
                "clone_size_mb": clone_size_mb,
                "clone_duration_seconds": duration,
                "branch": active_branch,
                "commit_sha": commit_sha,
                "redis_cache_key": f"clone:{user_id}:{repo_id}",
            }
            
            # Cache metadata
            if redis_client.is_connected():
                redis_client.set_clone_metadata(user_id, repo_id, metadata)
            
            return metadata
            
        except ValueError:
            self._remove_partial_clone(clone_path)
            raise
        except Exception as e:
            error_msg = f"Unexpected clone error: {e}"
            print(f"✗ {error_msg}")
            self._remove_partial_clone(clone_path)
            raise ValueError(error_msg)
        finally:
            self._release_workspace_lock(lock_fd, lock_path)

    # ------------------------------------------------------------------
    # Clone execution
    # ------------------------------------------------------------------

    def _run_git_clone(self, clone_url: str, clone_path: str, branch: Optional[str]) -> None:
        """
        Perform a shallow clone under a hard timeout.

        GitPython's ``kill_after_timeout`` is not supported on Windows, so the
        clone is executed directly and bounded by ``subprocess.run``. The
        command line never carries credentials: authentication travels through
        the ``GIT_CONFIG_*`` environment variables built by ``_build_git_env``.

        Raises:
            GitCommandError: when git fails or exceeds the timeout.
        """
        destination = str(Path(clone_path).resolve())
        command = ["git", "clone", "--depth", "1", "--single-branch"]
        if branch:
            command.extend(["--branch", branch])
        command.extend(["--", clone_url, destination])

        try:
            completed = subprocess.run(
                command,
                cwd=str(Path(destination).parent),
                env=self._build_git_env(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.clone_timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitCommandError(
                command,
                -1,
                stderr=f"fatal: clone timed out after {self.clone_timeout} seconds",
            ) from exc
        except FileNotFoundError as exc:
            raise GitCommandError(
                command, -1, stderr="fatal: git executable not found on this host"
            ) from exc

        if completed.returncode != 0:
            raise GitCommandError(
                command,
                completed.returncode,
                stderr=completed.stderr,
                stdout=completed.stdout,
            )

    @staticmethod
    def _remove_partial_clone(clone_path: str) -> None:
        """Delete an incomplete clone so the workspace can be reused."""
        try:
            shutil.rmtree(clone_path)
        except OSError:
            pass
    
    # ------------------------------------------------------------------
    # Credential-free cloning helpers
    # ------------------------------------------------------------------
    
    def _build_git_env(self) -> Dict[str, str]:
        """
        Build the environment used for the git clone.
        
        The PAT is injected as a per-invocation HTTP authorization header via
        GIT_CONFIG_* environment variables. It never appears in the command
        line, in the process arguments, or in the cloned repository's config.
        """
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        
        if self.pat:
            credentials = base64.b64encode(
                f"x-access-token:{self.pat}".encode()
            ).decode()
            env["GIT_CONFIG_COUNT"] = "1"
            env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
            env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {credentials}"
        
        return env
    
    @staticmethod
    def _acquire_workspace_lock(lock_path: str) -> int:
        """
        Acquire an exclusive lock for a clone workspace.
        
        Raises:
            WorkspaceBusyError: If another operation holds the workspace.
        """
        deadline = time.time() + 30
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                return fd
            except FileExistsError:
                if time.time() > deadline:
                    raise WorkspaceBusyError(
                        "Clone workspace is busy; another operation is in progress"
                    )
                time.sleep(1)
            except OSError as e:
                raise ValueError(f"Could not lock clone workspace: {e}")
    
    @staticmethod
    def _release_workspace_lock(fd: int, lock_path: str) -> None:
        """Release a previously acquired workspace lock."""
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.remove(lock_path)
        except OSError:
            pass
    
    def _verify_checkout(self, clone_path: str, branch: Optional[str]) -> Tuple[str, str]:
        """
        Verify the cloned checkout and read its actual commit SHA.
        
        Raises:
            ValueError: If the clone did not produce a usable checkout.
        """
        if not os.path.isdir(os.path.join(clone_path, ".git")):
            raise ValueError("Clone did not produce a valid git checkout")
        
        try:
            repo = Repo(clone_path)
            commit_sha = repo.head.commit.hexsha
            active_branch = repo.active_branch.name
        except Exception as e:
            raise ValueError(f"Could not verify cloned checkout: {e}")
        
        if branch and active_branch != branch:
            raise ValueError(
                f"Checked out branch '{active_branch}' does not match requested branch '{branch}'"
            )
        
        return commit_sha, active_branch
    
    @staticmethod
    def _format_git_error(error: GitCommandError) -> str:
        """Build a sanitized, user-safe message from a git failure."""
        stderr = getattr(error, "stderr", "") or ""
        lines = [line.strip() for line in stderr.splitlines() if line.strip()]
        
        # Git reports credential problems without echoing the secret itself
        for line in lines:
            lowered = line.lower()
            if "authentication failed" in lowered:
                return "GitHub authentication failed. Check the access token and its repository permissions."
            if "repository not found" in lowered:
                return "Repository not found or access denied. Check the URL and token permissions."
            if "remote branch" in lowered and "not found" in lowered:
                return f"Branch not found in repository: {line}"
            if "could not resolve host" in lowered or "connection timed out" in lowered:
                return "Network error while contacting GitHub."
        
        if lines:
            return f"Git clone failed: {lines[-1][:300]}"
        return "Git clone failed."
    
    def _get_clone_path(self, user_id: int, owner: str, repo_name: str) -> str:
        """
        Generate clone path for repository.
        
        Format: ./repos/{user_id}/{owner}_{repo_name}/
        
        Args:
            user_id: User ID
            owner: GitHub repository owner
            repo_name: Repository name
            
        Returns:
            Absolute path to clone directory
        """
        base_path = Path(self.clone_base_path).resolve()
        clone_path = base_path / str(user_id) / f"{owner}_{repo_name}"
        return str(clone_path)
    
    def _build_clone_url(self, repo_url: str) -> str:
        """
        Build the clone URL for a repository.
        
        The URL never carries credentials: authentication is provided through a
        per-invocation HTTP header so that no token is written into the cloned
        repository's remote configuration.
        
        Args:
            repo_url: GitHub repository URL
            
        Returns:
            Credential-free clone URL
        """
        repo_identifier = self._parse_repo_identifier(repo_url)
        return f"https://github.com/{repo_identifier}.git"
    
    @staticmethod
    def _get_directory_size_mb(directory: str) -> float:
        """
        Calculate directory size in megabytes.
        
        Args:
            directory: Path to directory
            
        Returns:
            Size in MB
        """
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
        except Exception as e:
            print(f"⚠ Error calculating directory size: {e}")
            return 0.0
        
        return total_size / (1024 * 1024)  # Convert to MB
    
    # ========================================================================
    # Repository Updates
    # ========================================================================
    
    def update_repository(self, clone_path: str) -> Dict[str, Any]:
        """
        Update an existing cloned repository (git pull).
        
        Args:
            clone_path: Path to cloned repository
            
        Returns:
            Update metadata
            
        Raises:
            ValueError: If update fails
        """
        if not os.path.exists(clone_path):
            raise ValueError(f"Clone path does not exist: {clone_path}")
        
        try:
            print(f"🔄 Updating repository: {clone_path}")
            start_time = datetime.utcnow()
            
            repo = Repo(clone_path)
            origin = repo.remotes.origin
            origin.pull()
            
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            print(f"✓ Repository updated ({duration:.1f}s)")
            
            return {
                "updated_at": end_time.isoformat(),
                "update_duration_seconds": duration,
                "status": "updated"
            }
            
        except GitCommandError as e:
            error_msg = f"Git pull failed: {e}"
            print(f"✗ {error_msg}")
            raise ValueError(error_msg)
    
    def delete_clone(self, user_id: int, repo_id: int, clone_path: str) -> bool:
        """
        Delete a cloned repository from filesystem and cache.
        
        Args:
            user_id: User ID
            repo_id: Repository ID
            clone_path: Path to cloned repository
            
        Returns:
            True if successful
        """
        try:
            # Delete from filesystem
            if os.path.exists(clone_path):
                shutil.rmtree(clone_path)
                print(f"✓ Deleted clone: {clone_path}")
            
            # Delete from cache
            redis_client = get_redis_client()
            if redis_client.is_connected():
                redis_client.delete_clone_metadata(user_id, repo_id)
            
            return True
            
        except Exception as e:
            print(f"✗ Delete clone failed: {e}")
            return False
    
    # ========================================================================
    # Validation
    # ========================================================================
    
    @staticmethod
    def validate_repo_url(repo_url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub repository URL format.
        
        Only github.com hosts (and the bare ``owner/repo`` shorthand) are
        accepted so that a URL can never redirect the clone elsewhere.
        
        Args:
            repo_url: Repository URL to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not repo_url or not repo_url.strip():
            return False, "Repository URL cannot be empty"
        
        raw = repo_url.strip()
        lowered = raw.lower()
        
        # Full URL: only github.com is supported
        if "://" in raw:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(raw)
            except Exception:
                return False, "Invalid repository URL"
            host = (parsed.netloc or "").lower().split("@")[-1].split(":")[0]
            if host not in ("github.com", "www.github.com"):
                return False, f"Unsupported repository host '{host}'. Only github.com is allowed."
        elif lowered.startswith("github.com/") or lowered.startswith("www.github.com/"):
            pass
        elif "/" not in raw:
            return False, "Repository URL must include an owner and repository name"
        
        try:
            GitHubClient._parse_repo_identifier(raw)
            return True, None
        except ValueError as e:
            return False, str(e)
    
    @staticmethod
    def validate_pat(pat: str) -> Tuple[bool, Optional[str]]:
        """
        Validate GitHub Personal Access Token format.
        
        Args:
            pat: GitHub PAT to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not pat:
            return False, "PAT cannot be empty"
        
        # GitHub PAT format: ghp_... (classic) or github_pat_... (fine-grained)
        if not (pat.startswith("ghp_") or pat.startswith("github_pat_")):
            return False, "Invalid PAT format (must start with 'ghp_' or 'github_pat_')"
        
        if len(pat) < 20:
            return False, "PAT too short (minimum 20 characters)"
        
        return True, None


# Helper functions for quick operations
def encrypt_github_pat(pat: str) -> str:
    """Encrypt a GitHub PAT (convenience function)."""
    client = GitHubClient()
    return client.encrypt_pat(pat)


def decrypt_github_pat(encrypted_pat: str) -> str:
    """Decrypt a GitHub PAT (convenience function)."""
    client = GitHubClient()
    return client.decrypt_pat(encrypted_pat)