import asyncio
from typing import Any, Dict, List, Optional
from pysnmp.hlapi.v3arch.asyncio import (
    ContextData,
    NoSuchInstance,
    NoSuchObject,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    get_cmd,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
    usmHMAC192SHA256AuthProtocol,
    walk_cmd,
)
from app.models import CredentialVault, DeviceConnectionProfile
from app.services.device_connection_manager import decrypt_secret

STANDARD_CISCO_OIDS = {
    "sysUpTime": "1.3.6.1.2.1.1.3.0",
    "cpu_utilization": "1.3.6.1.4.1.9.9.109.1.1.1.1.6.1",
    "memory_used": "1.3.6.1.4.1.9.9.48.1.1.1.5.1",
    "memory_free": "1.3.6.1.4.1.9.9.48.1.1.1.6.1",
    "ifDescr": "1.3.6.1.2.1.2.2.1.2",
    "ifSpeed": "1.3.6.1.2.1.2.2.1.5",
    "ifAdminStatus": "1.3.6.1.2.1.2.2.1.7",
    "ifOperStatus": "1.3.6.1.2.1.2.2.1.8",
    "ifInOctets": "1.3.6.1.2.1.2.2.1.10",
    "ifInErrors": "1.3.6.1.2.1.2.2.1.14",
    "ifOutOctets": "1.3.6.1.2.1.2.2.1.16",
    "ifOutErrors": "1.3.6.1.2.1.2.2.1.20",
}

_AUTH_PROTOCOLS = {
    "SHA": usmHMACSHAAuthProtocol,
    "SHA256": usmHMAC192SHA256AuthProtocol,
    "MD5": usmHMACMD5AuthProtocol,
}

_PRIV_PROTOCOLS = {
    "AES128": usmAesCfb128Protocol,
    "AES": usmAesCfb128Protocol,
    "DES": usmDESPrivProtocol,
}


class SNMPAuthError(Exception):
    """Raised when SNMPv3 authentication or privacy validation fails."""


def build_usm_user_data(
    username: str,
    auth_key: str,
    priv_key: Optional[str],
    auth_proto: str,
    priv_proto: Optional[str],
    environment: str = "LAB",
) -> UsmUserData:
    auth_p = _AUTH_PROTOCOLS.get((auth_proto or "SHA").upper())
    if not auth_p:
        raise SNMPAuthError("Unsupported SNMPv3 authentication protocol.")

    if (environment or "").upper() == "PRODUCTION" and not priv_key:
        raise SNMPAuthError("PRODUCTION SNMPv3 requires authPriv (encryption key mandatory).")

    if priv_key:
        priv_p = _PRIV_PROTOCOLS.get((priv_proto or "AES128").upper())
        if not priv_p:
            raise SNMPAuthError("Unsupported SNMPv3 privacy protocol.")
        return UsmUserData(
            userName=username,
            authKey=auth_key,
            privKey=priv_key,
            authProtocol=auth_p,
            privProtocol=priv_p,
        )

    return UsmUserData(
        userName=username,
        authKey=auth_key,
        authProtocol=auth_p,
    )


async def _async_snmp_get_and_walk(
    host: str,
    port: int,
    usm_user: UsmUserData,
    timeout_seconds: int = 5,
    retries: int = 1,
) -> Dict[str, Any]:
    engine = SnmpEngine()
    try:
        target = await UdpTransportTarget.create(
            (host, port),
            timeout=float(timeout_seconds),
            retries=max(0, retries - 1),
        )
        ctx = ContextData()
        scalar_keys = ["sysUpTime", "cpu_utilization", "memory_used", "memory_free"]
        obj_types = [ObjectType(ObjectIdentity(STANDARD_CISCO_OIDS[k])) for k in scalar_keys]

        error_indication, error_status, error_index, var_binds = await get_cmd(
            engine, usm_user, target, ctx, *obj_types
        )
        if error_indication:
            err_txt = str(error_indication)
            if any(tok in err_txt.lower() for tok in ("auth", "digest", "unknownuser", "decryption")):
                raise SNMPAuthError(f"SNMPv3 USM error: {err_txt}")
            raise TimeoutError(f"SNMPv3 transport error: {err_txt}")
        if error_status:
            raise RuntimeError(f"SNMPv3 agent error: {error_status.prettyPrint()} at index {error_index}")

        result: Dict[str, Any] = {}
        for key, vb in zip(scalar_keys, var_binds):
            val = vb[1]
            if isinstance(val, (NoSuchObject, NoSuchInstance)):
                result[key] = "NO_SUCH_OBJECT"
            else:
                try:
                    result[key] = float(val) if key != "sysUpTime" else int(val)
                except Exception:
                    result[key] = str(val)

        # Compute memory percentage if both used & free are present
        if isinstance(result.get("memory_used"), (int, float)) and isinstance(result.get("memory_free"), (int, float)):
            total_mem = result["memory_used"] + result["memory_free"]
            if total_mem > 0:
                result["memory_used"] = round((result["memory_used"] / total_mem) * 100.0, 2)

        # Walk MIB-II ifTable columns
        if_map: Dict[str, Dict[str, Any]] = {}
        col_keys = ["ifDescr", "ifSpeed", "ifAdminStatus", "ifOperStatus", "ifInOctets", "ifInErrors", "ifOutOctets", "ifOutErrors"]
        for col in col_keys:
            base_oid = STANDARD_CISCO_OIDS[col]
            async for err_ind, err_stat, _, vbs in walk_cmd(
                engine, usm_user, target, ctx, ObjectType(ObjectIdentity(base_oid)), lexicographicMode=False
            ):
                if err_ind or err_stat:
                    break
                for oid, val in vbs:
                    idx = str(oid).split(".")[-1]
                    entry = if_map.setdefault(idx, {"if_index": idx})
                    if col == "ifDescr":
                        entry["name"] = str(val)
                    elif col == "ifSpeed":
                        entry["speed_bps"] = int(val)
                    elif col == "ifAdminStatus":
                        entry["admin_status"] = "up" if int(val) == 1 else "down"
                    elif col == "ifOperStatus":
                        entry["oper_status"] = "up" if int(val) == 1 else "down"
                    elif col == "ifInOctets":
                        entry["in_octets"] = int(val)
                    elif col == "ifOutOctets":
                        entry["out_octets"] = int(val)
                    elif col == "ifInErrors":
                        entry["input_errors"] = int(val)
                    elif col == "ifOutErrors":
                        entry["output_errors"] = int(val)

        result["interfaces"] = list(if_map.values())
        return result
    finally:
        engine.close_dispatcher()


class SNMPv3Collector:
    """
    SNMPv3 metric collector for authorized LAB/PRODUCTION devices using pysnmp v3arch.
    Never downgrades to SNMPv1/v2c and never exposes credentials in responses, logs, or exceptions.
    """

    @staticmethod
    def _snmp_get(
        host: str,
        port: int,
        username: str,
        auth_key: str,
        priv_key: Optional[str],
        auth_proto: str,
        priv_proto: Optional[str],
        oids: Dict[str, str],
        timeout_seconds: int = 5,
        retries: int = 1,
        environment: str = "LAB",
    ) -> Dict[str, Any]:
        usm_user = build_usm_user_data(
            username=username,
            auth_key=auth_key,
            priv_key=priv_key,
            auth_proto=auth_proto,
            priv_proto=priv_proto,
            environment=environment,
        )
        coro = _async_snmp_get_and_walk(
            host=host,
            port=port,
            usm_user=usm_user,
            timeout_seconds=timeout_seconds,
            retries=retries,
        )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Run in dedicated loop inside worker thread if called from an async loop
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return asyncio.run(coro)

    @staticmethod
    def collect_device_metrics(
        profile: DeviceConnectionProfile,
        cred: CredentialVault,
    ) -> Dict[str, Any]:
        auth_key = decrypt_secret(cred.encrypted_password)
        priv_key = decrypt_secret(cred.encrypted_secret) if cred.encrypted_secret else None
        auth_proto = (cred.auth_protocol or "SHA").upper()
        priv_proto = (cred.priv_protocol or "AES128").upper() if priv_key else None

        if auth_proto not in _AUTH_PROTOCOLS:
            raise SNMPAuthError("Unsupported SNMPv3 authentication protocol.")

        try:
            raw = SNMPv3Collector._snmp_get(
                host=profile.management_ip,
                port=profile.port if profile.protocol == "SNMPV3" else 161,
                username=cred.username,
                auth_key=auth_key,
                priv_key=priv_key,
                auth_proto=auth_proto,
                priv_proto=priv_proto,
                oids=STANDARD_CISCO_OIDS,
                timeout_seconds=profile.timeout_seconds,
                retries=profile.max_retries,
                environment=profile.environment,
            )
        except SNMPAuthError as exc:
            msg = str(exc).replace(auth_key, "[REDACTED]")
            if priv_key:
                msg = msg.replace(priv_key, "[REDACTED]")
            raise SNMPAuthError(msg[:220])
        except Exception as exc:
            msg = str(exc).replace(auth_key, "[REDACTED]")
            if priv_key:
                msg = msg.replace(priv_key, "[REDACTED]")
            raise RuntimeError(msg[:220])

        unsupported_oids: List[str] = []
        metrics: Dict[str, Any] = {}
        for name in ("sysUpTime", "cpu_utilization", "memory_used"):
            val = raw.get(name)
            if val is None or val == "NO_SUCH_OBJECT":
                unsupported_oids.append(name)
                metrics[name] = None
            else:
                metrics[name] = val

        interfaces = raw.get("interfaces", [])
        return {
            "device_name": profile.device_name,
            "telemetry_source": profile.environment,
            "collection_method": "SNMPV3",
            "metrics": metrics,
            "interfaces": interfaces,
            "unsupported_oids": unsupported_oids,
        }
