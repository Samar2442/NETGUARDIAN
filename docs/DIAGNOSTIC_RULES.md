# NetGuardian Diagnostic Rules & Confidence Weights

NetGuardian replaces black-box arbitrary AI scores with documented, evidence-based diagnostic rules and mathematically calculated confidence metrics.

---

## 1. Missing VLAN from Trunk Port (`VLAN_TRUNK_PRUNED`)
- **Category**: `vlan_trunk`
- **Default Confidence**: `96.0%`
- **Severity**: `HIGH`
- **Rule Criteria**:
  1. Downstream clients in a specific VLAN report gateway unreachable.
  2. Upstream switch trunk port is in `UP/UP` operational state.
  3. The switchport trunk allowed VLAN list on the uplink port excludes the affected VLAN tag.
- **Supporting Evidence**:
  - Client IP configuration matches subnet.
  - Central DHCP & DNS services are reachable across other VLANs.
  - SVI default gateway is unreachable.
  - Trunk port allowed list does not contain the VLAN ID.
- **Contradicting Evidence Ruled Out**:
  - Physical carrier is UP/UP, ruling out transceiver or fiber cable break.
- **Recommended Cisco CLI**:
  ```cisco
  interface GigabitEthernet0/1
   switchport trunk allowed vlan add 30
  ```
- **Verification Procedure**:
  - `show interfaces trunk`
  - ICMP echo request from client to default gateway
  - ARP cache resolution check

---

## 2. Interface Administratively Down (`INTERFACE_SHUTDOWN`)
- **Category**: `interface`
- **Confidence**: `99.0%`
- **Severity**: `HIGH` / `MEDIUM`
- **Rule Criteria**:
  - Port `admin_status == "down"` and `oper_status == "down"`.
  - Syslog `%LINK-5-CHANGED: administratively down`.
- **Recommended Cisco CLI**:
  ```cisco
  interface <interface_name>
   no shutdown
  ```

---

## 3. Wrong Access Port VLAN Assignment (`WRONG_VLAN`)
- **Category**: `vlan_access`
- **Confidence**: `94.0%`
- **Severity**: `MEDIUM`
- **Rule Criteria**:
  - Access switchport configured with VLAN X while client IP is in VLAN Y subnet.
  - ARP resolution fails to default gateway.
- **Recommended Cisco CLI**:
  ```cisco
  interface <interface_name>
   switchport access vlan <correct_vlan>
  ```

---

## 4. Central DHCP Infrastructure Failure (`DHCP_FAILURE`)
- **Category**: `services`
- **Confidence**: `92.0%`
- **Severity**: `HIGH`
- **Rule Criteria**:
  - Clients assign APIPA `169.254.0.0/16` addresses.
  - IP Helper address on core SVI times out reaching DHCP server.

---

## 5. OSPF Routing Adjacency Deadlock (`OSPF_FAILURE`)
- **Category**: `routing`
- **Confidence**: `93.0%`
- **Severity**: `HIGH`
- **Rule Criteria**:
  - OSPF neighbor state stuck in `INIT` or `DOWN`.
  - MTU mismatch or passive-interface enabled on core link.
