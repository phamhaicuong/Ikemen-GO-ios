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

# 2. Cai dat IkemenTouchHUD duoi dang header de tranh bien dich trung
hud_dst = os.path.join(app_dir, "IkemenTouchHUD_impl.h")
shutil.copy2(hud_src, hud_dst)
print("==> Installed IkemenTouchHUD_impl.h")

# 3. Thay TouchOverlayView.m
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

# 4. Thay TouchOverlayViewController.m (bo awakeFromNib, gan HUD gon trong viewDidLoad)
touch_vc_m = """#import "TouchOverlayViewController.h"
#import "TouchOverlayView.h"
#import "ViewController.h"
#import "IkemenTouchHUD_impl.h"

@interface TouchOverlayViewController ()
@property (nonatomic, strong) IkemenTouchHUD *customHUD;
@end

@implementation TouchOverlayViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor clearColor];
    self.view.opaque = NO;
    if ([self.view isKindOfClass:[TouchOverlayView class]]) {
        self.overlayView = (TouchOverlayView *)self.view;
        self.overlayView.delegate = self.parentVC;
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
    if (self.isViewLoaded && [self.view isKindOfClass:[TouchOverlayView class]]) {
        self.overlayView = (TouchOverlayView *)self.view;
        self.overlayView.delegate = _parentVC;
    }
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

# 5. Thay ViewController.m:
#    - Doc thang tu Documents (I.K.E.M.E.N-Go), tu dong bo file loi engine ma giu nguyen chars/stages/select.def
#    - Tu sua save/config.ini neu nguoi dung chep data PC vao
#    - Hien bang loi + nut khoi phuc ngay tren man hinh neu engine dung (khong out ngang)
vc_m = """#import "GamepadInputs.h"
#import "ViewController.h"
#import "TouchOverlayView.h"
#import "TouchOverlayViewController.h"
#import "AnalogJoystickView.h"
#import <Foundation/Foundation.h>
#import <GameController/GameController.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#import <stdio.h>
#import "zlib.h"
#import "ZipArchive.h"
#import "libikemen.h"
#import <SDL2/SDL.h>
#import "GoWindow.h"
#import "SDLWindowFix.h"

static NSString *const kCoreSyncMarker = @".ikemen-core-sync-v5";

@interface ViewController ()
@property (nonatomic, strong) NSURL *assetsFolderURL;
@property (nonatomic, assign) BOOL ikemenStarted;
@property (nonatomic, strong) TouchOverlayView *overlayView;
@property (nonatomic, strong) MetalContainerView *metalContainerView;
@property (nonatomic, strong) UILabel *bootStatusLabel;
@property (nonatomic, strong) UIView *errorOverlayView;
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

    self.bootStatusLabel = [[UILabel alloc] initWithFrame:CGRectMake(20, 40, 320, 90)];
    self.bootStatusLabel.tag = 9991;
    self.bootStatusLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleBottomMargin;
    self.bootStatusLabel.textColor = [UIColor whiteColor];
    self.bootStatusLabel.font = [UIFont boldSystemFontOfSize:15];
    self.bootStatusLabel.textAlignment = NSTextAlignmentCenter;
    self.bootStatusLabel.numberOfLines = 5;
    self.bootStatusLabel.text = @"Dang chuan bi Ikemen GO...";
    [self.view addSubview:self.bootStatusLabel];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    self.bootStatusLabel.frame = CGRectMake(20, (self.view.bounds.size.height - 90) * 0.5, self.view.bounds.size.width - 40, 90);
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
    [self prepareDocumentsAndRunForceReset:NO];
}

- (void)copyItemOverwriteFrom:(NSString *)src to:(NSString *)dst {
    NSFileManager *fm = [NSFileManager defaultManager];
    BOOL isDir = NO;
    if (![fm fileExistsAtPath:src isDirectory:&isDir]) return;
    if (isDir) {
        [fm createDirectoryAtPath:dst withIntermediateDirectories:YES attributes:nil error:nil];
        NSArray<NSString *> *items = [fm contentsOfDirectoryAtPath:src error:nil];
        for (NSString *item in items) {
            [self copyItemOverwriteFrom:[src stringByAppendingPathComponent:item]
                                     to:[dst stringByAppendingPathComponent:item]];
        }
    } else {
        [fm createDirectoryAtPath:[dst stringByDeletingLastPathComponent] withIntermediateDirectories:YES attributes:nil error:nil];
        if ([fm fileExistsAtPath:dst]) {
            [fm removeItemAtPath:dst error:nil];
        }
        [fm copyItemAtPath:src toPath:dst error:nil];
    }
}

- (void)repairConfigAtBasePath:(NSString *)basePath {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *saveDir = [basePath stringByAppendingPathComponent:@"save"];
    [fm createDirectoryAtPath:saveDir withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *cfgPath = [saveDir stringByAppendingPathComponent:@"config.ini"];

    NSArray<NSString *> *motifCandidates = @[
        @"data/ikemen1/system.def",
        @"data/system.def",
        @"data/mugen1/system.def",
        @"data/system.base.def"
    ];
    NSString *fallbackMotif = @"data/ikemen1/system.def";
    for (NSString *cand in motifCandidates) {
        if ([fm fileExistsAtPath:[basePath stringByAppendingPathComponent:cand]]) {
            fallbackMotif = cand;
            break;
        }
    }

    if (![fm fileExistsAtPath:cfgPath]) {
        return;
    }

    NSString *txt = [NSString stringWithContentsOfFile:cfgPath encoding:NSUTF8StringEncoding error:nil];
    if (!txt) {
        [fm removeItemAtPath:cfgPath error:nil];
        return;
    }

    NSMutableArray<NSString *> *outLines = [NSMutableArray array];
    BOOL changed = NO;
    for (NSString *rawLine in [txt componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
        NSString *trim = [rawLine stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([trim hasPrefix:@"Motif"] && [trim containsString:@"="]) {
            NSRange eq = [rawLine rangeOfString:@"="];
            NSString *val = [[rawLine substringFromIndex:eq.location + 1] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
            if (val.length == 0 || ![fm fileExistsAtPath:[basePath stringByAppendingPathComponent:val]]) {
                [outLines addObject:[NSString stringWithFormat:@"Motif = %@", fallbackMotif]];
                changed = YES;
                continue;
            }
        } else if ([trim hasPrefix:@"System"] && [trim containsString:@"="] && ![trim hasPrefix:@"System."]) {
            NSRange eq = [rawLine rangeOfString:@"="];
            NSString *key = [[rawLine substringToIndex:eq.location] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
            if ([key isEqualToString:@"System"]) {
                [outLines addObject:@"System = external/script/main.lua"];
                changed = YES;
                continue;
            }
        } else if ([trim hasPrefix:@"RenderMode"] && [trim containsString:@"="]) {
            [outLines addObject:@"RenderMode = Vulkan 1.3"];
            changed = YES;
            continue;
        } else if ([trim hasPrefix:@"BootLoadingMode"] && [trim containsString:@"="]) {
            [outLines addObject:@"BootLoadingMode = 0"];
            changed = YES;
            continue;
        }
        [outLines addObject:rawLine];
    }

    if (changed) {
        [[outLines componentsJoinedByString:@"\\n"] writeToFile:cfgPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}

- (BOOL)syncEngineCoreAtBasePath:(NSString *)basePath forceFullReset:(BOOL)forceFullReset errorOut:(NSString **)errorOut {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSURL *zipURL = [[NSBundle mainBundle] URLForResource:@"DefaultAssets" withExtension:@"zip"];
    if (!zipURL) {
        if (errorOut) *errorOut = @"Khong tim thay DefaultAssets.zip ben trong file IPA.";
        return NO;
    }

    BOOL hasChars = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"chars"]];
    BOOL hasData  = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data"]];
    BOOL hasStages = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"stages"]];

    if (forceFullReset || !hasChars || !hasData || !hasStages) {
        NSString *selectDef = [basePath stringByAppendingPathComponent:@"data/select.def"];
        NSData *savedSelect = (!forceFullReset && [fm fileExistsAtPath:selectDef]) ? [NSData dataWithContentsOfFile:selectDef] : nil;

        BOOL ok = [SSZipArchive unzipFileAtPath:zipURL.path toDestination:basePath];
        if (!ok) {
            if (errorOut) *errorOut = @"Giai nen DefaultAssets.zip vao Documents that bai.";
            return NO;
        }
        if (savedSelect.length > 0) {
            [savedSelect writeToFile:selectDef atomically:YES];
        }
        [@"ok" writeToFile:[basePath stringByAppendingPathComponent:kCoreSyncMarker] atomically:YES encoding:NSUTF8StringEncoding error:nil];
        [self repairConfigAtBasePath:basePath];
        return YES;
    }

    BOOL coreSynced = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:kCoreSyncMarker]];
    BOOL hasMainLua = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"external/script/main.lua"]];
    BOOL hasSysBase = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data/system.base.def"]];
    BOOL hasCommonZss = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data/common1.cns.zss"]];
    BOOL hasGamepadDb = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"external/gamecontrollerdb.txt"]];

    if (!coreSynced || !hasMainLua || !hasSysBase || !hasCommonZss || !hasGamepadDb) {
        NSString *tmpDir = [NSTemporaryDirectory() stringByAppendingPathComponent:@"IkemenCoreSyncTmp"];
        [fm removeItemAtPath:tmpDir error:nil];
        [fm createDirectoryAtPath:tmpDir withIntermediateDirectories:YES attributes:nil error:nil];

        BOOL ok = [SSZipArchive unzipFileAtPath:zipURL.path toDestination:tmpDir];
        if (ok) {
            NSArray<NSString *> *corePaths = @[
                @"external/script",
                @"external/shaders",
                @"external/gamecontrollerdb.txt",
                @"data/system.base.def",
                @"data/common.air",
                @"data/common.cmd",
                @"data/common.const",
                @"data/common1.cns.zss",
                @"data/action.zss",
                @"data/demo.zss",
                @"data/dizzy.zss",
                @"data/functions.zss",
                @"data/guardbreak.zss",
                @"data/score.zss",
                @"data/system.zss",
                @"data/tag.zss",
                @"data/training.zss",
                @"font/debug.def",
                @"font/default-3x5.def",
                @"font/default-3x5.sff",
                @"font/default-3x5-bold.def",
                @"font/default-3x5-bold.sff",
                @"font/Open_Sans"
            ];
            for (NSString *rel in corePaths) {
                [self copyItemOverwriteFrom:[tmpDir stringByAppendingPathComponent:rel]
                                         to:[basePath stringByAppendingPathComponent:rel]];
            }
            BOOL hasAnyMotif = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data/ikemen1/system.def"]]
                            || [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data/system.def"]];
            if (!hasAnyMotif) {
                [self copyItemOverwriteFrom:[tmpDir stringByAppendingPathComponent:@"data/ikemen1"]
                                         to:[basePath stringByAppendingPathComponent:@"data/ikemen1"]];
            }
            if (![fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data/select.def"]]) {
                [self copyItemOverwriteFrom:[tmpDir stringByAppendingPathComponent:@"data/select.def"]
                                         to:[basePath stringByAppendingPathComponent:@"data/select.def"]];
            }
            [@"ok" writeToFile:[basePath stringByAppendingPathComponent:kCoreSyncMarker] atomically:YES encoding:NSUTF8StringEncoding error:nil];
        }
        [fm removeItemAtPath:tmpDir error:nil];
    }

    [self repairConfigAtBasePath:basePath];
    return YES;
}

- (void)prepareDocumentsAndRunForceReset:(BOOL)forceReset {
    if (self.errorOverlayView) {
        [self.errorOverlayView removeFromSuperview];
        self.errorOverlayView = nil;
    }

    NSString *basePath = self.assetsFolderURL.path;
    self.bootStatusLabel.hidden = NO;
    self.bootStatusLabel.text = forceReset
        ? @"Dang khoi phuc du lieu mac dinh..."
        : @"Dang kiem tra du lieu & khoi dong Ikemen GO...";

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSString *errText = nil;
        BOOL ok = [self syncEngineCoreAtBasePath:basePath forceFullReset:forceReset errorOut:&errText];
        dispatch_async(dispatch_get_main_queue(), ^{
            if (!ok) {
                [self showEngineErrorOverlay:(errText ?: @"Loi chuan bi du lieu.")];
                return;
            }
            self.bootStatusLabel.text = @"Dang khoi dong do hoa Vulkan...";
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.6 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
                [self runIkemenGo];
            });
        });
    });
}

- (void)showEngineErrorOverlay:(NSString *)message {
    self.bootStatusLabel.hidden = YES;
    if (self.errorOverlayView) {
        [self.errorOverlayView removeFromSuperview];
    }

    UIView *overlay = [[UIView alloc] initWithFrame:self.view.bounds];
    overlay.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    overlay.backgroundColor = [UIColor colorWithWhite:0.05 alpha:0.95];

    UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(20, 24, overlay.bounds.size.width - 40, 28)];
    title.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    title.text = @"Ikemen GO da dung (Chi tiet loi)";
    title.textColor = [UIColor colorWithRed:1.0 green:0.35 blue:0.35 alpha:1.0];
    title.font = [UIFont boldSystemFontOfSize:17];
    title.textAlignment = NSTextAlignmentCenter;
    [overlay addSubview:title];

    UITextView *tv = [[UITextView alloc] initWithFrame:CGRectMake(20, 60, overlay.bounds.size.width - 40, overlay.bounds.size.height - 130)];
    tv.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    tv.backgroundColor = [UIColor colorWithWhite:0.12 alpha:1.0];
    tv.textColor = [UIColor whiteColor];
    tv.font = [UIFont fontWithName:@"Menlo" size:12] ?: [UIFont systemFontOfSize:12];
    tv.editable = NO;
    tv.layer.cornerRadius = 10;
    tv.text = message ?: @"Khong co chi tiet loi.";
    [overlay addSubview:tv];

    CGFloat btnY = overlay.bounds.size.height - 56;
    CGFloat halfW = (overlay.bounds.size.width - 52) * 0.5;

    UIButton *fixCfgBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    fixCfgBtn.frame = CGRectMake(20, btnY, halfW, 40);
    fixCfgBtn.autoresizingMask = UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleRightMargin;
    [fixCfgBtn setTitle:@"Xoa config.ini & thu lai" forState:UIControlStateNormal];
    [fixCfgBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    fixCfgBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    fixCfgBtn.backgroundColor = [UIColor colorWithRed:0.15 green:0.50 blue:0.90 alpha:1.0];
    fixCfgBtn.layer.cornerRadius = 8;
    [fixCfgBtn addTarget:self action:@selector(onTapResetConfig) forControlEvents:UIControlEventTouchUpInside];
    [overlay addSubview:fixCfgBtn];

    UIButton *resetAllBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    resetAllBtn.frame = CGRectMake(32 + halfW, btnY, halfW, 40);
    resetAllBtn.autoresizingMask = UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleLeftMargin;
    [resetAllBtn setTitle:@"Nap lai data mac dinh" forState:UIControlStateNormal];
    [resetAllBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    resetAllBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    resetAllBtn.backgroundColor = [UIColor colorWithRed:0.80 green:0.25 blue:0.25 alpha:1.0];
    resetAllBtn.layer.cornerRadius = 8;
    [resetAllBtn addTarget:self action:@selector(onTapResetDefaultAssets) forControlEvents:UIControlEventTouchUpInside];
    [overlay addSubview:resetAllBtn];

    self.errorOverlayView = overlay;
    [self.view addSubview:overlay];
}

- (void)onTapResetConfig {
    NSString *cfgPath = [self.assetsFolderURL.path stringByAppendingPathComponent:@"save/config.ini"];
    [[NSFileManager defaultManager] removeItemAtPath:cfgPath error:nil];
    [self prepareDocumentsAndRunForceReset:NO];
}

- (void)onTapResetDefaultAssets {
    NSString *cfgPath = [self.assetsFolderURL.path stringByAppendingPathComponent:@"save/config.ini"];
    [[NSFileManager defaultManager] removeItemAtPath:cfgPath error:nil];
    [self prepareDocumentsAndRunForceReset:YES];
}

- (void)runIkemenGo {
    if (_ikemenStarted || !_assetsFolderURL) {
        return;
    }

    NSString *basePath = _assetsFolderURL.path;
    const char *path = basePath.fileSystemRepresentation;
    if (!path) {
        [self showEngineErrorOverlay:@"Loi: Khong doc duoc duong dan Documents."];
        return;
    }

    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *logsDir = [basePath stringByAppendingPathComponent:@"save/logs"];
    [fm createDirectoryAtPath:logsDir withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *lastErrPath = [logsDir stringByAppendingPathComponent:@"last_error.txt"];
    NSString *stderrPath = [logsDir stringByAppendingPathComponent:@"boot_stderr.log"];
    [fm removeItemAtPath:lastErrPath error:nil];
    freopen(stderrPath.fileSystemRepresentation, "w", stderr);
    setvbuf(stderr, NULL, _IONBF, 0);

    char **argv = calloc(4, sizeof(char *));
    if (!argv) return;

    argv[0] = strdup("ikemen-go");
    argv[1] = strdup("--assets");
    argv[2] = strdup(path);
    argv[3] = NULL;

    self.ikemenStarted = YES;
    dispatch_async(dispatch_get_main_queue(), ^{
        SDL_SetMainReady();

        NSString *dbPath = [basePath stringByAppendingPathComponent:@"external/gamecontrollerdb.txt"];
        if ([fm fileExistsAtPath:dbPath]) {
            SDL_SetHint(SDL_HINT_GAMECONTROLLERCONFIG_FILE, [dbPath UTF8String]);
        }

        SDL_SetHint(SDL_HINT_JOYSTICK_MFI, "1");
        SDL_SetHint(SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS, "1");
        SDL_SetHint(SDL_HINT_GAMECONTROLLER_USE_BUTTON_LABELS, "1");

        self.overlayView.sdlWasInit = YES;
        int result = SDL_main(3, argv);
        (void)result;

        fflush(stderr);
        self.ikemenStarted = NO;

        NSString *errContent = [NSString stringWithContentsOfFile:lastErrPath encoding:NSUTF8StringEncoding error:nil];
        if (errContent.length == 0) {
            errContent = [NSString stringWithContentsOfFile:stderrPath encoding:NSUTF8StringEncoding error:nil];
        }
        if (errContent.length == 0) {
            errContent = @"Engine da thoat ma khong ghi loi. Kiem tra thu muc save/logs trong Tep.";
        }
        [self showEngineErrorOverlay:errContent];

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

# 6. An dong trang thai boot (tag 9991) khi MetalContainerView gan vao xong
sdl_fix_path = os.path.join(app_dir, "SDLWindowFix.m")
with open(sdl_fix_path, "r", encoding="utf-8", errors="replace") as fp:
    sdl_fix = fp.read()

target_line = "[hostView insertSubview:metalHostView atIndex:0];"
if target_line in sdl_fix and "viewWithTag:9991" not in sdl_fix:
    replacement = (
        target_line + "\n"
        "    UIView *bootLbl = [hostView viewWithTag:9991];\n"
        "    if (bootLbl) { bootLbl.hidden = YES; }"
    )
    sdl_fix = sdl_fix.replace(target_line, replacement, 1)
    with open(sdl_fix_path, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(sdl_fix)
    print("==> Patched SDLWindowFix.m")

print("==> All custom iOS wrapper patches applied successfully!")