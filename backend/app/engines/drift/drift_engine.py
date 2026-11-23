from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import difflib

class ConfigDriftEngine:
    """
    Compares running configuration against approved baseline snapshots,
    detecting unauthorized changes, missing VLANs, modified ACLs, or changed interface states.
    """

    @staticmethod
    def compare_configs(baseline_text: str, current_text: str) -> Dict[str, Any]:
        baseline_lines = [line.strip() for line in baseline_text.strip().splitlines() if line.strip() and not line.strip().startswith('!')]
        current_lines = [line.strip() for line in current_text.strip().splitlines() if line.strip() and not line.strip().startswith('!')]

        differ = difflib.Differ()
        diff = list(differ.compare(baseline_lines, current_lines))

        added = [line[2:] for line in diff if line.startswith('+ ')]
        removed = [line[2:] for line in diff if line.startswith('- ')]

        drift_detected = len(added) > 0 or len(removed) > 0
        severity = "none"

        if drift_detected:
            # Analyze severity based on keywords
            critical_keywords = ["vlan", "allowed", "shutdown", "access-list", "ospf", "ip route", "default-gateway"]
            is_critical = any(any(kw in line.lower() for kw in critical_keywords) for line in added + removed)
            severity = "high" if is_critical else "medium"

        unified = list(difflib.unified_diff(
            baseline_lines,
            current_lines,
            fromfile="baseline-config",
            tofile="current-running-config",
            lineterm=""
        ))

        return {
            "drift_detected": drift_detected,
            "severity": severity,
            "added_lines": added,
            "removed_lines": removed,
            "diff_unified": "\n".join(unified),
            "total_differences": len(added) + len(removed)
        }
