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

# 1. src/util_ios.go: GODEBUG + GOGC=50 an toan
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

# 2. src/resources/defaultConfig.ini: P1 menu=TAB, P2 menu=BACKSLASH, WindowIcon trong, FirstRun=0
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
cur_sec = ""
for line in cfg.splitlines():
    st = line.strip()
    if st.startswith("[") and st.endswith("]"):
        cur_sec = st
    elif cur_sec == "[Keys_P1]" and re.match(r'^menu\s*=', st):
        line = "menu     = TAB"
    elif cur_sec == "[Keys_P2]" and re.match(r'^menu\s*=', st):
        line = "menu     = BACKSLASH"
    out_cfg.append(line)
write_text(cfg_path, "\n".join(out_cfg) + "\n")
print("==> Patched src/resources/defaultConfig.ini (P1 menu=TAB, P2 menu=BACKSLASH)")

# 3. src/system.go: bo WindowIcon & stdin tren iOS + nil-safe shutdown
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

# 4. src/system_sdl.go: FIX loi thoat ra chua gat vao lai bi dung/crash tren iOS
sdl_path = os.path.join(repo_root, "src", "system_sdl.go")
sdl_txt = read_text(sdl_path)
old_bg = """\t\tcase sdl.CommonEvent:
\t\t\t// Android Vulkan behavior (Activity background/resume)
\t\t\tswitch t.Type {
\t\t\tcase sdl.APP_WILLENTERBACKGROUND:
\t\t\tcase sdl.APP_DIDENTERBACKGROUND:
\t\t\t\tif rvk, ok := gfx.(*Renderer_VK); ok {
\t\t\t\t\trvk.Await()
\t\t\t\t\tw.renderingPaused = true
\t\t\t\t}
\t\t\tcase sdl.APP_DIDENTERFOREGROUND:
\t\t\t\tif rvk, ok := gfx.(*Renderer_VK); ok {
\t\t\t\t\trvk.RecreateSurfaceAndSwapchain()
\t\t\t\t\trvk.surfaceLost = false
\t\t\t\t}
\t\t\t}"""

new_bg = """\t\tcase sdl.CommonEvent:
\t\t\t// Mobile Vulkan behavior (iOS & Android background/resume)
\t\t\tswitch t.Type {
\t\t\tcase sdl.APP_WILLENTERBACKGROUND, sdl.APP_DIDENTERBACKGROUND:
\t\t\t\tif rvk, ok := gfx.(*Renderer_VK); ok {
\t\t\t\t\tif !w.renderingPaused {
\t\t\t\t\t\tif rvk.frameOpen {
\t\t\t\t\t\t\trvk.EndFrame()
\t\t\t\t\t\t}
\t\t\t\t\t\trvk.Await()
\t\t\t\t\t\tw.renderingPaused = true
\t\t\t\t\t}
\t\t\t\t}
\t\t\tcase sdl.APP_WILLENTERFOREGROUND, sdl.APP_DIDENTERFOREGROUND:
\t\t\t\tif rvk, ok := gfx.(*Renderer_VK); ok {
\t\t\t\t\tif runtime.GOOS == "ios" {
\t\t\t\t\t\t// On iOS, CAMetalLayer persists across background/resume.
\t\t\t\t\t\trvk.Await()
\t\t\t\t\t\trvk.surfaceLost = false
\t\t\t\t\t\tw.renderingPaused = false
\t\t\t\t\t} else {
\t\t\t\t\t\trvk.RecreateSurfaceAndSwapchain()
\t\t\t\t\t\trvk.surfaceLost = false
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}"""

if old_bg in sdl_txt:
    sdl_txt = sdl_txt.replace(old_bg, new_bg, 1)
    write_text(sdl_path, sdl_txt)
    print("==> Patched src/system_sdl.go (fixed iOS background/resume Vulkan lifecycle)")
elif "CAMetalLayer persists" in sdl_txt:
    print("==> src/system_sdl.go already patched")
else:
    print("ERROR: Could not find CommonEvent block in src/system_sdl.go!", file=sys.stderr)
    sys.exit(1)

# 5. src/render_vk.go: xu ly ErrorOutOfDate & mo khoa surfaceMutex an toan tren iOS
vk_path = os.path.join(repo_root, "src", "render_vk.go")
vk_txt = read_text(vk_path)
old_vk_acq = """\tif res != vk.Success {
\t\tif res == vk.ErrorOutOfDate || res == vk.Suboptimal {
\t\t\tif res == vk.Suboptimal && runtime.GOOS != "ios" && runtime.GOOS != "android" {
\t\t\t\tLogMessage("[INFO] recreate swapchain")
\t\t\t\tr.RecreateSwapchain()
\t\t\t\tres = vk.AcquireNextImage(r.device, r.swapchains[0].swapchain,
\t\t\t\t\tvk.MaxUint64, r.semaphores[0], vk.NullFence, &r.swapchains[0].currentImageIndex)
\t\t\t\tif res != vk.Success {
\t\t\t\t\t// Try continue execution if error is suboptimal
\t\t\t\t\tif res == vk.Suboptimal {
\t\t\t\t\t\tLogMessage("[WARNING] vk.AcquireNextImage returned suboptimal after swapchain recreation")
\t\t\t\t\t\t// We're probably on Android and can recreate this
\t\t\t\t\t} else if res == vk.ErrorSurfaceLost {
\t\t\t\t\t\tr.surfaceLost = true
\t\t\t\t\t\treturn
\t\t\t\t\t} else {
\t\t\t\t\t\terr := fmt.Errorf("vk.AcquireNextImage failed with %s", vk.Error(res))
\t\t\t\t\t\tpanic(err)
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t} else {
\t\t\terr := fmt.Errorf("vk.AcquireNextImage failed with %s", vk.Error(res))
\t\t\tpanic(err)
\t\t}
\t}"""

new_vk_acq = """\tif res != vk.Success {
\t\tif res == vk.ErrorOutOfDate || res == vk.Suboptimal {
\t\t\tif res == vk.ErrorOutOfDate || (res == vk.Suboptimal && runtime.GOOS != "ios" && runtime.GOOS != "android") {
\t\t\t\tLogMessage("[INFO] recreate swapchain")
\t\t\t\tr.RecreateSwapchain()
\t\t\t\tres = vk.AcquireNextImage(r.device, r.swapchains[0].swapchain,
\t\t\t\t\tvk.MaxUint64, r.semaphores[0], vk.NullFence, &r.swapchains[0].currentImageIndex)
\t\t\t\tif res != vk.Success {
\t\t\t\t\tif res == vk.Suboptimal {
\t\t\t\t\t\tLogMessage("[WARNING] vk.AcquireNextImage returned suboptimal after swapchain recreation")
\t\t\t\t\t} else if res == vk.ErrorSurfaceLost {
\t\t\t\t\t\tr.surfaceLost = true
\t\t\t\t\t\tr.frameOpen = false
\t\t\t\t\t\tr.surfaceMutex.Unlock()
\t\t\t\t\t\treturn
\t\t\t\t\t} else {
\t\t\t\t\t\tr.frameOpen = false
\t\t\t\t\t\tr.surfaceMutex.Unlock()
\t\t\t\t\t\terr := fmt.Errorf("vk.AcquireNextImage failed with %s", vk.Error(res))
\t\t\t\t\t\tpanic(err)
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t} else if res == vk.ErrorSurfaceLost {
\t\t\tr.surfaceLost = true
\t\t\tr.frameOpen = false
\t\t\tr.surfaceMutex.Unlock()
\t\t\treturn
\t\t} else {
\t\t\tr.frameOpen = false
\t\t\tr.surfaceMutex.Unlock()
\t\t\terr := fmt.Errorf("vk.AcquireNextImage failed with %s", vk.Error(res))
\t\t\tpanic(err)
\t\t}
\t}"""

if old_vk_acq in vk_txt:
    vk_txt = vk_txt.replace(old_vk_acq, new_vk_acq, 1)
    write_text(vk_path, vk_txt)
    print("==> Patched src/render_vk.go")
elif 'if res == vk.ErrorOutOfDate || (res == vk.Suboptimal' in vk_txt:
    print("==> src/render_vk.go already patched")
else:
    print("ERROR: Could not find AcquireNextImage block in src/render_vk.go!", file=sys.stderr)
    sys.exit(1)

# 6. src/main.go
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

# 7. build/build.sh: nhung extra_chars (Goku) vao DefaultAssets.zip
sh_path = os.path.join(repo_root, "build", "build.sh")
sh_txt = read_text(sh_path)
zip_anchor = '\t( cd "$assets_dir" && zip -qr -X "$IOS_WRAPPER_DIR/DefaultAssets.zip" . )'
hook_line = '\tpython3 "$REPO_ROOT/build/ios_custom/bundle_extra_chars.py" "$REPO_ROOT/build/ios_custom/extra_chars" "$assets_dir"\n' + zip_anchor
if "bundle_extra_chars.py" not in sh_txt:
    sh_txt = sh_txt.replace(zip_anchor, hook_line, 1)
    write_text(sh_path, sh_txt)
    print("==> Patched build/build.sh (hooked extra_chars bundler)")