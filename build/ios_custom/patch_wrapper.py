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

# 1. Patch Info.plist de luon hien thu muc logo trong ung dung Tep
plist_path = os.path.join(app_dir, "Info.plist")
with open(plist_path, "rb") as fp:
    plist_data = plistlib.load(fp)
plist_data["UIFileSharingEnabled"] = True
plist_data["LSSupportsOpeningDocumentsInPlace"] = True
with open(plist_path, "wb") as fp:
    plistlib.dump(plist_data, fp)
print("==> Patched Info.plist")

# 2. Chep IkemenTouchHUD duoi dang header
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

# 4. Thay TouchOverlayViewController.m
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

# 5. Thay ViewController.m voi he thong tu dong nhap Nhan Vat / Map / Nhac
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

static NSString *const kCoreSyncMarker = @".ikemen-core-sync-v7";

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

#pragma mark - File & Text Helpers

- (NSString *)readTextFlexible:(NSString *)path {
    NSError *err = nil;
    NSString *s = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&err];
    if (!s) {
        s = [NSString stringWithContentsOfFile:path encoding:NSISOLatin1StringEncoding error:nil];
    }
    return s;
}

- (void)copyItemOverwriteFrom:(NSString *)src to:(NSString *)dst {
    NSFileManager *fm = [NSFileManager defaultManager];
    BOOL isDir = NO;
    if (![fm fileExistsAtPath:src isDirectory:&isDir]) return;
    if (isDir) {
        [fm createDirectoryAtPath:dst withIntermediateDirectories:YES attributes:nil error:nil];
        NSArray<NSString *> *items = [fm contentsOfDirectoryAtPath:src error:nil];
        for (NSString *item in items) {
            if ([item isEqualToString:@"__MACOSX"] || [item isEqualToString:@".DS_Store"] ||
                [[item lowercaseString] isEqualToString:@"thumbs.db"] || [[item lowercaseString] isEqualToString:@"desktop.ini"]) {
                continue;
            }
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

- (BOOL)isAudioFileName:(NSString *)name {
    NSString *ext = [[name pathExtension] lowercaseString];
    return [ext isEqualToString:@"mp3"] || [ext isEqualToString:@"ogg"] ||
           [ext isEqualToString:@"wav"] || [ext isEqualToString:@"flac"];
}

- (void)fixCaseSensitivityInDef:(NSString *)defPath baseDir:(NSString *)baseDir {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *text = [self readTextFlexible:defPath];
    if (text.length == 0) return;

    NSMutableDictionary<NSString *, NSString *> *fileMap = [NSMutableDictionary dictionary];
    NSDirectoryEnumerator<NSString *> *en = [fm enumeratorAtPath:baseDir];
    for (NSString *rel in en) {
        BOOL isDir = NO;
        NSString *full = [baseDir stringByAppendingPathComponent:rel];
        if ([fm fileExistsAtPath:full isDirectory:&isDir] && !isDir) {
            NSString *norm = [rel stringByReplacingOccurrencesOfString:@"\\\\" withString:@"/"];
            fileMap[[norm lowercaseString]] = norm;
        }
    }

    BOOL inTargetSec = NO;
    BOOL changed = NO;
    NSMutableArray<NSString *> *outLines = [NSMutableArray array];
    for (NSString *line in [text componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
        NSString *trim = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([trim hasPrefix:@"["] && [trim hasSuffix:@"]"]) {
            NSString *lowSec = [trim lowercaseString];
            inTargetSec = ([lowSec isEqualToString:@"[files]"] || [lowSec isEqualToString:@"[bgdef]"] || [lowSec isEqualToString:@"[music]"]);
            [outLines addObject:line];
            continue;
        }
        if (inTargetSec && ![trim hasPrefix:@";"] && [line containsString:@"="]) {
            NSRange semi = [line rangeOfString:@";"];
            NSString *codePart = (semi.location != NSNotFound) ? [line substringToIndex:semi.location] : line;
            NSString *commentPart = (semi.location != NSNotFound) ? [line substringFromIndex:semi.location] : @"";
            NSRange eq = [codePart rangeOfString:@"="];
            if (eq.location != NSNotFound) {
                NSString *key = [[codePart substringToIndex:eq.location] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
                NSString *val = [[codePart substringFromIndex:eq.location + 1] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
                NSString *cleanVal = [[val stringByTrimmingCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@"\\""]] stringByReplacingOccurrencesOfString:@"\\\\" withString:@"/"];
                NSString *actual = fileMap[[cleanVal lowercaseString]];
                if (!actual && [cleanVal hasPrefix:@"stages/"]) {
                    NSString *sub = [cleanVal substringFromIndex:7];
                    NSString *hit = fileMap[[sub lowercaseString]];
                    if (hit) actual = [@"stages/" stringByAppendingString:hit];
                }
                if (actual && ![actual isEqualToString:val]) {
                    NSString *rebuilt = commentPart.length > 0
                        ? [NSString stringWithFormat:@"%@ = %@ %@", key, actual, commentPart]
                        : [NSString stringWithFormat:@"%@ = %@", key, actual];
                    [outLines addObject:rebuilt];
                    changed = YES;
                    continue;
                }
            }
        }
        [outLines addObject:line];
    }

    if (changed) {
        [[outLines componentsJoinedByString:@"\\n"] writeToFile:defPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}

#pragma mark - Auto-Import Manager (1_Them_Nhan_Vat, 2_Them_Map, 3_Them_Nhac)

- (void)ensureUserImportFoldersAtBasePath:(NSString *)basePath {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSArray<NSString *> *folders = @[@"1_Them_Nhan_Vat", @"2_Them_Map", @"3_Them_Nhac", @"chars", @"stages", @"sound"];
    for (NSString *f in folders) {
        [fm createDirectoryAtPath:[basePath stringByAppendingPathComponent:f]
      withIntermediateDirectories:YES attributes:nil error:nil];
    }
    NSString *readmePath = [basePath stringByAppendingPathComponent:@"HUONG_DAN_THEM_MOD.txt"];
    if (![fm fileExistsAtPath:readmePath]) {
        NSString *guide =
            @"HUONG DAN THEM NHAN VAT / MAP / NHAC TU DONG (KHONG CAN SUA CODE):\\n\\n"
            @"1. Thu muc 1_Them_Nhan_Vat:\\n"
            @"   - Giai nen thu muc nhan vat (hoac tha thang file .zip) vao day.\\n"
            @"   - Mo lai game la nhan vat tu dong xuat hien trong danh sach chon!\\n\\n"
            @"2. Thu muc 2_Them_Map:\\n"
            @"   - Giai nen map (.def + .sff) hoac tha file .zip vao day.\\n"
            @"   - Mo lai game la map tu dong them vao danh sach san dau!\\n\\n"
            @"3. Thu muc 3_Them_Nhac:\\n"
            @"   - Chep file nhac .mp3 / .ogg / .wav vao day.\\n"
            @"   - Dat ten Title.mp3 / Select.mp3 / Versus.mp3 neu muon gan rieng,\\n"
            @"     hoac tha bat ky bai nao game se tu dong phat lam nhac nen & nhac dau!\\n";
        [guide writeToFile:readmePath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
}

- (NSString *)pickCharacterDefInDir:(NSString *)charDir {
    NSFileManager *fm = [NSFileManager defaultManager];
    NSArray<NSString *> *items = [[fm contentsOfDirectoryAtPath:charDir error:nil] sortedArrayUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
    NSMutableArray<NSString *> *defs = [NSMutableArray array];
    for (NSString *it in items) {
        if ([[[it pathExtension] lowercaseString] isEqualToString:@"def"]) {
            [defs addObject:it];
        }
    }
    if (defs.count == 0) return nil;
    NSString *folderLow = [[charDir lastPathComponent] lowercaseString];
    for (NSString *d in defs) {
        if ([[[d stringByDeletingPathExtension] lowercaseString] isEqualToString:folderLow]) {
            return d;
        }
    }
    for (NSString *d in defs) {
        NSString *t = [[self readTextFlexible:[charDir stringByAppendingPathComponent:d]] lowercaseString];
        if ([t containsString:@"[files]"] && [t containsString:@"[info]"] && ![t containsString:@"[bgdef]"]) {
            return d;
        }
    }
    return defs.firstObject;
}

- (void)collectCharDirsInRoot:(NSString *)rootDir into:(NSMutableArray<NSString *> *)outDirs depth:(int)depth {
    if (depth > 4) return;
    NSFileManager *fm = [NSFileManager defaultManager];
    NSString *defName = [self pickCharacterDefInDir:rootDir];
    if (defName) {
        NSString *t = [[self readTextFlexible:[rootDir stringByAppendingPathComponent:defName]] lowercaseString];
        if ([t containsString:@"[files]"] && ![t containsString:@"[bgdef]"]) {
            [outDirs addObject:rootDir];
            return;
        }
    }
    NSArray<NSString *> *items = [fm contentsOfDirectoryAtPath:rootDir error:nil];
    for (NSString *it in items) {
        if ([it hasPrefix:@"."] || [it isEqualToString:@"__MACOSX"]) continue;
        NSString *full = [rootDir stringByAppendingPathComponent:it];
        BOOL isDir = NO;
        if ([fm fileExistsAtPath:full isDirectory:&isDir] && isDir) {
            [self collectCharDirsInRoot:full into:outDirs depth:depth + 1];
        }
    }
}

- (void)registerEntries:(NSArray<NSString *> *)entries section:(NSString *)sectionHeader inSelectDef:(NSString *)selectPath isStage:(BOOL)isStage {
    NSFileManager *fm = [NSFileManager defaultManager];
    if (![fm fileExistsAtPath:selectPath] || entries.count == 0) return;

    NSString *txt = [self readTextFlexible:selectPath];
    if (!txt) return;

    NSArray<NSString *> *rawLines = [txt componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]];
    NSMutableSet<NSString *> *existingKeys = [NSMutableSet set];
    BOOL inSec = NO;
    NSString *secLow = [sectionHeader lowercaseString];

    for (NSString *line in rawLines) {
        NSString *trim = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([trim hasPrefix:@"["] && [trim hasSuffix:@"]"]) {
            inSec = [[trim lowercaseString] isEqualToString:secLow];
            continue;
        }
        if (inSec && trim.length > 0 && ![trim hasPrefix:@";"]) {
            NSString *firstTok = [[[trim componentsSeparatedByString:@","] firstObject] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
            NSString *norm = [[firstTok stringByReplacingOccurrencesOfString:@"\\\\" withString:@"/"] lowercaseString];
            [existingKeys addObject:norm];
            if (!isStage) {
                NSString *folderPart = [[norm componentsSeparatedByString:@"/"] firstObject];
                if (folderPart.length > 0) [existingKeys addObject:folderPart];
            }
        }
    }

    NSMutableArray<NSString *> *toInsert = [NSMutableArray array];
    for (NSString *entry in entries) {
        NSString *firstTok = [[[entry componentsSeparatedByString:@","] firstObject] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        NSString *norm = [[firstTok stringByReplacingOccurrencesOfString:@"\\\\" withString:@"/"] lowercaseString];
        NSString *folderPart = [[norm componentsSeparatedByString:@"/"] firstObject];
        if ([existingKeys containsObject:norm] || (!isStage && folderPart.length > 0 && [existingKeys containsObject:folderPart])) {
            continue;
        }
        [toInsert addObject:entry];
        [existingKeys addObject:norm];
        if (!isStage && folderPart.length > 0) [existingKeys addObject:folderPart];
    }

    if (toInsert.count == 0) return;

    NSMutableArray<NSString *> *outLines = [NSMutableArray array];
    BOOL inserted = NO;
    for (NSString *line in rawLines) {
        [outLines addObject:line];
        NSString *trim = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if (!inserted && [[trim lowercaseString] isEqualToString:secLow]) {
            for (NSString *ne in toInsert) {
                [outLines addObject:ne];
            }
            inserted = YES;
        }
    }
    if (!inserted) {
        [outLines addObject:sectionHeader];
        for (NSString *ne in toInsert) {
            [outLines addObject:ne];
        }
    }

    [[outLines componentsJoinedByString:@"\\n"] writeToFile:selectPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
}

- (void)processAutoImportAtBasePath:(NSString *)basePath {
    NSFileManager *fm = [NSFileManager defaultManager];
    [self ensureUserImportFoldersAtBasePath:basePath];

    NSString *charsDir  = [basePath stringByAppendingPathComponent:@"chars"];
    NSString *stagesDir = [basePath stringByAppendingPathComponent:@"stages"];
    NSString *soundDir  = [basePath stringByAppendingPathComponent:@"sound"];
    NSString *dropChars  = [basePath stringByAppendingPathComponent:@"1_Them_Nhan_Vat"];
    NSString *dropStages = [basePath stringByAppendingPathComponent:@"2_Them_Map"];
    NSString *dropMusic  = [basePath stringByAppendingPathComponent:@"3_Them_Nhac"];

    // --- 1. IMPORT NHAN VAT TU 1_Them_Nhan_Vat ---
    NSArray<NSString *> *charDropItems = [fm contentsOfDirectoryAtPath:dropChars error:nil];
    for (NSString *item in charDropItems) {
        if ([item hasPrefix:@"."]) continue;
        NSString *src = [dropChars stringByAppendingPathComponent:item];
        BOOL isDir = NO;
        [fm fileExistsAtPath:src isDirectory:&isDir];

        NSString *scanRoot = nil;
        NSString *tmpUnzip = nil;
        if (isDir) {
            scanRoot = src;
        } else if ([[[item pathExtension] lowercaseString] isEqualToString:@"zip"]) {
            tmpUnzip = [NSTemporaryDirectory() stringByAppendingPathComponent:[@"IkemenCharZip_" stringByAppendingString:[NSUUID UUID].UUIDString]];
            [fm createDirectoryAtPath:tmpUnzip withIntermediateDirectories:YES attributes:nil error:nil];
            if ([SSZipArchive unzipFileAtPath:src toDestination:tmpUnzip]) {
                scanRoot = tmpUnzip;
            }
        }

        if (scanRoot) {
            NSMutableArray<NSString *> *foundChars = [NSMutableArray array];
            [self collectCharDirsInRoot:scanRoot into:foundChars depth:0];
            for (NSString *cDir in foundChars) {
                NSString *folderName = [cDir lastPathComponent];
                if ([folderName hasPrefix:@"IkemenCharZip_"]) {
                    folderName = [item stringByDeletingPathExtension];
                }
                NSString *dst = [charsDir stringByAppendingPathComponent:folderName];
                [self copyItemOverwriteFrom:cDir to:dst];
            }
            if (foundChars.count > 0) {
                [fm removeItemAtPath:src error:nil];
            }
        }
        if (tmpUnzip) [fm removeItemAtPath:tmpUnzip error:nil];
    }

    NSMutableArray<NSString *> *charEntries = [NSMutableArray array];
    NSArray<NSString *> *allChars = [[fm contentsOfDirectoryAtPath:charsDir error:nil] sortedArrayUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
    for (NSString *folder in allChars) {
        if ([folder hasPrefix:@"."]) continue;
        NSString *full = [charsDir stringByAppendingPathComponent:folder];
        BOOL isDir = NO;
        if (![fm fileExistsAtPath:full isDirectory:&isDir] || !isDir) continue;
        NSString *mainDef = [self pickCharacterDefInDir:full];
        if (!mainDef) continue;
        [self fixCaseSensitivityInDef:[full stringByAppendingPathComponent:mainDef] baseDir:full];
        [charEntries addObject:[NSString stringWithFormat:@"%@/%@, random", folder, mainDef]];
    }

    // --- 2. IMPORT MAP TU 2_Them_Map ---
    NSArray<NSString *> *stageDropItems = [fm contentsOfDirectoryAtPath:dropStages error:nil];
    for (NSString *item in stageDropItems) {
        if ([item hasPrefix:@"."]) continue;
        NSString *src = [dropStages stringByAppendingPathComponent:item];
        BOOL isDir = NO;
        [fm fileExistsAtPath:src isDirectory:&isDir];

        if (!isDir && [[[item pathExtension] lowercaseString] isEqualToString:@"zip"]) {
            NSString *tmpUnzip = [NSTemporaryDirectory() stringByAppendingPathComponent:[@"IkemenStageZip_" stringByAppendingString:[NSUUID UUID].UUIDString]];
            [fm createDirectoryAtPath:tmpUnzip withIntermediateDirectories:YES attributes:nil error:nil];
            if ([SSZipArchive unzipFileAtPath:src toDestination:tmpUnzip]) {
                [self copyItemOverwriteFrom:tmpUnzip to:stagesDir];
                NSDirectoryEnumerator<NSString *> *en = [fm enumeratorAtPath:tmpUnzip];
                for (NSString *rel in en) {
                    if ([self isAudioFileName:rel]) {
                        [self copyItemOverwriteFrom:[tmpUnzip stringByAppendingPathComponent:rel]
                                                 to:[soundDir stringByAppendingPathComponent:[rel lastPathComponent]]];
                    }
                }
                [fm removeItemAtPath:src error:nil];
            }
            [fm removeItemAtPath:tmpUnzip error:nil];
        } else if (isDir) {
            [self copyItemOverwriteFrom:src to:[stagesDir stringByAppendingPathComponent:item]];
            NSDirectoryEnumerator<NSString *> *en = [fm enumeratorAtPath:src];
            for (NSString *rel in en) {
                if ([self isAudioFileName:rel]) {
                    [self copyItemOverwriteFrom:[src stringByAppendingPathComponent:rel]
                                             to:[soundDir stringByAppendingPathComponent:[rel lastPathComponent]]];
                }
            }
            [fm removeItemAtPath:src error:nil];
        } else {
            if ([self isAudioFileName:item]) {
                [self copyItemOverwriteFrom:src to:[soundDir stringByAppendingPathComponent:item]];
            } else {
                [self copyItemOverwriteFrom:src to:[stagesDir stringByAppendingPathComponent:item]];
            }
            [fm removeItemAtPath:src error:nil];
        }
    }

    NSMutableArray<NSString *> *stageEntries = [NSMutableArray array];
    NSDirectoryEnumerator<NSString *> *stEn = [fm enumeratorAtPath:stagesDir];
    for (NSString *rel in stEn) {
        if ([rel hasPrefix:@"."] || [rel containsString:@"__MACOSX"]) continue;
        if (![[[rel pathExtension] lowercaseString] isEqualToString:@"def"]) continue;
        NSString *full = [stagesDir stringByAppendingPathComponent:rel];
        NSString *txt = [[self readTextFlexible:full] lowercaseString];
        if ([txt containsString:@"[bgdef]"] || [txt containsString:@"[stageinfo]"]) {
            [self fixCaseSensitivityInDef:full baseDir:[full stringByDeletingLastPathComponent]];
            NSString *normRel = [rel stringByReplacingOccurrencesOfString:@"\\\\" withString:@"/"];
            [stageEntries addObject:[@"stages/" stringByAppendingString:normRel]];
        }
    }

    NSArray<NSString *> *selectFiles = @[
        [basePath stringByAppendingPathComponent:@"data/select.def"],
        [basePath stringByAppendingPathComponent:@"data/ikemen1/select.def"]
    ];
    for (NSString *sp in selectFiles) {
        [self registerEntries:charEntries section:@"[Characters]" inSelectDef:sp isStage:NO];
        [self registerEntries:stageEntries section:@"[ExtraStages]" inSelectDef:sp isStage:YES];
    }

    // --- 3. IMPORT NHAC TU 3_Them_Nhac ---
    NSMutableArray<NSString *> *userTracks = [NSMutableArray array];
    NSArray<NSString *> *musicItems = [[fm contentsOfDirectoryAtPath:dropMusic error:nil] sortedArrayUsingSelector:@selector(localizedCaseInsensitiveCompare:)];
    for (NSString *mFile in musicItems) {
        if ([mFile hasPrefix:@"."] || ![self isAudioFileName:mFile]) continue;
        NSString *src = [dropMusic stringByAppendingPathComponent:mFile];
        NSString *dst = [soundDir stringByAppendingPathComponent:mFile];
        [self copyItemOverwriteFrom:src to:dst];
        [userTracks addObject:[@"sound/" stringByAppendingString:mFile]];
    }

    if (userTracks.count > 0) {
        NSString *titleTrack = nil, *selectTrack = nil, *vsTrack = nil, *victoryTrack = nil;
        for (NSString *tr in userTracks) {
            NSString *low = [[tr lastPathComponent] lowercaseString];
            if (!titleTrack && ([low containsString:@"title"] || [low containsString:@"menu"])) titleTrack = tr;
            else if (!selectTrack && [low containsString:@"select"]) selectTrack = tr;
            else if (!vsTrack && ([low containsString:@"versus"] || [low hasPrefix:@"vs"])) vsTrack = tr;
            else if (!victoryTrack && ([low containsString:@"victory"] || [low containsString:@"win"])) victoryTrack = tr;
        }
        if (!titleTrack)   titleTrack   = userTracks[0];
        if (!selectTrack)  selectTrack  = userTracks.count > 1 ? userTracks[1] : userTracks[0];
        if (!vsTrack)      vsTrack      = userTracks.count > 2 ? userTracks[2] : userTracks[0];
        if (!victoryTrack) victoryTrack = userTracks.count > 3 ? userTracks[3] : userTracks[0];

        NSArray<NSString *> *motifDefs = @[
            [basePath stringByAppendingPathComponent:@"data/ikemen1/system.def"],
            [basePath stringByAppendingPathComponent:@"data/system.def"]
        ];
        for (NSString *mDef in motifDefs) {
            if (![fm fileExistsAtPath:mDef]) continue;
            NSString *txt = [self readTextFlexible:mDef];
            if (!txt) continue;
            NSMutableArray<NSString *> *outLines = [NSMutableArray array];
            BOOL inMusic = NO;
            BOOL changed = NO;
            for (NSString *line in [txt componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
                NSString *trim = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
                if ([trim hasPrefix:@"["] && [trim hasSuffix:@"]"]) {
                    inMusic = [[trim lowercaseString] isEqualToString:@"[music]"];
                    [outLines addObject:line];
                    continue;
                }
                if (inMusic && ![trim hasPrefix:@";"] && [trim containsString:@"="]) {
                    NSRange eq = [trim rangeOfString:@"="];
                    NSString *key = [[[trim substringToIndex:eq.location] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]] lowercaseString];
                    if ([key isEqualToString:@"title.bgm"]) {
                        [outLines addObject:[NSString stringWithFormat:@"title.bgm = %@", titleTrack]];
                        changed = YES; continue;
                    } else if ([key isEqualToString:@"select.bgm"]) {
                        [outLines addObject:[NSString stringWithFormat:@"select.bgm = %@", selectTrack]];
                        changed = YES; continue;
                    } else if ([key isEqualToString:@"vs.bgm"]) {
                        [outLines addObject:[NSString stringWithFormat:@"vs.bgm = %@", vsTrack]];
                        changed = YES; continue;
                    } else if ([key isEqualToString:@"victory.bgm"]) {
                        [outLines addObject:[NSString stringWithFormat:@"victory.bgm = %@", victoryTrack]];
                        changed = YES; continue;
                    }
                }
                [outLines addObject:line];
            }
            if (changed) {
                [[outLines componentsJoinedByString:@"\\n"] writeToFile:mDef atomically:YES encoding:NSUTF8StringEncoding error:nil];
            }
        }

        NSUInteger idx = 0;
        for (NSString *stRel in stageEntries) {
            NSString *stPath = [basePath stringByAppendingPathComponent:stRel];
            NSString *stTxt = [self readTextFlexible:stPath];
            if (!stTxt) continue;
            NSMutableArray<NSString *> *outLines = [NSMutableArray array];
            BOOL inMusic = NO;
            BOOL changed = NO;
            for (NSString *line in [stTxt componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
                NSString *trim = [line stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
                if ([trim hasPrefix:@"["] && [trim hasSuffix:@"]"]) {
                    inMusic = [[trim lowercaseString] isEqualToString:@"[music]"];
                    [outLines addObject:line];
                    continue;
                }
                if (inMusic && ![trim hasPrefix:@";"] && [trim containsString:@"="]) {
                    NSRange eq = [trim rangeOfString:@"="];
                    NSString *key = [[[trim substringToIndex:eq.location] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]] lowercaseString];
                    NSString *val = [[trim substringFromIndex:eq.location + 1] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
                    if ([key isEqualToString:@"bgmusic"]) {
                        BOOL exists = (val.length > 0 && [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:val]]);
                        if (!exists) {
                            NSString *pick = userTracks[idx % userTracks.count];
                            idx++;
                            [outLines addObject:[NSString stringWithFormat:@"bgmusic = %@", pick]];
                            changed = YES;
                            continue;
                        }
                    }
                }
                [outLines addObject:line];
            }
            if (changed) {
                [[outLines componentsJoinedByString:@"\\n"] writeToFile:stPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
            }
        }
    }
}

#pragma mark - Config & Core Sync

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
    NSString *curSec = @"";
    BOOL changed = NO;
    for (NSString *rawLine in [txt componentsSeparatedByCharactersInSet:[NSCharacterSet newlineCharacterSet]]) {
        NSString *trim = [rawLine stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
        if ([trim hasPrefix:@"["] && [trim hasSuffix:@"]"]) {
            curSec = trim;
        } else if ([curSec isEqualToString:@"[Keys_P1]"] && [trim hasPrefix:@"menu"] && [trim containsString:@"="]) {
            [outLines addObject:@"menu = TAB"];
            changed = YES; continue;
        } else if ([curSec isEqualToString:@"[Keys_P2]"] && [trim hasPrefix:@"menu"] && [trim containsString:@"="]) {
            [outLines addObject:@"menu = BACKSLASH"];
            changed = YES; continue;
        } else if ([trim hasPrefix:@"FirstRun"] && [trim containsString:@"="]) {
            [outLines addObject:@"FirstRun = 0"];
            changed = YES; continue;
        } else if ([trim hasPrefix:@"WindowIcon"] && [trim containsString:@"="]) {
            [outLines addObject:@"WindowIcon ="];
            changed = YES; continue;
        } else if ([trim hasPrefix:@"Motif"] && [trim containsString:@"="]) {
            NSRange eq = [rawLine rangeOfString:@"="];
            NSString *val = [[rawLine substringFromIndex:eq.location + 1] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
            if (val.length == 0 || ![fm fileExistsAtPath:[basePath stringByAppendingPathComponent:val]]) {
                [outLines addObject:[NSString stringWithFormat:@"Motif = %@", fallbackMotif]];
                changed = YES; continue;
            }
        } else if ([trim hasPrefix:@"System"] && [trim containsString:@"="] && ![trim hasPrefix:@"System."]) {
            NSRange eq = [rawLine rangeOfString:@"="];
            NSString *key = [[rawLine substringToIndex:eq.location] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceCharacterSet]];
            if ([key isEqualToString:@"System"]) {
                [outLines addObject:@"System = external/script/main.lua"];
                changed = YES; continue;
            }
        } else if ([trim hasPrefix:@"RenderMode"] && [trim containsString:@"="]) {
            [outLines addObject:@"RenderMode = Vulkan 1.3"];
            changed = YES; continue;
        } else if ([trim hasPrefix:@"BootLoadingMode"] && [trim containsString:@"="]) {
            [outLines addObject:@"BootLoadingMode = 0"];
            changed = YES; continue;
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

    BOOL hasChars  = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"chars"]];
    BOOL hasData   = [fm fileExistsAtPath:[basePath stringByAppendingPathComponent:@"data"]];
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
    } else {
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
                NSString *tmpChars = [tmpDir stringByAppendingPathComponent:@"chars"];
                NSString *dstChars = [basePath stringByAppendingPathComponent:@"chars"];
                for (NSString *ch in [fm contentsOfDirectoryAtPath:tmpChars error:nil]) {
                    if ([ch hasPrefix:@"."]) continue;
                    NSString *dstCh = [dstChars stringByAppendingPathComponent:ch];
                    if (![fm fileExistsAtPath:dstCh]) {
                        [self copyItemOverwriteFrom:[tmpChars stringByAppendingPathComponent:ch] to:dstCh];
                    }
                }
                [@"ok" writeToFile:[basePath stringByAppendingPathComponent:kCoreSyncMarker] atomically:YES encoding:NSUTF8StringEncoding error:nil];
            }
            [fm removeItemAtPath:tmpDir error:nil];
        }
    }

    [self processAutoImportAtBasePath:basePath];
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
        : @"Dang quet nhan vat / map / nhac & khoi dong...";

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSString *errText = nil;
        BOOL ok = [self syncEngineCoreAtBasePath:basePath forceFullReset:forceReset errorOut:&errText];
        dispatch_async(dispatch_get_main_queue(), ^{
            if (!ok) {
                [self showEngineErrorOverlay:(errText ?: @"Loi chuan bi du lieu.")];
                return;
            }
            self.bootStatusLabel.text = @"Dang khoi dong do hoa Vulkan...";
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.5 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
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

    NSString *displayMsg = message ?: @"Khong co chi tiet loi.";
    if (displayMsg.length > 5000) {
        displayMsg = [@"...(da cat bot log cu)...\\n" stringByAppendingString:[displayMsg substringFromIndex:displayMsg.length - 5000]];
    }

    UIView *overlay = [[UIView alloc] initWithFrame:self.view.bounds];
    overlay.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    overlay.backgroundColor = [UIColor colorWithWhite:0.05 alpha:0.95];

    UILabel *title = [[UILabel alloc] initWithFrame:CGRectMake(20, 22, overlay.bounds.size.width - 40, 28)];
    title.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    title.text = @"Ikemen GO da dung (Log moi nhat)";
    title.textColor = [UIColor colorWithRed:1.0 green:0.35 blue:0.35 alpha:1.0];
    title.font = [UIFont boldSystemFontOfSize:17];
    title.textAlignment = NSTextAlignmentCenter;
    [overlay addSubview:title];

    UITextView *tv = [[UITextView alloc] initWithFrame:CGRectMake(20, 56, overlay.bounds.size.width - 40, overlay.bounds.size.height - 124)];
    tv.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    tv.backgroundColor = [UIColor colorWithWhite:0.12 alpha:1.0];
    tv.textColor = [UIColor whiteColor];
    tv.font = [UIFont fontWithName:@"Menlo" size:12] ?: [UIFont systemFontOfSize:12];
    tv.editable = NO;
    tv.layer.cornerRadius = 10;
    tv.text = displayMsg;
    [overlay addSubview:tv];

    CGFloat btnY = overlay.bounds.size.height - 54;
    CGFloat w3 = (overlay.bounds.size.width - 60) / 3.0;

    UIButton *retryBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    retryBtn.frame = CGRectMake(20, btnY, w3, 40);
    retryBtn.autoresizingMask = UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleRightMargin;
    [retryBtn setTitle:@"Chay lai" forState:UIControlStateNormal];
    [retryBtn setTitleColor:UIColor.blackColor forState:UIControlStateNormal];
    retryBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    retryBtn.backgroundColor = [UIColor colorWithRed:0.25 green:0.88 blue:0.45 alpha:1.0];
    retryBtn.layer.cornerRadius = 8;
    [retryBtn addTarget:self action:@selector(onTapRetry) forControlEvents:UIControlEventTouchUpInside];
    [overlay addSubview:retryBtn];

    UIButton *fixCfgBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    fixCfgBtn.frame = CGRectMake(30 + w3, btnY, w3, 40);
    fixCfgBtn.autoresizingMask = UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleWidth;
    [fixCfgBtn setTitle:@"Xoa config.ini" forState:UIControlStateNormal];
    [fixCfgBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    fixCfgBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    fixCfgBtn.backgroundColor = [UIColor colorWithRed:0.15 green:0.50 blue:0.90 alpha:1.0];
    fixCfgBtn.layer.cornerRadius = 8;
    [fixCfgBtn addTarget:self action:@selector(onTapResetConfig) forControlEvents:UIControlEventTouchUpInside];
    [overlay addSubview:fixCfgBtn];

    UIButton *resetAllBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    resetAllBtn.frame = CGRectMake(40 + w3 * 2.0, btnY, w3, 40);
    resetAllBtn.autoresizingMask = UIViewAutoresizingFlexibleTopMargin | UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleLeftMargin;
    [resetAllBtn setTitle:@"Nap mac dinh" forState:UIControlStateNormal];
    [resetAllBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    resetAllBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    resetAllBtn.backgroundColor = [UIColor colorWithRed:0.80 green:0.25 blue:0.25 alpha:1.0];
    resetAllBtn.layer.cornerRadius = 8;
    [resetAllBtn addTarget:self action:@selector(onTapResetDefaultAssets) forControlEvents:UIControlEventTouchUpInside];
    [overlay addSubview:resetAllBtn];

    self.errorOverlayView = overlay;
    [self.view addSubview:overlay];
    if (tv.text.length > 1) {
        [tv scrollRangeToVisible:NSMakeRange(tv.text.length - 1, 1)];
    }
}

- (void)onTapRetry {
    [self prepareDocumentsAndRunForceReset:NO];
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
print("==> Replaced ViewController.m (Auto-Import + Tail Log)")

# 6. An dong trang thai boot (tag 9991) khi MetalContainerView gan xong
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