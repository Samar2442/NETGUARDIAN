from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.models import (
    ConfigSnapshot,
    Device,
    NetworkInterface,
    NetworkLink,
    Route,
    SecurityDetection,
    Student,
    VLAN,
)


def _latest_configs_map(db: Session) -> Dict[str, str]:
    snaps = db.query(ConfigSnapshot).order_by(ConfigSnapshot.created_at.desc()).limit(500).all()
    cfg_map: Dict[str, str] = {}
    for s in snaps:
        if s.device_id not in cfg_map and s.content:
            cfg_map[s.device_id] = s.content
    return cfg_map


def _score_severity(score: float, status: str) -> str:
    if status in ("NOT_ASSESSED", "UNKNOWN"):
        return "MEDIUM"
    if score >= 85.0:
        return "LOW"
    if score >= 65.0:
        return "MEDIUM"
    if score >= 40.0:
        return "HIGH"
    return "CRITICAL"


class NetworkSecurityIntelligenceService:
    """
    Defensive Network Security Posture & Configuration Compliance Engine.
    Never invents firewall/ACL configurations and never awards full compliance
    when evidence is missing (returns NOT_ASSESSED or UNKNOWN).
    """

    @staticmethod
    def assess_vlan_segmentation(db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        vlans = db.query(VLAN).filter(VLAN.vlan_id.in_([10, 20, 30])).order_by(VLAN.vlan_id.asc()).all()
        links = db.query(NetworkLink).all()
        routes = db.query(Route).all()
        fw = db.query(Device).filter(Device.device_type == "firewall").first()
        cfg_map = _latest_configs_map(db)
        fw_cfg = cfg_map.get(fw.id, "") if fw else ""

        passed: List[str] = []
        failed: List[str] = []
        unknown: List[str] = []
        evidence: List[str] = []
        recommendations: List[str] = []
        vlan_results: List[Dict[str, Any]] = []

        for v in vlans:
            v_evidence = [f"VLAN {v.vlan_id} ({v.department}) subnet={v.subnet} status={v.status}."]
            trunks_carrying = [
                l.name for l in links
                if l.allowed_vlans and str(v.vlan_id) in [x.strip() for x in l.allowed_vlans.split(",")]
            ]
            v_evidence.append(f"Carried across {len(trunks_carrying)} trunk link(s).")
            # Separate VLAN IDs alone do NOT prove effective L3 isolation without ACL/firewall policy evidence
            fw_policy_present = bool(fw_cfg and "access-list" in fw_cfg.lower())
            if not fw_policy_present:
                v_status = "PARTIAL"
                v_unknown = [
                    "Inter-VLAN L3 ACL/firewall isolation policy evidence is not present in running_config."
                ]
                v_score = 55.0
                unknown.append(f"VLAN {v.vlan_id}: Missing inter-VLAN ACL/firewall policy evidence.")
                recommendations.append(
                    f"Document and enforce explicit inter-VLAN ACLs between VLAN {v.vlan_id} ({v.department}) and peer subnets."
                )
            else:
                v_status = "ASSESSED"
                v_unknown = []
                v_score = 88.0
                passed.append(f"VLAN {v.vlan_id}: Trunk & policy evidence present.")

            if v.status != "active":
                failed.append(f"VLAN {v.vlan_id} status is '{v.status}'.")
                v_score = max(20.0, v_score - 25.0)
            else:
                passed.append(f"VLAN {v.vlan_id} ({v.department}) is active and mapped to {v.subnet}.")

            evidence.extend(v_evidence)
            vlan_results.append({
                "vlan_id": v.vlan_id,
                "name": v.name,
                "department": v.department,
                "subnet": v.subnet,
                "status": v_status,
                "score": v_score,
                "evidence": v_evidence,
                "unknown_checks": v_unknown,
                "note": "Separate VLAN IDs alone do not prove effective L3 isolation without ACL/firewall policy evidence.",
            })

        avg_score = round(sum(r["score"] for r in vlan_results) / max(1, len(vlan_results)), 1)
        overall_status = "UNKNOWN" if not vlans else ("PARTIAL" if unknown else "ASSESSED")
        return {
            "assessment_category": "VLAN_SEGMENTATION",
            "score": avg_score if vlans else 0.0,
            "severity": _score_severity(avg_score, overall_status),
            "status": overall_status,
            "data_source": "SIMULATION",
            "evidence": evidence,
            "passed_checks": passed,
            "failed_checks": failed,
            "unknown_checks": unknown,
            "recommendations": list(dict.fromkeys(recommendations)),
            "vlans": vlan_results,
            "routes_count": len(routes),
            "assessment_timestamp": now,
        }

    @staticmethod
    def assess_acls(db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        devs = db.query(Device).filter(Device.asset_category != "student_endpoint").all()
        cfg_map = _latest_configs_map(db)
        acl_configs = [(d, cfg_map[d.id]) for d in devs if d.id in cfg_map and "access-list" in cfg_map[d.id].lower()]

        if not acl_configs:
            return {
                "assessment_category": "ACL_CONFIGURATION",
                "score": 0.0,
                "severity": "MEDIUM",
                "status": "NOT_ASSESSED",
                "data_source": "SIMULATION",
                "evidence": ["No explicit ACL configuration blocks found in stored device ConfigSnapshot records."],
                "passed_checks": [],
                "failed_checks": [],
                "unknown_checks": [
                    "Permitted/denied traffic rules cannot be verified.",
                    "Rule ordering and overly permissive any-any checks not assessed due to missing ACL config.",
                ],
                "recommendations": [
                    "Collect/attach explicit IOS access-list configurations on edge, core, and SVI interfaces before certifying ACL compliance."
                ],
                "assessment_timestamp": now,
            }

        passed, failed, unknown, evidence, recs = [], [], [], [], []
        for d, raw_cfg in acl_configs:
            cfg = raw_cfg.lower()
            evidence.append(f"{d.hostname}: ACL configuration detected.")
            if "permit ip any any" in cfg or "permit any any" in cfg:
                failed.append(f"{d.hostname}: Overly permissive 'permit any any' ACL entry detected.")
                recs.append(f"Restrict broad 'permit any any' ACL rules on {d.hostname} to least-privilege subnets.")
            else:
                passed.append(f"{d.hostname}: No broad 'permit any any' rule observed in ACL snippet.")
            if "access-class" not in cfg:
                unknown.append(f"{d.hostname}: VTY management-plane access-class restriction not verified.")
                recs.append(f"Apply 'access-class' on VTY lines of {d.hostname} to restrict management-plane access.")

        score = max(0.0, round(100.0 - len(failed) * 25.0 - len(unknown) * 15.0, 1))
        return {
            "assessment_category": "ACL_CONFIGURATION",
            "score": score,
            "severity": _score_severity(score, "ASSESSED"),
            "status": "PARTIAL" if unknown else "ASSESSED",
            "data_source": "SIMULATION",
            "evidence": evidence,
            "passed_checks": passed,
            "failed_checks": failed,
            "unknown_checks": unknown,
            "recommendations": list(dict.fromkeys(recs)),
            "assessment_timestamp": now,
        }

    @staticmethod
    def assess_firewall(db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        fw = db.query(Device).filter(Device.device_type == "firewall").first()
        cfg_map = _latest_configs_map(db)
        fw_cfg = cfg_map.get(fw.id, "") if fw else ""
        if not fw:
            return {
                "assessment_category": "FIREWALL_CONFIGURATION",
                "score": 0.0,
                "severity": "HIGH",
                "status": "NOT_ASSESSED",
                "data_source": "SIMULATION",
                "evidence": ["No firewall device record found in topology."],
                "passed_checks": [],
                "failed_checks": ["Perimeter firewall asset missing."],
                "unknown_checks": ["Firewall policy rules not assessed."],
                "recommendations": ["Verify perimeter firewall presence in campus topology."],
                "assessment_timestamp": now,
            }

        cfg_map = _latest_configs_map(db)
        cfg = cfg_map.get(fw.id, "").lower()
        if not cfg.strip():
            return {
                "assessment_category": "FIREWALL_CONFIGURATION",
                "score": 0.0,
                "severity": "MEDIUM",
                "status": "UNKNOWN",
                "data_source": "SIMULATION",
                "device": fw.hostname,
                "evidence": [f"Firewall {fw.hostname} ({fw.management_ip}) is {fw.status}, but running_config policy evidence is empty."],
                "passed_checks": [f"{fw.hostname} operational status is '{fw.status}'."] if fw.status == "online" else [],
                "failed_checks": [],
                "unknown_checks": [
                    "Firewall zone/ACL rule ordering is UNKNOWN due to missing running_config.",
                    "Management-plane exposure on perimeter firewall is UNKNOWN.",
                ],
                "recommendations": [
                    f"Populate/collect firewall policy configuration for {fw.hostname} to enable rule-order and exposure assessment."
                ],
                "assessment_timestamp": now,
            }

        passed = [f"{fw.hostname} configuration evidence present."]
        failed = []
        unknown = []
        if "telnet" in cfg:
            failed.append(f"{fw.hostname}: Telnet reference detected in firewall configuration.")
        if "permit ip any any" in cfg:
            failed.append(f"{fw.hostname}: Overly permissive 'permit ip any any' rule detected.")
        score = max(0.0, round(90.0 - len(failed) * 25.0, 1))
        return {
            "assessment_category": "FIREWALL_CONFIGURATION",
            "score": score,
            "severity": _score_severity(score, "ASSESSED"),
            "status": "ASSESSED",
            "data_source": "SIMULATION",
            "device": fw.hostname,
            "evidence": [f"{fw.hostname} status={fw.status}, config length={len(cfg)} chars."],
            "passed_checks": passed,
            "failed_checks": failed,
            "unknown_checks": unknown,
            "recommendations": ["Review perimeter firewall rules quarterly."] if not failed else ["Remove permissive/insecure firewall entries."],
            "assessment_timestamp": now,
        }

    @staticmethod
    def assess_device_baseline(db: Session, device: Device, cfg_text: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        if cfg_text is None:
            snap = (
                db.query(ConfigSnapshot)
                .filter(ConfigSnapshot.device_id == device.id)
                .order_by(ConfigSnapshot.created_at.desc())
                .first()
            )
            cfg_text = snap.content if snap else ""
        cfg = (cfg_text or "").lower()
        passed: List[str] = []
        failed: List[str] = []
        unknown: List[str] = []
        evidence: List[str] = []
        recs: List[str] = []

        if not cfg.strip():
            unknown.extend([
                "SSH vs Telnet VTY configuration not present.",
                "SNMPv3 configuration not present.",
                "Port-security configuration not present.",
            ])
            evidence.append(f"{device.hostname}: running_config not populated; baseline controls cannot be confirmed.")
            recs.append(f"Capture baseline running_config for {device.hostname} to assess SSH, SNMPv3, and port-security.")
            status = "UNKNOWN"
            score = 0.0
        else:
            evidence.append(f"{device.hostname}: running_config present ({len(cfg)} chars).")
            if "transport input ssh" in cfg or "ip ssh" in cfg:
                passed.append("SSH management transport configured.")
            elif "telnet" in cfg:
                failed.append("Telnet management exposure detected.")
                recs.append(f"Disable Telnet and enforce 'transport input ssh' on {device.hostname}.")
            else:
                unknown.append("VTY SSH/Telnet transport setting not explicitly evidenced.")

            if "snmp-server" in cfg and "v3" in cfg:
                passed.append("SNMPv3 configured.")
            elif "snmp-server community public" in cfg:
                failed.append("Insecure default SNMP community 'public' detected.")
                recs.append(f"Migrate {device.hostname} from SNMPv1/v2c to SNMPv3 authPriv.")
            else:
                unknown.append("SNMPv3 configuration not evidenced.")

            if device.device_type in ("l2_switch", "access_switch"):
                if "port-security" in cfg:
                    passed.append("Switchport port-security configured.")
                else:
                    unknown.append("Port-security configuration not evidenced on access switch.")
                    recs.append(f"Enable 'switchport port-security' on access ports of {device.hostname}.")

            total_checks = len(passed) + len(failed) + len(unknown)
            # Never award full compliance when checks are unknown
            score = round((len(passed) / max(1, total_checks)) * 100.0, 1)
            status = "PARTIAL" if unknown else "ASSESSED"

        # Check active security detections on this device
        open_dets = db.query(SecurityDetection).filter(
            SecurityDetection.source_device_id == device.id,
            SecurityDetection.status.in_(["OPEN", "CORRELATED"]),
        ).count()
        if open_dets > 0:
            failed.append(f"{open_dets} active security detection(s) on {device.hostname}.")
            score = max(0.0, round(score - open_dets * 10.0, 1))

        return {
            "assessment_category": "DEVICE_SECURITY_BASELINE",
            "device_id": device.id,
            "hostname": device.hostname,
            "device_type": device.device_type,
            "department": device.department,
            "score": score,
            "severity": _score_severity(score, status),
            "status": status,
            "data_source": "SIMULATION",
            "evidence": evidence,
            "passed_checks": passed,
            "failed_checks": failed,
            "unknown_checks": unknown,
            "recommendations": list(dict.fromkeys(recs)),
            "assessment_timestamp": now,
        }

    @staticmethod
    def assess_devices(db: Session, limit: int = 30, offset: int = 0) -> Dict[str, Any]:
        q = db.query(Device).filter(Device.asset_category != "student_endpoint").order_by(Device.hostname.asc())
        total = q.count()
        devs = q.offset(offset).limit(limit).all()
        items = [NetworkSecurityIntelligenceService.assess_device_baseline(db, d) for d in devs]
        return {"total": total, "limit": limit, "offset": offset, "items": items}

    @staticmethod
    def assess_departments(db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        depts = ["CSE", "IT", "ECE"]
        results = []
        for dept in depts:
            devs = db.query(Device).filter(Device.department == dept, Device.asset_category != "student_endpoint").all()
            ep_count = db.query(Device).filter(Device.department == dept, Device.asset_category == "student_endpoint").count()
            assigned_students = db.query(Student).filter(Student.department == dept, Student.device_id.isnot(None)).count()
            open_dets = db.query(SecurityDetection).filter(
                SecurityDetection.department == dept,
                SecurityDetection.status.in_(["OPEN", "CORRELATED"]),
            ).count()
            baselines = [NetworkSecurityIntelligenceService.assess_device_baseline(db, d) for d in devs]
            avg_base = round(sum(b["score"] for b in baselines) / max(1, len(baselines)), 1) if baselines else 0.0
            nac_coverage = round((assigned_students / max(1, ep_count)) * 100.0, 1) if ep_count else 0.0
            score = max(0.0, round((avg_base * 0.6 + nac_coverage * 0.4) - open_dets * 8.0, 1))
            results.append({
                "department": dept,
                "infrastructure_devices": len(devs),
                "student_endpoints": ep_count,
                "assigned_endpoints": assigned_students,
                "open_detections": open_dets,
                "score": score,
                "severity": _score_severity(score, "PARTIAL"),
                "status": "PARTIAL",
                "data_source": "SIMULATION",
                "assessment_timestamp": now,
            })
        return {"assessment_category": "DEPARTMENT_POSTURE", "departments": results, "assessment_timestamp": now}

    @staticmethod
    def get_security_overview(db: Session) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        vlan_ass = NetworkSecurityIntelligenceService.assess_vlan_segmentation(db)
        acl_ass = NetworkSecurityIntelligenceService.assess_acls(db)
        fw_ass = NetworkSecurityIntelligenceService.assess_firewall(db)
        dept_ass = NetworkSecurityIntelligenceService.assess_departments(db)

        open_dets = db.query(SecurityDetection).filter(SecurityDetection.status.in_(["OPEN", "CORRELATED"])).count()
        crit_dets = db.query(SecurityDetection).filter(
            SecurityDetection.status.in_(["OPEN", "CORRELATED"]),
            SecurityDetection.severity.in_(["CRITICAL", "HIGH"]),
        ).count()

        scores = [vlan_ass["score"], acl_ass["score"], fw_ass["score"]]
        overall_score = round(sum(scores) / len(scores), 1)
        recs = list(dict.fromkeys(
            vlan_ass["recommendations"] + acl_ass["recommendations"] + fw_ass["recommendations"]
        ))

        return {
            "data_source": "SIMULATION",
            "overall_posture_score": overall_score,
            "severity": _score_severity(overall_score, "PARTIAL"),
            "open_detections": open_dets,
            "high_critical_detections": crit_dets,
            "categories": {
                "vlan_segmentation": {"score": vlan_ass["score"], "status": vlan_ass["status"]},
                "acl_configuration": {"score": acl_ass["score"], "status": acl_ass["status"]},
                "firewall_configuration": {"score": fw_ass["score"], "status": fw_ass["status"]},
            },
            "departments": dept_ass["departments"],
            "recommendations": recs[:10],
            "assessment_timestamp": now,
        }
