import os
import plistlib
import re
import shutil
import sys

wrapper_dir = sys.argv[1]
hud_src = sys.argv[2]

print("==> Inspecting ikemen-ios wrapper:", wrapper_dir)
for root, dirs, files in os.walk(wrapper_dir):
    if ".git" in root or "Frameworks" in root:
        continue
    for f in files:
        print("  ", os.path.relpath(os.path.join(root, f), wrapper_dir))

# 1. Bat quyen hien thi thu muc Documents trong ung dung Tep (Files)
for root, dirs, files in os.walk(wrapper_dir):
    if ".git" in root or "Frameworks" in root:
        continue
    for f in files:
        if f == "Info.plist":
            p = os.path.join(root, f)
            try:
                with open(p, "rb") as fp:
                    data = plistlib.load(fp)
                data["UIFileSharingEnabled"] = True
                data["LSSupportsOpeningDocumentsInPlace"] = True
                with open(p, "wb") as fp:
                    plistlib.dump(data, fp)
                print("==> Patched Info.plist:", p)
            except Exception as e:
                print("WARN: Could not patch Info.plist", p, e)

# 2. Tu dong gan IkemenTouchHUD_impl.h vao file dinh nghia IkemenAttachMetalLayer
hooked = False
pattern = re.compile(r'(void\s+IkemenAttachMetalLayer\s*\([^)]*\)\s*\{)')
for root, dirs, files in os.walk(wrapper_dir):
    if ".git" in root or "Frameworks" in root:
        continue
    for f in files:
        if f.endswith((".m", ".mm")):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="replace") as fp:
                content = fp.read()
            if "IkemenAttachMetalLayer" in content and pattern.search(content):
                shutil.copy2(hud_src, os.path.join(root, "IkemenTouchHUD_impl.h"))
                if '#import "IkemenTouchHUD_impl.h"' not in content:
                    content = '#import "IkemenTouchHUD_impl.h"\n' + content
                    content = pattern.sub(r'\1\n    [IkemenTouchHUD attachToKeyWindow];\n', content, count=1)
                    with open(p, "w", encoding="utf-8", newline="\n") as fp:
                        fp.write(content)
                print("==> Hooked IkemenTouchHUD into:", p)
                hooked = True
                break
    if hooked:
        break

if not hooked:
    print("ERROR: Could not find IkemenAttachMetalLayer in wrapper!", file=sys.stderr)
    sys.exit(1)
print("==> Custom iOS wrapper patching complete.")