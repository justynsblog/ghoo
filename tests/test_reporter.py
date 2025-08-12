"""Test execution monitoring and reporting for ghoo test suite.

This module provides comprehensive test execution monitoring, reporting, and
analytics capabilities. It tracks test execution times, failure patterns,
mode usage, and provides detailed reports for test suite optimization.

Features:
- Real-time test execution monitoring
- Detailed execution time tracking and analysis
- Test failure categorization and reporting
- Mode usage statistics (live vs mock)
- Performance trend analysis
- CI/CD integration support
- Execution summaries and recommendations
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging

import pytest

logger = logging.getLogger(__name__)


class TestResult(Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    XFAIL = "xfail"     # Expected failure
    XPASS = "xpass"     # Unexpected pass


class TestMode(Enum):
    """Test execution mode."""
    LIVE = "live"
    MOCK = "mock"
    UNKNOWN = "unknown"


@dataclass
class TestExecution:
    """Represents a single test execution."""
    
    # Test identification
    test_id: str                    # Unique test identifier
    test_name: str                  # Human-readable test name
    test_file: str                  # Test file path
    test_category: str              # unit, integration, e2e
    test_markers: List[str]         # Pytest markers
    
    # Execution details
    result: TestResult              # Test result status
    execution_time: float           # Execution time in seconds
    setup_time: float               # Setup time in seconds
    teardown_time: float            # Teardown time in seconds
    
    # Environment context
    mode: TestMode                  # Live or mock mode
    execution_method: str           # subprocess_uv, subprocess_python, typer
    python_version: str             # Python version used
    platform: str                   # Operating system
    
    # Timestamps
    start_time: datetime            # Test start timestamp
    end_time: datetime              # Test end timestamp
    
    # Additional metadata
    failure_reason: Optional[str] = None    # Failure details
    skip_reason: Optional[str] = None       # Skip reason
    warnings: List[str] = None              # Warning messages
    fixtures_used: List[str] = None         # Fixtures used by test
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.fixtures_used is None:
            self.fixtures_used = []
    
    @property
    def total_time(self) -> float:
        """Total time including setup and teardown."""
        return self.setup_time + self.execution_time + self.teardown_time
    
    @property
    def success(self) -> bool:
        """Whether the test was successful."""
        return self.result in [TestResult.PASSED, TestResult.XFAIL]


@dataclass
class TestSession:
    """Represents a complete test session."""
    
    session_id: str                 # Unique session identifier
    start_time: datetime           # Session start time
    end_time: Optional[datetime]   # Session end time
    
    # Environment information
    python_version: str
    platform: str
    pytest_version: str
    ghoo_version: Optional[str]
    
    # Configuration
    test_directory: str
    command_line: List[str]
    selected_tests: List[str]
    
    # Results
    executions: List[TestExecution]
    
    # Summary statistics
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    
    def __post_init__(self):
        if not hasattr(self, 'executions') or self.executions is None:
            self.executions = []
    
    @property
    def duration(self) -> Optional[timedelta]:
        """Total session duration."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100
    
    def update_summary(self):
        """Update summary statistics from executions."""
        self.total_tests = len(self.executions)
        self.passed = sum(1 for e in self.executions if e.result == TestResult.PASSED)
        self.failed = sum(1 for e in self.executions if e.result == TestResult.FAILED)
        self.skipped = sum(1 for e in self.executions if e.result == TestResult.SKIPPED)
        self.errors = sum(1 for e in self.executions if e.result == TestResult.ERROR)


class TestReporter:
    """Test execution reporter and analyzer."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(__file__).parent / "reports"
        self.output_dir.mkdir(exist_ok=True)
        
        self.current_session: Optional[TestSession] = None
        self.session_history: List[TestSession] = []
        
        # Load existing session history
        self._load_history()
    
    def start_session(self, session_id: Optional[str] = None) -> TestSession:
        """Start a new test session."""
        if session_id is None:
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Get environment information
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        platform = sys.platform
        pytest_version = pytest.__version__
        
        # Try to get ghoo version
        ghoo_version = None
        try:
            import ghoo
            ghoo_version = getattr(ghoo, '__version__', 'unknown')
        except ImportError:
            pass
        
        self.current_session = TestSession(
            session_id=session_id,
            start_time=datetime.now(),
            end_time=None,
            python_version=python_version,
            platform=platform,
            pytest_version=pytest_version,
            ghoo_version=ghoo_version,
            test_directory=str(Path(__file__).parent),
            command_line=sys.argv.copy(),
            selected_tests=[],
            executions=[]
        )
        
        return self.current_session
    
    def end_session(self):
        """End the current test session."""
        if self.current_session:
            self.current_session.end_time = datetime.now()
            self.current_session.update_summary()
            self.session_history.append(self.current_session)
            self._save_session(self.current_session)
            self.current_session = None
    
    def record_test_execution(self, execution: TestExecution):
        """Record a test execution."""
        if self.current_session:
            self.current_session.executions.append(execution)
    
    def _detect_test_mode(self, test_item) -> TestMode:
        """Detect test execution mode from markers and environment."""
        # Check for explicit mode markers
        if hasattr(test_item, 'markers'):
            marker_names = [marker.name for marker in test_item.iter_markers()]
            if 'live_only' in marker_names:
                return TestMode.LIVE
            elif 'mock_only' in marker_names:
                return TestMode.MOCK
        
        # Check environment
        if os.environ.get('TESTING_GITHUB_TOKEN'):
            return TestMode.LIVE
        
        return TestMode.MOCK
    
    def _detect_execution_method(self) -> str:
        """Detect CLI execution method from environment."""
        # This is a heuristic - in practice this would be set by the CLI executor
        test_type = os.environ.get('GHOO_TEST_TYPE', 'unit')
        if test_type == 'e2e':
            if os.system('which uv > /dev/null 2>&1') == 0:
                return 'subprocess_uv'
            else:
                return 'subprocess_python'
        elif test_type == 'integration':
            return 'mixed'
        else:
            return 'typer'
    
    def generate_session_report(self, session: Optional[TestSession] = None) -> str:
        """Generate a detailed session report."""
        if session is None:
            session = self.current_session
        
        if not session:
            return "No session data available"
        
        lines = []
        lines.append(f"📊 Test Session Report: {session.session_id}")
        lines.append("=" * 60)
        lines.append("")
        
        # Session overview
        lines.append("📋 Session Overview:")
        lines.append(f"  Start time: {session.start_time}")
        if session.end_time:
            lines.append(f"  End time: {session.end_time}")
            lines.append(f"  Duration: {session.duration}")
        lines.append(f"  Python: {session.python_version}")
        lines.append(f"  Platform: {session.platform}")
        lines.append(f"  Pytest: {session.pytest_version}")
        if session.ghoo_version:
            lines.append(f"  Ghoo: {session.ghoo_version}")
        lines.append("")
        
        # Test results summary
        lines.append("🎯 Results Summary:")
        lines.append(f"  Total tests: {session.total_tests}")
        lines.append(f"  Passed: {session.passed} ({session.passed/session.total_tests*100:.1f}%)" if session.total_tests > 0 else "  Passed: 0")
        lines.append(f"  Failed: {session.failed}")
        lines.append(f"  Skipped: {session.skipped}")
        lines.append(f"  Errors: {session.errors}")
        lines.append(f"  Success rate: {session.success_rate:.1f}%")
        lines.append("")
        
        # Performance analysis
        if session.executions:
            execution_times = [e.execution_time for e in session.executions if e.execution_time > 0]
            if execution_times:
                avg_time = sum(execution_times) / len(execution_times)
                max_time = max(execution_times)
                min_time = min(execution_times)
                
                lines.append("⚡ Performance Analysis:")
                lines.append(f"  Average execution time: {avg_time:.2f}s")
                lines.append(f"  Fastest test: {min_time:.2f}s")
                lines.append(f"  Slowest test: {max_time:.2f}s")
                lines.append("")
        
        # Category breakdown
        category_stats = {}
        mode_stats = {}
        for execution in session.executions:
            # Category statistics
            category = execution.test_category
            if category not in category_stats:
                category_stats[category] = {'total': 0, 'passed': 0, 'failed': 0}
            category_stats[category]['total'] += 1
            if execution.success:
                category_stats[category]['passed'] += 1
            else:
                category_stats[category]['failed'] += 1
            
            # Mode statistics
            mode = execution.mode.value
            if mode not in mode_stats:
                mode_stats[mode] = {'total': 0, 'passed': 0}
            mode_stats[mode]['total'] += 1
            if execution.success:
                mode_stats[mode]['passed'] += 1
        
        if category_stats:
            lines.append("📂 By Category:")
            for category, stats in category_stats.items():
                success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
                lines.append(f"  {category}: {stats['total']} tests ({success_rate:.1f}% success)")
            lines.append("")
        
        if mode_stats:
            lines.append("🔧 By Mode:")
            for mode, stats in mode_stats.items():
                success_rate = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
                lines.append(f"  {mode}: {stats['total']} tests ({success_rate:.1f}% success)")
            lines.append("")
        
        # Failure analysis
        failed_executions = [e for e in session.executions if not e.success and e.result != TestResult.SKIPPED]
        if failed_executions:
            lines.append("❌ Failed Tests:")
            for execution in failed_executions[:10]:  # Show up to 10 failures
                lines.append(f"  • {execution.test_name}")
                if execution.failure_reason:
                    lines.append(f"    {execution.failure_reason}")
            
            if len(failed_executions) > 10:
                lines.append(f"  ... and {len(failed_executions) - 10} more failures")
            lines.append("")
        
        # Slowest tests
        slow_executions = sorted(
            [e for e in session.executions if e.execution_time > 0],
            key=lambda x: x.execution_time,
            reverse=True
        )
        
        if slow_executions:
            lines.append("🐌 Slowest Tests:")
            for execution in slow_executions[:5]:  # Show top 5 slowest
                lines.append(f"  • {execution.test_name}: {execution.execution_time:.2f}s")
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_trend_analysis(self, days: int = 7) -> str:
        """Generate trend analysis from recent sessions."""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_sessions = [
            s for s in self.session_history 
            if s.start_time > cutoff_date
        ]
        
        if not recent_sessions:
            return f"No sessions found in the last {days} days"
        
        lines = []
        lines.append(f"📈 Trend Analysis (Last {days} Days)")
        lines.append("=" * 50)
        lines.append("")
        
        # Success rate trend
        success_rates = [s.success_rate for s in recent_sessions]
        avg_success_rate = sum(success_rates) / len(success_rates)
        
        lines.append(f"🎯 Success Rate Trend:")
        lines.append(f"  Average: {avg_success_rate:.1f}%")
        lines.append(f"  Best: {max(success_rates):.1f}%")
        lines.append(f"  Worst: {min(success_rates):.1f}%")
        lines.append("")
        
        # Performance trend
        avg_times = []
        for session in recent_sessions:
            if session.executions:
                execution_times = [e.execution_time for e in session.executions if e.execution_time > 0]
                if execution_times:
                    avg_times.append(sum(execution_times) / len(execution_times))
        
        if avg_times:
            lines.append(f"⚡ Performance Trend:")
            lines.append(f"  Average execution time: {sum(avg_times)/len(avg_times):.2f}s")
            lines.append(f"  Best average: {min(avg_times):.2f}s")
            lines.append(f"  Worst average: {max(avg_times):.2f}s")
            lines.append("")
        
        # Session frequency
        lines.append(f"📊 Activity:")
        lines.append(f"  Total sessions: {len(recent_sessions)}")
        lines.append(f"  Sessions per day: {len(recent_sessions)/days:.1f}")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_recommendations(self, session: Optional[TestSession] = None) -> List[str]:
        """Generate optimization recommendations."""
        if session is None:
            session = self.current_session
        
        if not session or not session.executions:
            return []
        
        recommendations = []
        
        # Performance recommendations
        slow_tests = [e for e in session.executions if e.execution_time > 30]
        if slow_tests:
            recommendations.append(
                f"Consider optimizing {len(slow_tests)} tests that take >30s to execute"
            )
        
        # Category balance recommendations
        category_counts = {}
        for execution in session.executions:
            category = execution.test_category
            category_counts[category] = category_counts.get(category, 0) + 1
        
        total_tests = len(session.executions)
        unit_percentage = (category_counts.get('unit', 0) / total_tests) * 100
        
        if unit_percentage < 60:
            recommendations.append(
                f"Unit tests are only {unit_percentage:.1f}% of tests. Consider adding more unit tests for faster feedback"
            )
        
        # Skip rate recommendations  
        if session.skipped > session.total_tests * 0.2:
            recommendations.append(
                f"High skip rate ({session.skipped/session.total_tests*100:.1f}%). Check test environment setup"
            )
        
        # Mode usage recommendations
        mode_counts = {}
        for execution in session.executions:
            mode = execution.mode.value
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
        
        if 'live' not in mode_counts and total_tests > 0:
            recommendations.append(
                "No tests ran in live mode. Consider setting up GitHub credentials for more comprehensive testing"
            )
        
        return recommendations
    
    def _save_session(self, session: TestSession):
        """Save session data to disk."""
        session_file = self.output_dir / f"{session.session_id}.json"
        
        # Convert to serializable format
        session_data = asdict(session)
        
        # Handle datetime objects
        session_data['start_time'] = session.start_time.isoformat()
        if session.end_time:
            session_data['end_time'] = session.end_time.isoformat()
        
        # Handle executions with datetime objects
        for execution_data in session_data['executions']:
            execution_data['start_time'] = execution_data['start_time'].isoformat()
            execution_data['end_time'] = execution_data['end_time'].isoformat()
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save session data: {e}")
    
    def _load_history(self):
        """Load session history from disk."""
        if not self.output_dir.exists():
            return
        
        for session_file in self.output_dir.glob("session_*.json"):
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                
                # Convert back from serialized format
                session_data['start_time'] = datetime.fromisoformat(session_data['start_time'])
                if session_data['end_time']:
                    session_data['end_time'] = datetime.fromisoformat(session_data['end_time'])
                
                # Convert executions
                executions = []
                for exec_data in session_data.get('executions', []):
                    exec_data['start_time'] = datetime.fromisoformat(exec_data['start_time'])
                    exec_data['end_time'] = datetime.fromisoformat(exec_data['end_time'])
                    exec_data['result'] = TestResult(exec_data['result'])
                    exec_data['mode'] = TestMode(exec_data['mode'])
                    executions.append(TestExecution(**exec_data))
                
                session_data['executions'] = executions
                session = TestSession(**session_data)
                self.session_history.append(session)
                
            except Exception as e:
                logger.error(f"Failed to load session from {session_file}: {e}")


# Pytest hooks for automatic reporting

def pytest_configure(config):
    """Configure pytest reporting."""
    # Initialize global reporter
    if not hasattr(config, '_ghoo_reporter'):
        config._ghoo_reporter = TestReporter()


def pytest_sessionstart(session):
    """Start test session reporting."""
    if hasattr(session.config, '_ghoo_reporter'):
        reporter = session.config._ghoo_reporter
        reporter.start_session()


def pytest_sessionfinish(session, exitstatus):
    """Finish test session reporting."""
    if hasattr(session.config, '_ghoo_reporter'):
        reporter = session.config._ghoo_reporter
        reporter.end_session()
        
        # Generate and print report
        if reporter.session_history:
            latest_session = reporter.session_history[-1]
            report = reporter.generate_session_report(latest_session)
            print("\n" + report)
            
            # Generate recommendations
            recommendations = reporter.generate_recommendations(latest_session)
            if recommendations:
                print("\n💡 Recommendations:")
                for rec in recommendations:
                    print(f"  • {rec}")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to capture test execution details."""
    outcome = yield
    report = outcome.get_result()
    
    # Only process the main test execution phase
    if call.when == 'call':
        reporter = getattr(item.config, '_ghoo_reporter', None)
        if reporter and reporter.current_session:
            # Extract test information
            test_id = item.nodeid
            test_name = item.name
            test_file = str(item.fspath.relto(item.config.rootdir))
            
            # Determine category from file path
            if '/unit/' in test_file:
                category = 'unit'
            elif '/integration/' in test_file:
                category = 'integration'
            elif '/e2e/' in test_file:
                category = 'e2e'
            else:
                category = 'unknown'
            
            # Extract markers
            markers = [marker.name for marker in item.iter_markers()]
            
            # Determine result
            if report.passed:
                result = TestResult.PASSED
            elif report.failed:
                result = TestResult.FAILED
            elif report.skipped:
                result = TestResult.SKIPPED
            else:
                result = TestResult.ERROR
            
            # Create execution record
            execution = TestExecution(
                test_id=test_id,
                test_name=test_name,
                test_file=test_file,
                test_category=category,
                test_markers=markers,
                result=result,
                execution_time=report.duration,
                setup_time=getattr(report, 'setup_duration', 0),
                teardown_time=getattr(report, 'teardown_duration', 0),
                mode=reporter._detect_test_mode(item),
                execution_method=reporter._detect_execution_method(),
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}",
                platform=sys.platform,
                start_time=datetime.now() - timedelta(seconds=report.duration),
                end_time=datetime.now(),
                failure_reason=str(report.longrepr) if report.failed else None,
                skip_reason=str(report.longrepr) if report.skipped else None
            )
            
            reporter.record_test_execution(execution)


if __name__ == "__main__":
    # CLI interface for reporting
    import argparse
    
    parser = argparse.ArgumentParser(description="Test execution reporting")
    parser.add_argument(
        "--report",
        help="Generate report for specific session ID (or 'latest')"
    )
    parser.add_argument(
        "--trends",
        type=int,
        default=7,
        help="Show trend analysis for N days"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available sessions"
    )
    
    args = parser.parse_args()
    
    reporter = TestReporter()
    
    if args.list:
        print("Available Sessions:")
        for session in reporter.session_history:
            print(f"  {session.session_id}: {session.start_time} ({session.total_tests} tests)")
    
    elif args.report:
        if args.report == 'latest':
            if reporter.session_history:
                session = reporter.session_history[-1]
                print(reporter.generate_session_report(session))
            else:
                print("No sessions available")
        else:
            # Find session by ID
            session = next(
                (s for s in reporter.session_history if s.session_id == args.report),
                None
            )
            if session:
                print(reporter.generate_session_report(session))
            else:
                print(f"Session {args.report} not found")
    
    elif args.trends:
        print(reporter.generate_trend_analysis(args.trends))
    
    else:
        # Default: show latest session report
        if reporter.session_history:
            session = reporter.session_history[-1]
            print(reporter.generate_session_report(session))
            
            recommendations = reporter.generate_recommendations(session)
            if recommendations:
                print("\n💡 Recommendations:")
                for rec in recommendations:
                    print(f"  • {rec}")
        else:
            print("No test sessions available")