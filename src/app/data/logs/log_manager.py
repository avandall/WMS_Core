"""
Log management utilities for WMS application.

Handles log rotation and automatic cleanup of old log files.
"""

import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List


class LogManager:
    """Manages log files with rotation and cleanup."""
    
    def __init__(self, log_dir: str = None):
        if log_dir is None:
            # Default to this script's directory
            self.log_dir = Path(__file__).parent
        else:
            self.log_dir = Path(log_dir)
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def cleanup_old_logs(self, days: int = 7) -> None:
        """Remove log files older than specified days."""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        for log_file in self.log_dir.glob("*.log*"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    print(f"Removed old log file: {log_file}")
            except OSError as e:
                print(f"Error removing log file {log_file}: {e}")
    
    def get_log_files(self) -> List[Path]:
        """Get list of all log files."""
        return list(self.log_dir.glob("*.log*"))
    
    def get_total_log_size(self) -> int:
        """Get total size of all log files in bytes."""
        return sum(f.stat().st_size for f in self.get_log_files())
    
    def setup_log_rotation(self, max_size_mb: int = 10, backup_count: int = 5) -> None:
        """Setup log rotation configuration."""
        # This would be used with Python's logging RotatingFileHandler
        self.max_size = max_size_mb * 1024 * 1024
        self.backup_count = backup_count
    
    def create_log_file_path(self, name: str) -> Path:
        """Create full path for log file."""
        return self.log_dir / f"{name}.log"
    
    def log_cleanup_info(self) -> None:
        """Log information about cleanup process."""
        log_files = self.get_log_files()
        total_size = self.get_total_log_size()
        
        print(f"Log cleanup completed:")
        print(f"  Total log files: {len(log_files)}")
        print(f"  Total size: {total_size / (1024*1024):.2f} MB")
        print(f"  Log directory: {self.log_dir}")


def setup_logging_with_cleanup(log_dir: str = None) -> None:
    """Setup logging with automatic cleanup."""
    # Initialize log manager
    log_manager = LogManager(log_dir)
    
    # Run cleanup on startup
    log_manager.cleanup_old_logs(days=7)
    
    # Log cleanup info
    log_manager.log_cleanup_info()
    
    # Setup logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_manager.create_log_file_path('app')),
            logging.FileHandler(log_manager.create_log_file_path('error')),
        ]
    )
    
    # Create separate error logger
    error_handler = logging.FileHandler(log_manager.create_log_file_path('error'))
    error_handler.setLevel(logging.ERROR)
    
    # Create audit logger for sensitive operations
    audit_handler = logging.FileHandler(log_manager.create_log_file_path('audit'))
    audit_handler.setLevel(logging.INFO)


if __name__ == "__main__":
    # Run cleanup manually if script is executed directly
    manager = LogManager()
    manager.cleanup_old_logs(days=7)
    manager.log_cleanup_info()
