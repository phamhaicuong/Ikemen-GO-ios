import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

extra_dir = sys.argv[1]
assets_dir = sys.argv[2]

if not os.path.isdir(extra_dir):
    print("==> No extra_chars directory found, skipping:", extra_dir)
    sys.exit(0)

chars_out = os.path.join(assets_dir, "chars")
os.makedirs(chars_out, exist_ok=True)

def find_char_roots(root_dir):
    found = []
    for cur, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d != "__MACOSX" and not d.startswith(".")]
        defs = [f for f in files if f.lower().endswith(".def")]
        if defs:
            found.append((cur, sorted(defs)))
            dirs[:] = []
    return found

def fix_def_case_sensitivity(char_dir, def_filename):
    def_path = os.path.join(char_dir, def_filename)
    file_map = {}
    for cur, dirs, files in os.walk(char_dir):
        for f in files:
            full = os.path.join(cur, f)
            rel = os.path.relpath(full, char_dir).replace("\\", "/")
            file_map[rel.lower()] = rel

    with open(def_path, "rb") as fp:
        raw = fp.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    in_files = False
    changed = False
    out_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_files = (stripped.lower() == "[files]")
            out_lines.append(line)
            continue
        if in_files and "=" in line and not stripped.startswith(";"):
            code_part, sep, comment_part = line.partition(";")
            key, eq, val = code_part.partition("=")
            clean_val = val.strip().strip('"').replace("\\", "/")
            if clean_val and clean_val.lower() in file_map:
                actual = file_map[clean_val.lower()]
                if actual != val.strip():
                    new_line = f"{key.rstrip()} = {actual}"
                    if sep:
                        new_line += f" ;{comment_part}"
                    out_lines.append(new_line)
                    changed = True
                    continue
        out_lines.append(line)

    if changed:
        with open(def_path, "w", encoding="utf-8", newline="\n") as fp:
            fp.write("\n".join(out_lines) + "\n")
        print(f"    -> Fixed case/path references in {def_filename}")

def pick_main_def(char_dir, defs):
    folder_low = os.path.basename(char_dir).lower()
    for d in defs:
        if os.path.splitext(d)[0].lower() == folder_low:
            return d
    for d in defs:
        p = os.path.join(char_dir, d)
        try:
            t = open(p, "r", encoding="utf-8", errors="ignore").read().lower()
            if "[files]" in t and "[info]" in t:
                return d
        except Exception:
            pass
    return defs[0]

def add_to_select_def(select_path, entry_line):
    if not os.path.isfile(select_path):
        return
    with open(select_path, "r", encoding="utf-8", errors="replace") as fp:
        txt = fp.read()
    char_key = entry_line.split(",")[0].strip().lower()
    for existing in txt.splitlines():
        s = existing.strip()
        if not s or s.startswith(";"):
            continue
        if s.split(",")[0].strip().lower() == char_key:
            return
    lines = txt.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.strip().lower() == "[characters]":
            out.append(entry_line)
            inserted = True
    if not inserted:
        out.append("[Characters]")
        out.append(entry_line)
    with open(select_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(out) + "\n")
    print(f"    -> Registered in {os.path.relpath(select_path, assets_dir)}: {entry_line}")

staging = tempfile.mkdtemp(prefix="ikemen_extra_chars_")
added_entries = []
try:
    for item in sorted(os.listdir(extra_dir)):
        if item.startswith("."):
            continue
        src = os.path.join(extra_dir, item)
        work = os.path.join(staging, os.path.splitext(item)[0])
        os.makedirs(work, exist_ok=True)
        low = item.lower()
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(work, item), dirs_exist_ok=True)
        elif low.endswith(".zip"):
            print("==> Extracting ZIP extra char:", item)
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(work)
        elif low.endswith(".rar"):
            print("==> Extracting RAR extra char:", item)
            if shutil.which("unar"):
                subprocess.run(["unar", "-quiet", "-force-overwrite", "-output-directory", work, src], check=True)
            elif shutil.which("7z"):
                subprocess.run(["7z", "x", "-y", f"-o{work}", src], check=True)
            elif shutil.which("unrar"):
                subprocess.run(["unrar", "x", "-o+", src, work + os.sep], check=True)
            else:
                print("ERROR: unar/7z/unrar not installed!", file=sys.stderr)
                sys.exit(1)
        else:
            continue

        for char_dir, defs in find_char_roots(work):
            folder_name = os.path.basename(char_dir)
            dst = os.path.join(chars_out, folder_name)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(char_dir, dst)
            for cur, dirs, files in os.walk(dst):
                for jf in files:
                    if jf.lower() in ("thumbs.db", "desktop.ini", ".ds_store"):
                        os.remove(os.path.join(cur, jf))
            main_def = pick_main_def(dst, defs)
            fix_def_case_sensitivity(dst, main_def)
            entry = f"{folder_name}/{main_def}, random"
            added_entries.append(entry)
            print(f"==> Bundled character: {folder_name} (def: {main_def})")

    select_candidates = [
        os.path.join(assets_dir, "data", "select.def"),
        os.path.join(assets_dir, "data", "ikemen1", "select.def"),
    ]
    for entry in added_entries:
        for sp in select_candidates:
            add_to_select_def(sp, entry)
finally:
    shutil.rmtree(staging, ignore_errors=True)

print(f"==> Extra character bundling finished ({len(added_entries)} character(s) added).")