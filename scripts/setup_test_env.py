#!/usr/bin/env python3
"""
Virtual environment setup script for ghoo test environment.

This script creates a safe, isolated Python virtual environment and installs
all necessary dependencies for running the ghoo test suite without requiring
system-level package installations.

Usage:
    python3 scripts/setup_test_env.py [--force] [--quiet]

Options:
    --force     Remove existing virtual environment and create fresh one
    --quiet     Suppress informational output
    --help      Show this help message
"""

import os
import sys
import subprocess
import venv
import shutil
from pathlib import Path
from typing import List, Optional
import argparse


class TestEnvironmentSetup:
    """Handles creation and management of test virtual environment."""
    
    def __init__(self, project_root: Optional[Path] = None):
        """Initialize setup manager.
        
        Args:
            project_root: Root directory of project (auto-detected if None)
        """
        self.project_root = project_root or Path(__file__).parent.parent
        self.venv_dir = self.project_root / ".venv"
        self.requirements_file = self.project_root / "pyproject.toml"
        
    def log(self, message: str, quiet: bool = False) -> None:
        """Log message unless in quiet mode."""
        if not quiet:
            print(f"[SETUP] {message}")
    
    def check_python_version(self) -> bool:
        """Check if Python version meets requirements."""
        version = sys.version_info
        if version.major != 3 or version.minor < 10:
            print(f"❌ Python 3.10+ required, found {version.major}.{version.minor}")
            return False
        return True
    
    def create_virtual_environment(self, force: bool = False, quiet: bool = False) -> bool:
        """Create virtual environment.
        
        Args:
            force: Remove existing venv if present
            quiet: Suppress output
            
        Returns:
            True if successful
        """
        if self.venv_dir.exists():
            if force:
                self.log(f"Removing existing virtual environment at {self.venv_dir}", quiet)
                shutil.rmtree(self.venv_dir)
            else:
                self.log(f"Virtual environment already exists at {self.venv_dir}", quiet)
                return True
        
        self.log(f"Creating virtual environment at {self.venv_dir}", quiet)
        try:
            venv.create(self.venv_dir, with_pip=True)
            self.log("✅ Virtual environment created successfully", quiet)
            return True
        except Exception as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False
    
    def get_pip_command(self) -> List[str]:
        """Get pip command for this virtual environment."""
        if os.name == 'nt':  # Windows
            return [str(self.venv_dir / "Scripts" / "python.exe"), "-m", "pip"]
        else:  # Unix-like
            return [str(self.venv_dir / "bin" / "python"), "-m", "pip"]
    
    def install_dependencies(self, quiet: bool = False) -> bool:
        """Install project dependencies from pyproject.toml.
        
        Args:
            quiet: Suppress output
            
        Returns:
            True if successful
        """
        if not self.requirements_file.exists():
            print(f"❌ Requirements file not found: {self.requirements_file}")
            return False
        
        self.log("Installing project dependencies", quiet)
        
        # First upgrade pip
        pip_cmd = self.get_pip_command()
        try:
            subprocess.run(
                pip_cmd + ["install", "--upgrade", "pip"],
                check=True,
                capture_output=quiet
            )
            self.log("✅ Pip upgraded successfully", quiet)
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Warning: Failed to upgrade pip: {e}")
        
        # Install the project in development mode with all dev dependencies
        try:
            # Use pip to install from pyproject.toml with dev dependencies
            subprocess.run(
                pip_cmd + ["install", "-e", ".[dev]", "--group", "dev"],
                cwd=self.project_root,
                check=True,
                capture_output=quiet
            )
            self.log("✅ Dependencies installed successfully", quiet)
            return True
        except subprocess.CalledProcessError:
            # Fallback: install dev dependencies separately
            self.log("Main installation failed, trying fallback method", quiet)
            try:
                # Install main package
                subprocess.run(
                    pip_cmd + ["install", "-e", "."],
                    cwd=self.project_root,
                    check=True,
                    capture_output=quiet
                )
                
                # Install dev dependencies manually
                dev_deps = [
                    "pytest>=8.4.1",
                    "pytest-httpx>=0.35.0", 
                    "python-dotenv>=1.0.0"
                ]
                
                subprocess.run(
                    pip_cmd + ["install"] + dev_deps,
                    check=True,
                    capture_output=quiet
                )
                
                self.log("✅ Dependencies installed via fallback method", quiet)
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install dependencies: {e}")
                return False
    
    def verify_installation(self, quiet: bool = False) -> bool:
        """Verify that installation was successful.
        
        Args:
            quiet: Suppress output
            
        Returns:
            True if verification passes
        """
        python_cmd = self.get_pip_command()[0]  # Get python executable path
        
        # Test 1: Can import ghoo
        try:
            subprocess.run(
                [python_cmd, "-c", "import ghoo.main; print('✅ ghoo module imports successfully')"],
                cwd=self.project_root,
                check=True,
                capture_output=quiet
            )
        except subprocess.CalledProcessError:
            print("❌ Failed to import ghoo module")
            return False
        
        # Test 2: Can run ghoo command
        try:
            subprocess.run(
                [python_cmd, "-m", "ghoo.main", "--version"],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            self.log("✅ ghoo CLI command works", quiet)
        except subprocess.CalledProcessError:
            print("❌ Failed to run ghoo CLI command")
            return False
        
        # Test 3: Can import test modules
        try:
            subprocess.run(
                [python_cmd, "-c", "from tests.environment import get_test_environment; print('✅ test modules import successfully')"],
                cwd=self.project_root,
                check=True,
                capture_output=quiet
            )
        except subprocess.CalledProcessError:
            print("❌ Failed to import test modules")
            return False
        
        return True
    
    def generate_activation_instructions(self, quiet: bool = False) -> None:
        """Generate instructions for using the virtual environment."""
        if quiet:
            return
            
        if os.name == 'nt':  # Windows
            activate_cmd = str(self.venv_dir / "Scripts" / "activate.bat")
            python_cmd = str(self.venv_dir / "Scripts" / "python.exe")
        else:  # Unix-like
            activate_cmd = f"source {self.venv_dir / 'bin' / 'activate'}"
            python_cmd = str(self.venv_dir / "bin" / "python")
        
        print(f"\n🎉 Test environment setup complete!")
        print(f"\nTo use the virtual environment:")
        print(f"  {activate_cmd}")
        print(f"\nTo run tests:")
        print(f"  {python_cmd} -m pytest tests/")
        print(f"\nTo run ghoo CLI:")
        print(f"  {python_cmd} -m ghoo.main --help")
        print(f"\nVirtual environment location: {self.venv_dir}")
    
    def setup(self, force: bool = False, quiet: bool = False) -> bool:
        """Complete environment setup process.
        
        Args:
            force: Force recreation of virtual environment
            quiet: Suppress informational output
            
        Returns:
            True if setup successful
        """
        # Check Python version
        if not self.check_python_version():
            return False
        
        # Create virtual environment
        if not self.create_virtual_environment(force, quiet):
            return False
        
        # Install dependencies
        if not self.install_dependencies(quiet):
            return False
        
        # Verify installation
        if not self.verify_installation(quiet):
            return False
        
        # Show usage instructions
        self.generate_activation_instructions(quiet)
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up virtual environment for ghoo testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--force", 
        action="store_true",
        help="Remove existing virtual environment and create fresh one"
    )
    parser.add_argument(
        "--quiet", 
        action="store_true",
        help="Suppress informational output"
    )
    
    args = parser.parse_args()
    
    setup = TestEnvironmentSetup()
    success = setup.setup(force=args.force, quiet=args.quiet)
    
    if not success:
        print("\n❌ Setup failed. Please check the error messages above.")
        sys.exit(1)
    
    if not args.quiet:
        print("\n✅ Setup completed successfully!")


if __name__ == "__main__":
    main()