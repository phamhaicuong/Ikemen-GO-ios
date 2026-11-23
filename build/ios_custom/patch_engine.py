import os
import re
import sys

repo_root = sys.argv[1]

def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def write_text(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.replace("\r\n", "\n"))

# 1. src/util_ios.go
util_path = os.path.join(repo_root, "src", "util_ios.go")
util = read_text(util_path)
new_lines = []
for line in util.splitlines():
    if 'setenv("GOMEMLIMIT"' in line or 'setenv("GOGC"' in line:
        continue
    new_lines.append(line)
    if 'setenv("GODEBUG", "asyncpreemptoff=1,cgocheck=0", 1);' in line:
        new_lines.append('    setenv("GOGC", "50", 1);')
write_text(util_path, "\n".join(new_lines) + "\n")
print("==> Patched src/util_ios.go")

# 2. src/resources/defaultConfig.ini
cfg_path = os.path.join(repo_root, "src", "resources", "defaultConfig.ini")
cfg = read_text(cfg_path)
for old, new in [
    ("AfterImageMax       = 512", "AfterImageMax       = 256"),
    ("AfterImageMax       = 128", "AfterImageMax       = 256"),
    ("ExplodMax           = 512", "ExplodMax           = 256"),
    ("ProjectileMax       = 256", "ProjectileMax       = 128"),
    ("BootLoadingMode     = 2", "BootLoadingMode     = 0"),
    ("FirstRun            = 1", "FirstRun            = 0"),
    ("VRAMSwapThresholdPercent = 80", "VRAMSwapThresholdPercent = 70"),
    ("VRAMSwapThresholdPercent = 65", "VRAMSwapThresholdPercent = 70"),
    ("LifeBarTextureAtlasSize = 512", "LifeBarTextureAtlasSize = 1024"),
    ("StageTextureAtlasSize = 512", "StageTextureAtlasSize = 1024"),
    ("TextureAtlasSize  = 512", "TextureAtlasSize  = 1024"),
    ("ImageSuballocBlockSizeMB = 128", "ImageSuballocBlockSizeMB = 64"),
    ("ImageSuballocBlockSizeMB = 32", "ImageSuballocBlockSizeMB = 64"),
    ("BGMRAMBuffer      = 1", "BGMRAMBuffer      = 0"),
]:
    cfg = cfg.replace(old, new)
cfg = re.sub(r'(?m)^WindowIcon\s*=.*$', 'WindowIcon          =', cfg)

out_cfg = []
in_p1 = False
for line in cfg.splitlines():
    st = line.strip()
    if st.startswith("[") and st.endswith("]"):
        in_p1 = (st == "[Keys_P1]")
    elif in_p1 and re.match(r'^menu\s*=', st):
        line = "menu     = TAB"
    out_cfg.append(line)
write_text(cfg_path, "\n".join(out_cfg) + "\n")
print("==> Patched src/resources/defaultConfig.ini (WindowIcon cleared, FirstRun=0, Keys_P1 menu=TAB)")

# 3. src/system.go
sys_path = os.path.join(repo_root, "src", "system.go")
sys_txt = read_text(sys_path)
old_icon = '\tif runtime.GOOS != "android" {'
new_icon = '\tif runtime.GOOS != "android" && runtime.GOOS != "ios" {'
if old_icon in sys_txt:
    sys_txt = sys_txt.replace(old_icon, new_icon, 1)
    print("==> Patched src/system.go (skip desktop WindowIcon on iOS)")

old_shut = "\tgfx.Close()\n\ts.window.Close()"
new_shut = "\tif gfx != nil {\n\t\tgfx.Close()\n\t}\n\tif s.window != nil {\n\t\ts.window.Close()\n\t}"
if old_shut in sys_txt:
    sys_txt = sys_txt.replace(old_shut, new_shut, 1)
    print("==> Patched src/system.go (nil-safe shutdown)")
write_text(sys_path, sys_txt)

# 4. src/main.go
main_path = os.path.join(repo_root, "src", "main.go")
main_txt = read_text(main_path)
ios_anchor = '\t} else if runtime.GOOS == "ios" {\n\t\tLogcat("Inside realMain...")'
ios_patched = '\t} else if runtime.GOOS == "ios" {\n\t\tLogcat("Inside realMain...")\n\t\tos.Args = []string{"ikemen-go"}'
if 'os.Args = []string{"ikemen-go"}' not in main_txt.split('else if runtime.GOOS == "ios"')[1][:300]:
    main_txt = main_txt.replace(ios_anchor, ios_patched, 1)

if '\trender := gfx.GetName()' in main_txt:
    main_txt = main_txt.replace(
        '\trender := gfx.GetName()',
        '\trender := "uninitialized"\n\tif gfx != nil {\n\t\trender = gfx.GetName()\n\t}',
        1
    )

if '\trendererDebug := gfx.DebugInfo()' in main_txt:
    main_txt = main_txt.replace(
        '\trendererDebug := gfx.DebugInfo()',
        '\trendererDebug := ""\n\tif gfx != nil {\n\t\trendererDebug = gfx.DebugInfo()\n\t}',
        1
    )

old_exit = '\tShowErrorDialog(dialogMsg)\n\n\t// Cleanup and exit\n\tsys.shutdown()\n\tos.Exit(1)'
new_exit = (
    '\tShowErrorDialog(dialogMsg)\n\n'
    '\tif ef, eerr := os.OpenFile(filepath.Join(logDir, "last_error.txt"), os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644); eerr == nil {\n'
    '\t\tfmt.Fprintf(ef, "%s\\n\\nError: %s\\n\\n%s", crashType, displayErr, goStack)\n'
    '\t\tef.Close()\n'
    '\t}\n\n'
    '\t// Cleanup and exit\n'
    '\tsys.shutdown()\n'
    '\tif runtime.GOOS != "ios" {\n'
    '\t\tos.Exit(1)\n'
    '\t}'
)
if old_exit in main_txt:
    main_txt = main_txt.replace(old_exit, new_exit, 1)

old_he = 'func handleExit() {\n\tsys.shutdown()\n\tos.Exit(0)\n}'
new_he = 'func handleExit() {\n\tsys.shutdown()\n\tif runtime.GOOS != "ios" {\n\t\tos.Exit(0)\n\t}\n}'
if old_he in main_txt:
    main_txt = main_txt.replace(old_he, new_he, 1)

write_text(main_path, main_txt)
print("==> Patched src/main.go")

# 5. build/build.sh: goi bundle_extra_chars.py ngay truoc khi nen DefaultAssets.zip
sh_path = os.path.join(repo_root, "build", "build.sh")
sh_txt = read_text(sh_path)
zip_anchor = '\t( cd "$assets_dir" && zip -qr -X "$IOS_WRAPPER_DIR/DefaultAssets.zip" . )'
hook_line = '\tpython3 "$REPO_ROOT/build/ios_custom/bundle_extra_chars.py" "$REPO_ROOT/build/ios_custom/extra_chars" "$assets_dir"\n' + zip_anchor
if "bundle_extra_chars.py" not in sh_txt:
    sh_txt = sh_txt.replace(zip_anchor, hook_line, 1)
    write_text(sh_path, sh_txt)
    print("==> Patched build/build.sh (hooked extra_chars bundler)")