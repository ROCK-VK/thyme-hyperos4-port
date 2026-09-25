#!/usr/bin/env python3
import os
import glob
import subprocess
from pathlib import Path

def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.stdout.strip(), p.stderr.strip(), p.returncode

def main():
    print("=== AUDITING SELINUX CIL AND MAPPING FOR CANDIDATE 13 ===")
    
    # 1. Check plat_sepolicy_vers.txt across partitions
    vendor_img = "[LOCAL_WSL_USER]/thyme_xiaomi15_os4_first_boot_candidate_1/provider_images/vendor.img"
    odm_img = "[LOCAL_WSL_USER]/thyme_xiaomi15_os4_first_boot_candidate_1/provider_images/odm.img"
    
    out, err, rc = run(f"debugfs -R 'cat etc/selinux/plat_sepolicy_vers.txt' {vendor_img} 2>/dev/null")
    print(f"vendor plat_sepolicy_vers: {out}")
    vers = out.strip()
    
    out, err, rc = run(f"debugfs -R 'cat etc/selinux/plat_sepolicy_vers.txt' {odm_img} 2>/dev/null")
    print(f"odm plat_sepolicy_vers: {out}")

    # 2. Extract vendor_sepolicy.cil and odm_sepolicy.cil
    audit_dir = "[LOCAL_WSL_USER]/c13_audit"
    os.makedirs(audit_dir, exist_ok=True)
    run(f"debugfs -R 'dump etc/selinux/vendor_sepolicy.cil {audit_dir}/vendor_sepolicy.cil' {vendor_img} 2>/dev/null")
    run(f"debugfs -R 'dump etc/selinux/odm_sepolicy.cil {audit_dir}/odm_sepolicy.cil' {odm_img} 2>/dev/null")
    
    vendor_cil = f"{audit_dir}/vendor_sepolicy.cil"
    odm_cil = f"{audit_dir}/odm_sepolicy.cil"
    print("vendor_sepolicy.cil size:", os.path.getsize(vendor_cil) if os.path.exists(vendor_cil) else "missing")
    print("odm_sepolicy.cil size:", os.path.getsize(odm_cil) if os.path.exists(odm_cil) else "missing")

    # 3. List active CIL files for vers (202604)
    # System
    sys_dir = "[LOCAL_WSL_USER]/thyme_xiaomi15_os4_first_boot_candidate_1/rootlike_stage/system/etc/selinux"
    plat_cil = f"{sys_dir}/plat_sepolicy.cil"
    mapping_cil = f"{sys_dir}/mapping/{vers}.cil"
    genfs_cil = f"{sys_dir}/plat_sepolicy_genfs_{vers}.cil"
    
    print(f"plat_sepolicy.cil exists: {os.path.exists(plat_cil)}")
    print(f"system mapping/{vers}.cil exists: {os.path.exists(mapping_cil)}")
    print(f"system plat_sepolicy_genfs_{vers}.cil exists: {os.path.exists(genfs_cil)}")
    
    # System Ext
    sys_ext_dir = "[LOCAL_WSL_USER]/c12_build_stage/system_ext_tree/etc/selinux"
    sys_ext_cil = f"{sys_ext_dir}/system_ext_sepolicy.cil"
    sys_ext_mapping_cil = f"{sys_ext_dir}/mapping/{vers}.cil"
    sys_ext_compat_cil = f"{sys_ext_dir}/mapping/{vers}.compat.cil"
    
    print(f"system_ext_sepolicy.cil exists: {os.path.exists(sys_ext_cil)}")
    print(f"system_ext mapping/{vers}.cil exists: {os.path.exists(sys_ext_mapping_cil)}")
    print(f"system_ext mapping/{vers}.compat.cil exists: {os.path.exists(sys_ext_compat_cil)}")

    # Product
    # Check where product CILs are
    out, _, _ = run("find [LOCAL_WSL_USER]/ -name product_sepolicy.cil")
    print("Product sepolicy files found:", out.splitlines())
    prod_cil = out.splitlines()[0] if out.splitlines() else None
    
    prod_mapping_cil = None
    if prod_cil:
        prod_dir = os.path.dirname(prod_cil)
        candidate_prod_mapping = f"{prod_dir}/mapping/{vers}.cil"
        if os.path.exists(candidate_prod_mapping):
            prod_mapping_cil = candidate_prod_mapping
        print(f"product mapping/{vers}.cil: {prod_mapping_cil}")

    # Check ion_device in mapping/202604.cil
    if os.path.exists(mapping_cil):
        out, _, _ = run(f"grep 'ion_device' {mapping_cil}")
        print(f"\n[mapping/{vers}.cil for ion_device]:\n{out}")

    if os.path.exists(sys_ext_mapping_cil):
        out, _, _ = run(f"grep 'ion_device' {sys_ext_mapping_cil}")
        print(f"\n[system_ext mapping/{vers}.cil for ion_device]:\n{out}")

    # Check vendor_sepolicy for hal_keymaster and hal_gatekeeper
    vendor_cil = f"{audit_dir}/vendor_sepolicy.cil"
    if os.path.exists(vendor_cil):
        with open(vendor_cil) as f:
            vlines = f.readlines()
        ion_allows = [l.strip() for l in vlines if 'ion_device' in l and l.strip().startswith('(allow')]
        print(f"\n[vendor_sepolicy total allow for ion_device: {len(ion_allows)}]")
        for a in ion_allows:
            print("  ", a)

if __name__ == "__main__":
    main()
