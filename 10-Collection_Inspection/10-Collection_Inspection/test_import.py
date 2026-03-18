import sys, os, pathlib
print("Testing imports...")
try: import run_daily_report_v4_6; print("run_daily_report_v4_6 imported successfully.")
except Exception as e: print(f"Failed to import run_daily_report_v4_6: {e}")
try: import run_cashloan_report_v4_6; print("run_cashloan_report_v4_6 imported successfully.")
except Exception as e: print(f"Failed to import run_cashloan_report_v4_6: {e}")
print("Done.")
