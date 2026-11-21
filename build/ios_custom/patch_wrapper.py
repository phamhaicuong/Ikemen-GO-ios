import os
import plistlib
import shutil
import sys

wrapper_dir = sys.argv[1]
hud_src = sys.argv[2]
app_dir = os.path.join(wrapper_dir, "I.K.E.M.E.N-Go")

print("==> Patching ikemen-ios wrapper at:", app_dir)
if not os.path.isdir(app_dir):
    print("ERROR: App directory not found:", app_dir, file=sys.stderr)
    sys.exit(1)

# 1. Bat quyen hien thi thu muc Documents (I.K.E.M.E.N-Go) trong ung dung Tep
plist_path = os.path.join(app_dir, "Info.plist")
with open(plist_path, "rb") as fp:
    plist_data = plistlib.load(fp)
plist_data["UIFileSharingEnabled"] = True
plist_data["LSSupportsOpeningDocumentsInPlace"] = True
with open(plist_path, "wb") as fp:
    plistlib.dump(plist_data, fp)
print("==> Patched Info.plist")

# 2. Chep IkemenTouchHUD duoi dang header de tranh Xcode bien dich trung
hud_dst = os.path.join(app_dir, "IkemenTouchHUD_impl.h")
shutil.copy2(hud_src, hud_dst)
print("==> Installed IkemenTouchHUD_impl.h")

# 3. Thay TouchOverlayView.m: bo bo dem an nut sau 5s va chuyen cam ung cho IkemenTouchHUD
touch_overlay_m = """#import "TouchOverlayView.h"

@implementation TouchOverlayView

- (instancetype)initWithCoder:(NSCoder *)coder {
    self = [super initWithCoder:coder];
    if (self) {
        self.backgroundColor = [UIColor clearColor];
        self.opaque = NO;
        self.multipleTouchEnabled = YES;
        self.userInteractionEnabled = YES;
    }
    return self;
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.backgroundColor = [UIColor clearColor];
        self.opaque = NO;
        self.multipleTouchEnabled = YES;
        self.userInteractionEnabled = YES;
    }
    return self;
}

- (void)resetHideTimer {
    self.alpha = 1.0;
}

- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return (hit == self) ? nil : hit;
}

- (void)joystick:(AnalogJoystickView *)joystick didMoveX:(CGFloat)x y:(CGFloat)y {}
- (void)dPad:(DPadView *)dPad didChangeDirection:(DPadDirection)direction {}

@end
"""
with open(os.path.join(app_dir, "TouchOverlayView.m"), "w", encoding="utf-8", newline="\n") as fp:
    fp.write(touch_overlay_m)
print("==> Replaced TouchOverlayView.m")

# 4. Thay TouchOverlayViewController.m: xoa sach XIB cu, gan thang IkemenTouchHUD
touch_vc_m = """#import "TouchOverlayViewController.h"
#import "TouchOverlayView.h"
#import "ViewController.h"
#import "IkemenTouchHUD_impl.h"

@interface TouchOverlayViewController ()
@property (nonatomic, strong) IkemenTouchHUD *customHUD;
@end

@implementation TouchOverlayViewController

- (void)awakeFromNib {
    [super awakeFromNib];
    if ([self.view isKindOfClass:[TouchOverlayView class]]) {
        self.overlayView = (TouchOverlayView *)self.view;
    }
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor clearColor];
    self.view.opaque = NO;
    if ([self.view isKindOfClass:[TouchOverlayView class]]) {
        self.overlayView = (TouchOverlayView *)self.view;
    }
    for (UIView *sub in [self.view.subviews copy]) {
        [sub removeFromSuperview];
    }
    self.customHUD = [[IkemenTouchHUD alloc] initWithFrame:self.view.bounds];
    self.customHUD.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.view addSubview:self.customHUD];
}

- (void)setParentVC:(ViewController *)parentVC {
    _parentVC = parentVC;
    self.overlayView.delegate = _parentVC;
}

- (void)touchOverlayDidTapGameFolder:(TouchOverlayView *)view {
    if ([self.parentVC respondsToSelector:@selector(touchOverlayDidTapGameFolder:)]) {
        [self.parentVC touchOverlayDidTapGameFolder:view];
    }
}

@end
"""
with open(os.path.join(app_dir, "TouchOverlayViewController.m"), "w", encoding="utf-8", newline="\n") as fp:
    fp.write(touch_vc_m)
print("==> Replaced TouchOverlayViewController.m")

# 5. Thay ViewController.m: chay thang tu thu muc Documents (bo qua chon thu muc & bo cho 5 giay)
vc_m = """#import "GamepadInputs.h"
#import "ViewController.h"
#import "TouchOverlayView.h"
#import "TouchOverlayViewController.h"
#import "AnalogJoystickView.h"
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import "zlib.h"
#import "ZipArchive.h"
#import "libikemen.h"
#import <SDL2/SDL.h>
#import "GoWindow.h"
#import "SDLWindowFix.h"

@interface ViewController ()
@property (nonatomic, strong) NSURL *assetsFolderURL;
@property (nonatomic, assign) BOOL ikemenStarted;
@property (nonatomic, strong) TouchOverlayView *overlayView;
@property (nonatomic, strong) MetalContainerView *metalContainerView;
@property (nonatomic, strong) UILabel *bootStatusLabel;
@end

@implementation ViewController

- (UIInterfaceOrientationMask)supportedInterfaceOrientations {
    return IkemenOrientationIsLocked() ? IkemenLockedOrientationMask() : UIInterfaceOrientationMaskAll;
}

- (BOOL)shouldAutorotate {
    return !IkemenOrientationIsLocked();
}

- (BOOL)prefersHomeIndicatorAutoHidden {
    return YES;
}

- (UIRectEdge)preferredScreenEdgesDeferringSystemGestures {
    return UIRectEdgeAll;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor blackColor];
    self.definesPresentationContext = YES;
    IkemenLockOrientationToCurrent();

    self.bootStatusLabel = [[UILabel alloc] initWithFrame:CGRectMake(20, 40, 320, 80)];
    self.bootStatusLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleBottomMargin;
    self.bootStatusLabel.textColor = [UIColor whiteColor];
    self.bootStatusLabel.font = [UIFont boldSystemFontOfSize:15];
    self.bootStatusLabel.textAlignment = NSTextAlignmentCenter;
    self.bootStatusLabel.numberOfLines = 4;
    self.bootStatusLabel.text = @"Dang chuan bi Ikemen GO...";
    [self.view addSubview:self.bootStatusLabel];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    self.bootStatusLabel.frame = CGRectMake(20, (self.view.bounds.size.height - 80) * 0.5, self.view.bounds.size.width - 40, 80);
    for (UIView *view in self.view.subviews) {
        if ([view isKindOfClass:[MetalContainerView class]]) {
            self.metalContainerView = (MetalContainerView *)view;
            self.bootStatusLabel.hidden = YES;
        }
        for (UIView *view2 in view.subviews) {
            if ([view2 isKindOfClass:[TouchOverlayView class]]) {
                self.overlayView = (TouchOverlayView *)view2;
                break;
            }
        }
    }
}

- (void)viewWillTransitionToSize:(CGSize)size withTransitionCoordinator:(id<UIViewControllerTransitionCoordinator>)coordinator {
    [super viewWillTransitionToSize:size withTransitionCoordinator:coordinator];
    CGFloat scale = self.view.window.screen.nativeScale ?: [UIScreen mainScreen].nativeScale;
    CGSize boundsSize = self.view.bounds.size;
    CGSize newDrawableSize = CGSizeMake(boundsSize.width * scale, boundsSize.height * scale);
    CGRect newFrame = CGRectMake(self.view.bounds.origin.x, self.view.bounds.origin.y, newDrawableSize.width, newDrawableSize.height);
    self.metalContainerView.frame = newFrame;
    self.metalContainerView.metalLayer.frame = newFrame;
    self.metalContainerView.metalLayer.contentsScale = scale;
    self.metalContainerView.metalLayer.drawableSize = newDrawableSize;
    [_metalContainerView setNeedsLayout];
    [_overlayView setNeedsLayout];
}

- (NSURL *)documentsAssetsURL {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSURL *docs = [[fm URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask] firstObject];
    [fm createDirectoryAtURL:docs withIntermediateDirectories:YES attributes:nil error:nil];
    return docs;
}

- (void)viewDidAppear:(BOOL)animated {
    [super viewDidAppear:animated];

    if (self.view.window) {
        self.view.window.windowLevel = UIWindowLevelNormal + 1.0f;
    }

    if (self.ikemenStarted) {
        return;
    }

    self.assetsFolderURL = [self documentsAssetsURL];
    [self prepareDocumentsAndRun];
}

- (void)prepareDocumentsAndRun {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *basePath = self.assetsFolderURL.path;
    NSString *mainLua = [basePath stringByAppendingPathComponent:@"external/script/main.lua"];
    NSString *sysBase = [basePath stringByAppendingPathComponent:@"data/system.base.def"];

    BOOL hasEngineAssets = [fm fileExistsAtPath:mainLua] && [fm fileExistsAtPath:sysBase];
    if (!hasEngineAssets) {
        self.bootStatusLabel.hidden = NO;
        self.bootStatusLabel.text = @"Dang giai nen du lieu mac dinh vao thu muc I.K.E.M.E.N-Go...\\n(Chi chay 1 lan dau)";
        dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
            NSURL *zipURL = [[NSBundle mainBundle] URLForResource:@"DefaultAssets" withExtension:@"zip"];
            BOOL ok = NO;
            NSString *errText = nil;
            if (!zipURL) {
                errText = @"Khong tim thay DefaultAssets.zip trong IPA.";
            } else {
                NSString *selectDef = [basePath stringByAppendingPathComponent:@"data/select.def"];
                NSData *savedSelect = [fm fileExistsAtPath:selectDef] ? [NSData dataWithContentsOfFile:selectDef] : nil;

                ok = [SSZipArchive unzipFileAtPath:zipURL.path toDestination:basePath];
                if (ok && savedSelect.length > 0) {
                    [savedSelect writeToFile:selectDef atomically:YES];
                }
                if (!ok) {
                    errText = @"Giai nen DefaultAssets.zip that bai.";
                }
            }
            dispatch_async(dispatch_get_main_queue(), ^{
                if (!ok) {
                    self.bootStatusLabel.text = errText ?: @"Loi giai nen du lieu.";
                    return;
                }
                self.bootStatusLabel.text = @"Dang khoi dong Ikemen GO...";
                [self runIkemenGo];
            });
        });
    } else {
        self.bootStatusLabel.hidden = NO;
        self.bootStatusLabel.text = @"Dang khoi dong Ikemen GO...";
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.15 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self runIkemenGo];
        });
    }
}

- (void)runIkemenGo {
    if (_ikemenStarted || !_assetsFolderURL) {
        return;
    }

    const char *path = _assetsFolderURL.path.fileSystemRepresentation;
    if (!path) {
        self.bootStatusLabel.text = @"Loi: Khong doc duoc duong dan Documents.";
        return;
    }

    char **argv = calloc(4, sizeof(char *));
    if (!argv) return;

    argv[0] = strdup("ikemen-go");
    argv[1] = strdup("--assets");
    argv[2] = strdup(path);
    argv[3] = NULL;

    self.ikemenStarted = YES;
    dispatch_async(dispatch_get_main_queue(), ^{
        SDL_SetMainReady();

        NSString *dbPath = [self.assetsFolderURL.path stringByAppendingPathComponent:@"external/gamecontrollerdb.txt"];
        if ([[NSFileManager defaultManager] fileExistsAtPath:dbPath]) {
            SDL_SetHint(SDL_HINT_GAMECONTROLLERCONFIG_FILE, [dbPath UTF8String]);
        }

        SDL_SetHint(SDL_HINT_JOYSTICK_MFI, "1");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        SDL_SetHint(SDL_HINT_GAMECONTROLLER_USE_BUTTON_LABELS, "1");

        self.overlayView.sdlWasInit = YES;
        int result = SDL_main(3, argv);
        (void)result;

        self.ikemenStarted = NO;
        self.bootStatusLabel.hidden = NO;
        self.bootStatusLabel.text = @"Engine da dung. Kiem tra thu muc save/logs trong Tep.";

        for (int i = 0; i < 3; i++) {
            free(argv[i]);
        }
        free(argv);
    });
}

- (void)touchOverlayDidTapGameFolder:(TouchOverlayView *)view {
}

- (void)prepareForSegue:(UIStoryboardSegue *)segue sender:(id)sender {
    if ([segue.destinationViewController isKindOfClass:[TouchOverlayViewController class]]) {
        TouchOverlayViewController *child = (TouchOverlayViewController *)segue.destinationViewController;
        [child setParentVC:self];
    }
}

@end
"""
with open(os.path.join(app_dir, "ViewController.m"), "w", encoding="utf-8", newline="\n") as fp:
    fp.write(vc_m)
print("==> Replaced ViewController.m")

# 6. An dong chu trang thai boot ngay khi man hinh game Metal hien len
sdl_fix_path = os.path.join(app_dir, "SDLWindowFix.m")
with open(sdl_fix_path, "r", encoding="utf-8", errors="replace") as fp:
    sdl_fix = fp.read()

target_line = "[hostView insertSubview:metalHostView atIndex:0];"
if target_line in sdl_fix and "Hide boot labels" not in sdl_fix:
    replacement = (
        target_line + "\n"
        "    // Hide boot labels once Metal view is ready\n"
        "    for (UIView *v in hostView.subviews) {\n"
        "        if ([v isKindOfClass:[UILabel class]]) { v.hidden = YES; }\n"
        "    }"
    )
    sdl_fix = sdl_fix.replace(target_line, replacement, 1)
    with open(sdl_fix_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(sdl_fix)
    print("==> Patched SDLWindowFix.m")

print("==> All custom iOS wrapper patches applied successfully!")