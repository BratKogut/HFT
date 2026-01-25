#!/usr/bin/env python3
"""
HFT System - Deployment Test Script
====================================

Quick verification script to test HFT system in your environment.

Usage:
    python test_deployment.py

Expected runtime: 30-60 seconds
"""

import sys
import time
import importlib
from pathlib import Path

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


# ============================================================================
# TEST 1: PYTHON VERSION
# ============================================================================

def test_python_version():
    """Test Python version"""
    print_header("TEST 1: Python Version")
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    print(f"Python version: {version_str}")
    
    if version.major == 3 and version.minor >= 11:
        print_success(f"Python {version_str} is compatible")
        return True
    else:
        print_error(f"Python {version_str} is too old (need 3.11+)")
        return False


# ============================================================================
# TEST 2: DEPENDENCIES
# ============================================================================

def test_dependencies():
    """Test required dependencies"""
    print_header("TEST 2: Dependencies")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'numpy',
        'pandas',
        'redis',
        'loguru',
        'pydantic',
        'orjson',
    ]
    
    failed = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print_success(f"{package:15} - installed")
        except ImportError:
            print_error(f"{package:15} - MISSING")
            failed.append(package)
    
    if failed:
        print_error(f"\n{len(failed)} packages missing: {', '.join(failed)}")
        print_info("Run: pip install -r backend/requirements.txt")
        return False
    else:
        print_success(f"\nAll {len(required_packages)} required packages installed")
        return True


# ============================================================================
# TEST 3: FILE STRUCTURE
# ============================================================================

def test_file_structure():
    """Test repository file structure"""
    print_header("TEST 3: File Structure")
    
    required_paths = [
        'backend/core/l0_sanitizer.py',
        'backend/core/tca_analyzer.py',
        'backend/core/deterministic_fee_model.py',
        'backend/core/drb_guard.py',
        'backend/core/wal_logger.py',
        'backend/core/reason_codes.py',
        'backend/core/event_bus.py',
        'backend/engine/production_engine_v2.py',
        'backend/strategies/optimized_liquidation_hunter.py',
        'backend/backtesting/optimized_backtest.py',
        'data/btc_usdt_30d_synthetic.csv',
    ]
    
    missing = []
    
    for path_str in required_paths:
        path = Path(path_str)
        if path.exists():
            size = path.stat().st_size
            print_success(f"{path_str:50} ({size:>8,} bytes)")
        else:
            print_error(f"{path_str:50} MISSING")
            missing.append(path_str)
    
    if missing:
        print_error(f"\n{len(missing)} files missing")
        return False
    else:
        print_success(f"\nAll {len(required_paths)} required files present")
        return True


# ============================================================================
# TEST 4: IMPORTS
# ============================================================================

def test_imports():
    """Test core module imports"""
    print_header("TEST 4: Core Module Imports")
    
    # Add backend to path
    sys.path.insert(0, str(Path(__file__).parent / 'backend'))
    
    modules = [
        ('core.l0_sanitizer', 'L0Sanitizer'),
        ('core.tca_analyzer', 'TCAAnalyzer'),
        ('core.deterministic_fee_model', 'DeterministicFeeModel'),
        ('core.drb_guard', 'DRBGuard'),
        ('core.wal_logger', 'WALLogger'),
        ('core.reason_codes', 'ReasonCodeTracker'),
        ('core.event_bus', 'EventBus'),
        ('strategies.optimized_liquidation_hunter', 'OptimizedLiquidationHunter'),
    ]
    
    failed = []
    
    for module_name, class_name in modules:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            print_success(f"{module_name:40} → {class_name}")
        except Exception as e:
            print_error(f"{module_name:40} → FAILED: {e}")
            failed.append(module_name)
    
    if failed:
        print_error(f"\n{len(failed)} imports failed")
        return False
    else:
        print_success(f"\nAll {len(modules)} imports successful")
        return True


# ============================================================================
# TEST 5: DATA AVAILABILITY
# ============================================================================

def test_data():
    """Test data availability"""
    print_header("TEST 5: Test Data")
    
    import pandas as pd
    
    data_file = Path('data/btc_usdt_30d_synthetic.csv')
    
    if not data_file.exists():
        print_error(f"Data file not found: {data_file}")
        return False
    
    try:
        df = pd.read_csv(data_file)
        
        print(f"Data file: {data_file}")
        print(f"Size: {data_file.stat().st_size:,} bytes")
        print(f"Rows: {len(df):,}")
        print(f"Columns: {list(df.columns)}")
        
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print_error(f"Missing columns: {missing_cols}")
            return False
        
        print_success(f"Data loaded: {len(df):,} candles")
        return True
        
    except Exception as e:
        print_error(f"Failed to load data: {e}")
        return False


# ============================================================================
# TEST 6: BACKTEST PERFORMANCE
# ============================================================================

def test_backtest():
    """Test backtest performance"""
    print_header("TEST 6: Backtest Performance")
    
    sys.path.insert(0, str(Path(__file__).parent / 'backend'))
    
    try:
        from backtesting.optimized_backtest import OptimizedBacktest
        import pandas as pd
        
        # Load data
        print("Loading data...")
        data_file = Path('data/btc_usdt_30d_synthetic.csv')
        df = pd.read_csv(data_file)
        
        # Create backtest
        print("Initializing backtest...")
        backtest = OptimizedBacktest(initial_capital=10000.0)
        
        # Run backtest
        print("Running backtest...")
        start_time = time.time()
        results = backtest.run_backtest(data_file)
        duration = time.time() - start_time
        
        # Calculate speed
        total_ticks = len(df)
        speed = total_ticks / duration if duration > 0 else 0
        
        # Print results
        print(f"\nBacktest completed in {duration:.2f} seconds")
        print(f"Processed {total_ticks:,} ticks")
        print(f"Speed: {speed:,.0f} ticks/sec")
        
        print(f"\nResults:")
        print(f"  Return: {results.get('return_pct', 0):.2%}")
        print(f"  Win Rate: {results.get('win_rate', 0):.1%}")
        print(f"  Trades: {results.get('total_trades', 0)}")
        print(f"  Profit Factor: {results.get('profit_factor', 0):.2f}")
        
        # Check performance
        if speed < 5000:
            print_warning(f"Performance is slow ({speed:,.0f} ticks/sec < 5,000)")
        elif speed < 15000:
            print_success(f"Performance is acceptable ({speed:,.0f} ticks/sec)")
        else:
            print_success(f"Performance is excellent ({speed:,.0f} ticks/sec)")
        
        return True
        
    except Exception as e:
        print_error(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests"""
    print_header("HFT SYSTEM - DEPLOYMENT TEST")
    print("Testing system in your environment...\n")
    
    results = {}
    
    # Run tests
    results['Python Version'] = test_python_version()
    results['Dependencies'] = test_dependencies()
    results['File Structure'] = test_file_structure()
    results['Imports'] = test_imports()
    results['Data'] = test_data()
    results['Backtest'] = test_backtest()
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        if result:
            print_success(f"{test_name:25} PASSED")
        else:
            print_error(f"{test_name:25} FAILED")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.END}")
    
    if passed == total:
        print_success("\n🎉 ALL TESTS PASSED! System is ready!")
        print_info("\nNext steps:")
        print_info("  1. Review QUICK_START.md for usage")
        print_info("  2. Check WEEK3_OPTIMIZATION_ROADMAP.md for improvements")
        print_info("  3. Start paper trading preparation")
        return 0
    else:
        print_error(f"\n❌ {total - passed} tests failed")
        print_info("\nTroubleshooting:")
        print_info("  1. Check DEPLOYMENT_READINESS_CHECKLIST.md")
        print_info("  2. Run: pip install -r backend/requirements.txt")
        print_info("  3. Verify Python 3.11+ is installed")
        print_info("  4. Check logs for detailed errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
