import zipfile, io, hashlib, struct, os, subprocess

def get_avb_root_digest(payload_bytes, tmp_dir):
    img_path = os.path.join(tmp_dir, "temp_payload.img")
    with open(img_path, "wb") as f:
        f.write(payload_bytes)
    try:
        res = subprocess.run(
            ["python", "tools/bootimg/avbtool.py", "print_partition_digests", "--image", img_path],
            capture_output=True, text=True, check=True
        )
        for line in res.stdout.splitlines():
            if ":" in line:
                return line.strip()
        return res.stdout.strip()
    except Exception as e:
        return f"avbtool error: {e}"

def parse_manifest(raw_bytes):
    # apex_manifest proto:
    # 1: name (string) -> wire type 2, tag 1 (0x0a)
    # 2: version (int64) -> wire type 0, tag 2 (0x10)
    # capexMetadata (tag 11 = 0x5a) -> originalApexDigest (tag 1 = 0x0a)
    name = "unknown"
    version = None
    original_apex_digest = None
    
    idx = 0
    while idx < len(raw_bytes):
        tag_byte = raw_bytes[idx]
        wire_type = tag_byte & 7
        field_num = tag_byte >> 3
        idx += 1
        if wire_type == 0: # varint
            val = 0
            shift = 0
            while True:
                b = raw_bytes[idx]
                idx += 1
                val |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            if field_num == 2:
                version = val
        elif wire_type == 2: # length-delimited
            # read varint length
            length = 0
            shift = 0
            while True:
                b = raw_bytes[idx]
                idx += 1
                length |= (b & 0x7f) << shift
                if not (b & 0x80):
                    break
                shift += 7
            field_data = raw_bytes[idx:idx+length]
            idx += length
            if field_num == 1:
                name = field_data.decode('utf-8', errors='ignore')
            elif field_num == 11: # capexMetadata
                # parse submessage
                sub_idx = 0
                while sub_idx < len(field_data):
                    sub_tag = field_data[sub_idx]
                    sub_wire = sub_tag & 7
                    sub_field = sub_tag >> 3
                    sub_idx += 1
                    if sub_wire == 2:
                        sub_len = field_data[sub_idx]
                        sub_idx += 1
                        sub_val = field_data[sub_idx:sub_idx+sub_len]
                        sub_idx += sub_len
                        if sub_field == 1:
                            original_apex_digest = sub_val.decode('utf-8', errors='ignore')
                    else:
                        break
        else:
            break
    return name, version, original_apex_digest

def analyze_target(label, capex_or_apex_path, tmp_dir):
    print("=" * 70)
    print(f"TARGET: {label}")
    print(f"Path: {capex_or_apex_path}")
    is_capex = capex_or_apex_path.endswith('.capex')
    print(f"Container format: {'.capex' if is_capex else '.apex'}")
    
    with open(capex_or_apex_path, 'rb') as f:
        container_bytes = f.read()
    print(f"Container file size: {len(container_bytes)} bytes")
    print(f"Container SHA256: {hashlib.sha256(container_bytes).hexdigest()}")
    
    cz = zipfile.ZipFile(io.BytesIO(container_bytes))
    print(f"Container entries: {cz.namelist()}")
    
    if is_capex and 'apex_manifest.pb' in cz.namelist():
        outer_manifest_raw = cz.read('apex_manifest.pb')
        out_name, out_ver, out_orig_digest = parse_manifest(outer_manifest_raw)
        print(f"Outer manifest: package={out_name}, version={out_ver}, originalApexDigest={out_orig_digest}")
        original_apex_bytes = cz.read('original_apex')
        print(f"Extracted original_apex size: {len(original_apex_bytes)} bytes")
        print(f"original_apex SHA256: {hashlib.sha256(original_apex_bytes).hexdigest()}")
        ordinary_apex_bytes = original_apex_bytes
    else:
        ordinary_apex_bytes = container_bytes
        
    oz = zipfile.ZipFile(io.BytesIO(ordinary_apex_bytes))
    print(f"Inner ordinary APEX entries: {oz.namelist()}")
    
    if 'apex_manifest.pb' in oz.namelist():
        inner_manifest_raw = oz.read('apex_manifest.pb')
        in_name, in_ver, _ = parse_manifest(inner_manifest_raw)
        print(f"Inner manifest: package={in_name}, version={in_ver}")
        
    # Find apex_payload.img inside ordinary APEX
    payload_info = None
    for info in oz.infolist():
        if info.filename == 'apex_payload.img':
            payload_info = info
            break
            
    if payload_info:
        print(f"payload size: {payload_info.file_size} bytes")
        print(f"payload compress_type: {payload_info.compress_type} (0=STORED, 8=DEFLATED)")
        
        # Calculate exact ZIP data offset
        idx = 0
        payload_data_offset = None
        while idx < len(ordinary_apex_bytes) - 30:
            if ordinary_apex_bytes[idx:idx+4] == b'PK\x03\x04':
                fn_len = struct.unpack('<H', ordinary_apex_bytes[idx+26:idx+28])[0]
                extra_len = struct.unpack('<H', ordinary_apex_bytes[idx+28:idx+30])[0]
                fn = ordinary_apex_bytes[idx+30:idx+30+fn_len]
                if fn == b'apex_payload.img':
                    payload_data_offset = idx + 30 + fn_len + extra_len
                    break
                idx += 30 + fn_len + extra_len
            else:
                idx += 1
            
        print(f"apex_payload.img ZIP data offset: {payload_data_offset}")
        if payload_data_offset is not None:
            mod4096 = payload_data_offset % 4096
            mod512 = payload_data_offset % 512
            print(f"offset % 4096: {mod4096} (4096-ALIGNED: {mod4096 == 0})")
            print(f"offset % 512:  {mod512} (512-ALIGNED:  {mod512 == 0})")
            
        payload_data = oz.read('apex_payload.img')
        print(f"payload SHA256: {hashlib.sha256(payload_data).hexdigest()}")
        avb_res = get_avb_root_digest(payload_data, tmp_dir)
        print(f"payload AVB digest: {avb_res}")
        
        # Check libnetd_updatable.so inside payload
        # Find magic in payload
        # ext4 partition can be extracted or searched for the SO
        so_name = b'libnetd_updatable.so'
        so_idx = payload_data.find(so_name)
        print(f"libnetd_updatable.so string in payload: {'Found at ' + hex(so_idx) if so_idx != -1 else 'Not found'}")
            
    if 'apex_pubkey' in oz.namelist():
        pubkey = oz.read('apex_pubkey')
        print(f"apex_pubkey size: {len(pubkey)}, SHA256: {hashlib.sha256(pubkey).hexdigest()}")

tmp_dir = r"[LOCAL_PROJECT_ROOT]\work\three_way_tethering_check"
os.makedirs(tmp_dir, exist_ok=True)

targets = [
    ("1. Xiaomi 15 (dada) Donor HyperOS 4", r"[LOCAL_PROJECT_ROOT]\work\three_way_tethering_check\dada_tethering.capex"),
    ("2. K40 (alioth) Milo Port HyperOS 4", r"[LOCAL_PROJECT_ROOT]\work\third_party_milo_hyperos4_audit_20260930\targeted_files\milo\milo_system_a\system\apex\com.android.tethering.capex"),
    ("3. Candidate 44 (thyme current)", r"\\wsl.localhost\Ubuntu\root\[LOCAL_WSL_BUILD_DIR]\c44_capex_digest_fix_20261004\system_tree\system\apex\com.android.tethering.capex")
]

for label, p in targets:
    analyze_target(label, p, tmp_dir)
