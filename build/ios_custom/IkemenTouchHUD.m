#import <UIKit/UIKit.h>
#import <math.h>
#if __has_include(<SDL2/SDL.h>)
#import <SDL2/SDL.h>
#else
#import "SDL.h"
#endif

static NSString *const kHUDPrefix = @"IkemenCustomHUD_v1_";

static void IkemenSendSDLKey(SDL_Keycode key, BOOL isDown) {
    SDL_Event ev;
    SDL_zero(ev);
    ev.type = isDown ? SDL_KEYDOWN : SDL_KEYUP;
    ev.key.state = isDown ? SDL_PRESSED : SDL_RELEASED;
    ev.key.repeat = 0;
    ev.key.keysym.sym = key;
    ev.key.keysym.scancode = SDL_GetScancodeFromKey(key);
    ev.key.keysym.mod = KMOD_NONE;
    SDL_PushEvent(&ev);
}

@protocol IkemenHUDControl <NSObject>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
- (void)releaseAllKeys;
@end

@interface IkemenJoystickView : UIView <IkemenHUDControl>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
@property (nonatomic, strong) UIView *knobView;
@property (nonatomic, strong) UITouch *activeTouch;
@property (nonatomic, assign) BOOL heldUp;
@property (nonatomic, assign) BOOL heldDown;
@property (nonatomic, assign) BOOL heldLeft;
@property (nonatomic, assign) BOOL heldRight;
@end

@implementation IkemenJoystickView

- (instancetype)initWithBaseSize:(CGFloat)size {
    self = [super initWithFrame:CGRectMake(0, 0, size, size)];
    if (self) {
        self.controlID = @"joystick";
        self.multipleTouchEnabled = YES;
        self.exclusiveTouch = NO;
        self.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.45];
        self.layer.cornerRadius = size * 0.5;
        self.layer.borderWidth = 2.0;
        self.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.65].CGColor;

        CGFloat knobSize = size * 0.42;
        self.knobView = [[UIView alloc] initWithFrame:CGRectMake(0, 0, knobSize, knobSize)];
        self.knobView.center = CGPointMake(size * 0.5, size * 0.5);
        self.knobView.backgroundColor = [UIColor colorWithWhite:1.0 alpha:0.85];
        self.knobView.layer.cornerRadius = knobSize * 0.5;
        self.knobView.userInteractionEnabled = NO;
        [self addSubview:self.knobView];
    }
    return self;
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    self.layer.borderColor = editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : [UIColor colorWithWhite:1.0 alpha:0.65].CGColor;
}

- (void)applyDirectionUp:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    if (u != self.heldUp)    { self.heldUp = u;    IkemenSendSDLKey(SDLK_UP, u); }
    if (d != self.heldDown)  { self.heldDown = d;  IkemenSendSDLKey(SDLK_DOWN, d); }
    if (l != self.heldLeft)  { self.heldLeft = l;  IkemenSendSDLKey(SDLK_LEFT, l); }
    if (r != self.heldRight) { self.heldRight = r; IkemenSendSDLKey(SDLK_RIGHT, r); }
}

- (void)releaseAllKeys {
    self.activeTouch = nil;
    self.knobView.center = CGPointMake(self.bounds.size.width * 0.5, self.bounds.size.height * 0.5);
    [self applyDirectionUp:NO down:NO left:NO right:NO];
}

- (void)updateWithLocalPoint:(CGPoint)pt {
    CGPoint c = CGPointMake(self.bounds.size.width * 0.5, self.bounds.size.height * 0.5);
    CGFloat dx = pt.x - c.x;
    CGFloat dy = pt.y - c.y;
    CGFloat dist = hypot(dx, dy);
    CGFloat maxR = self.bounds.size.width * 0.34;
    CGFloat deadzone = maxR * 0.22;

    if (dist > maxR && dist > 0.001) {
        self.knobView.center = CGPointMake(c.x + (dx / dist) * maxR, c.y + (dy / dist) * maxR);
    } else {
        self.knobView.center = pt;
    }

    if (dist < deadzone) {
        [self applyDirectionUp:NO down:NO left:NO right:NO];
        return;
    }

    double deg = atan2(dy, dx) * (180.0 / M_PI);
    BOOL right = (deg > -67.5 && deg < 67.5);
    BOOL left  = (deg > 112.5 || deg < -112.5);
    BOOL down  = (deg > 22.5  && deg < 157.5);
    BOOL up    = (deg < -22.5 && deg > -157.5);
    [self applyDirectionUp:up down:down left:left right:right];
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    UITouch *t = touches.anyObject;
    if (!t) return;
    self.activeTouch = t;
    if (!self.editMode) [self updateWithLocalPoint:[t locationInView:self]];
}

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (![touches containsObject:self.activeTouch]) return;
    if (self.editMode) {
        CGPoint p = [self.activeTouch locationInView:self.superview];
        CGPoint prev = [self.activeTouch previousLocationInView:self.superview];
        CGPoint nc = CGPointMake(self.center.x + (p.x - prev.x), self.center.y + (p.y - prev.y));
        self.center = nc;
        if (self.onMoved) self.onMoved(self.controlID, nc);
    } else {
        [self updateWithLocalPoint:[self.activeTouch locationInView:self]];
    }
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if ([touches containsObject:self.activeTouch]) {
        if (!self.editMode) [self releaseAllKeys];
        else self.activeTouch = nil;
    }
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if ([touches containsObject:self.activeTouch]) [self releaseAllKeys];
}

@end

@interface IkemenActionButton : UIView <IkemenHUDControl>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
@property (nonatomic, assign) SDL_Keycode keycode;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UIColor *tintAccent;
@property (nonatomic, strong) NSMutableSet<UITouch *> *activeTouches;
@property (nonatomic, strong) UITouch *dragTouch;
@end

@implementation IkemenActionButton

- (instancetype)initWithID:(NSString *)cid
                     title:(NSString *)title
                   keycode:(SDL_Keycode)key
                      size:(CGSize)size
                    accent:(UIColor *)accent {
    self = [super initWithFrame:CGRectMake(0, 0, size.width, size.height)];
    if (self) {
        self.controlID = cid;
        self.keycode = key;
        self.tintAccent = accent;
        self.activeTouches = [NSMutableSet set];
        self.multipleTouchEnabled = YES;
        self.exclusiveTouch = NO;

        self.backgroundColor = [accent colorWithAlphaComponent:0.42];
        self.layer.cornerRadius = MIN(size.width, size.height) * 0.5;
        self.layer.borderWidth = 1.8;
        self.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.75].CGColor;

        self.titleLabel = [[UILabel alloc] initWithFrame:self.bounds];
        self.titleLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        self.titleLabel.text = title;
        self.titleLabel.textAlignment = NSTextAlignmentCenter;
        self.titleLabel.textColor = UIColor.whiteColor;
        self.titleLabel.font = [UIFont boldSystemFontOfSize:(size.height > 40 ? 18 : 12)];
        self.titleLabel.userInteractionEnabled = NO;
        [self addSubview:self.titleLabel];
    }
    return self;
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    self.layer.borderColor = editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : [UIColor colorWithWhite:1.0 alpha:0.75].CGColor;
}

- (void)setHighlightedState:(BOOL)pressed {
    self.backgroundColor = [self.tintAccent colorWithAlphaComponent:(pressed ? 0.85 : 0.42)];
}

- (void)releaseAllKeys {
    if (self.activeTouches.count > 0) {
        [self.activeTouches removeAllObjects];
        IkemenSendSDLKey(self.keycode, NO);
        [self setHighlightedState:NO];
    }
    self.dragTouch = nil;
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.editMode) {
        self.dragTouch = touches.anyObject;
        return;
    }
    BOOL wasEmpty = (self.activeTouches.count == 0);
    [self.activeTouches unionSet:touches];
    if (wasEmpty && self.activeTouches.count > 0) {
        IkemenSendSDLKey(self.keycode, YES);
        [self setHighlightedState:YES];
    }
}

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.editMode && [touches containsObject:self.dragTouch]) {
        CGPoint p = [self.dragTouch locationInView:self.superview];
        CGPoint prev = [self.dragTouch previousLocationInView:self.superview];
        CGPoint nc = CGPointMake(self.center.x + (p.x - prev.x), self.center.y + (p.y - prev.y));
        self.center = nc;
        if (self.onMoved) self.onMoved(self.controlID, nc);
    }
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.editMode) {
        if ([touches containsObject:self.dragTouch]) self.dragTouch = nil;
        return;
    }
    [self.activeTouches minusSet:touches];
    if (self.activeTouches.count == 0) {
        IkemenSendSDLKey(self.keycode, NO);
        [self setHighlightedState:NO];
    }
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self touchesEnded:touches withEvent:event];
}

@end

@interface IkemenTouchHUD : UIView
@property (nonatomic, strong) NSMutableArray<UIView<IkemenHUDControl> *> *controls;
@property (nonatomic, strong) UIButton *gearButton;
@property (nonatomic, strong) UIView *editorPanel;
@property (nonatomic, strong) UISlider *opacitySlider;
@property (nonatomic, strong) UISlider *scaleSlider;
@property (nonatomic, strong) UILabel *opacityLabel;
@property (nonatomic, strong) UILabel *scaleLabel;
@property (nonatomic, strong) UIButton *toggleExtraBtn;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGFloat hudOpacity;
@property (nonatomic, assign) CGFloat hudScale;
@property (nonatomic, assign) BOOL showExtraButtons;
@property (nonatomic, assign) CGSize lastLayoutSize;
+ (void)attachToKeyWindow;
@end

@implementation IkemenTouchHUD

static IkemenTouchHUD *sSharedHUD = nil;

+ (UIWindow *)findActiveWindow {
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if ([scene isKindOfClass:[UIWindowScene class]]) {
            UIWindowScene *ws = (UIWindowScene *)scene;
            for (UIWindow *w in ws.windows) {
                if (w.isKeyWindow) return w;
            }
            if (ws.windows.firstObject) return ws.windows.firstObject;
        }
    }
    return nil;
}

+ (void)attachToKeyWindow {
    dispatch_async(dispatch_get_main_queue(), ^{
        UIWindow *win = [self findActiveWindow];
        if (!win) {
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.5 * NSEC_PER_SEC)),
                           dispatch_get_main_queue(), ^{
                [self attachToKeyWindow];
            });
            return;
        }
        if (sSharedHUD && sSharedHUD.superview == win) {
            [win bringSubviewToFront:sSharedHUD];
            return;
        }
        if (sSharedHUD) [sSharedHUD removeFromSuperview];
        sSharedHUD = [[IkemenTouchHUD alloc] initWithFrame:win.bounds];
        sSharedHUD.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
        [win addSubview:sSharedHUD];
        [win bringSubviewToFront:sSharedHUD];

        static dispatch_once_t obsOnce;
        dispatch_once(&obsOnce, ^{
            [NSNotificationCenter.defaultCenter addObserverForName:UIWindowDidBecomeKeyNotification
                                                            object:nil
                                                             queue:NSOperationQueue.mainQueue
                                                        usingBlock:^(NSNotification *note) {
                if (sSharedHUD && sSharedHUD.superview) {
                    [sSharedHUD.superview bringSubviewToFront:sSharedHUD];
                }
            }];
        });
    });
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.backgroundColor = UIColor.clearColor;
        self.multipleTouchEnabled = YES;
        self.controls = [NSMutableArray array];

        NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
        self.hudOpacity = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"opacity"]]
            ? [ud floatForKey:[kHUDPrefix stringByAppendingString:@"opacity"]] : 0.55f;
        self.hudScale = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"scale"]]
            ? [ud floatForKey:[kHUDPrefix stringByAppendingString:@"scale"]] : 1.0f;
        self.showExtraButtons = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"showDW"]]
            ? [ud boolForKey:[kHUDPrefix stringByAppendingString:@"showDW"]] : YES;

        [self buildControls];
        [self buildEditorUI];
        [self applyVisualSettings];
    }
    return self;
}

- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    UIView *hit = [super hitTest:point withEvent:event];
    return (hit == self) ? nil : hit;
}

- (void)registerControl:(UIView<IkemenHUDControl> *)ctrl defaultNorm:(CGPoint)norm {
    ctrl.defaultNormCenter = norm;
    __weak typeof(self) weakSelf = self;
    ctrl.onMoved = ^(NSString *cid, CGPoint c) {
        __strong typeof(weakSelf) s = weakSelf;
        if (!s || s.bounds.size.width < 1 || s.bounds.size.height < 1) return;
        CGFloat nx = MAX((CGFloat)0.04, MIN((CGFloat)0.96, c.x / s.bounds.size.width));
        CGFloat ny = MAX((CGFloat)0.06, MIN((CGFloat)0.94, c.y / s.bounds.size.height));
        NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
        [ud setFloat:(float)nx forKey:[NSString stringWithFormat:@"%@pos_%@_x", kHUDPrefix, cid]];
        [ud setFloat:(float)ny forKey:[NSString stringWithFormat:@"%@pos_%@_y", kHUDPrefix, cid]];
    };
    [self.controls addObject:ctrl];
    [self addSubview:ctrl];
}

- (void)buildControls {
    IkemenJoystickView *joy = [[IkemenJoystickView alloc] initWithBaseSize:136.0];
    [self registerControl:joy defaultNorm:CGPointMake(0.14, 0.72)];

    CGSize btnSz = CGSizeMake(56, 56);
    UIColor *punchCol = [UIColor colorWithRed:0.15 green:0.55 blue:0.95 alpha:1.0];
    UIColor *kickCol  = [UIColor colorWithRed:0.90 green:0.28 blue:0.28 alpha:1.0];
    UIColor *extraCol = [UIColor colorWithRed:0.62 green:0.35 blue:0.90 alpha:1.0];
    UIColor *sysCol   = [UIColor colorWithWhite:0.25 alpha:1.0];

    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_x" title:@"X" keycode:SDLK_a size:btnSz accent:punchCol]
              defaultNorm:CGPointMake(0.73, 0.60)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_y" title:@"Y" keycode:SDLK_s size:btnSz accent:punchCol]
              defaultNorm:CGPointMake(0.82, 0.54)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_z" title:@"Z" keycode:SDLK_d size:btnSz accent:punchCol]
              defaultNorm:CGPointMake(0.91, 0.58)];

    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_a" title:@"A" keycode:SDLK_z size:btnSz accent:kickCol]
              defaultNorm:CGPointMake(0.71, 0.80)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_b" title:@"B" keycode:SDLK_x size:btnSz accent:kickCol]
              defaultNorm:CGPointMake(0.80, 0.74)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_c" title:@"C" keycode:SDLK_c size:btnSz accent:kickCol]
              defaultNorm:CGPointMake(0.89, 0.78)];

    CGSize extraSz = CGSizeMake(46, 46);
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_d" title:@"D" keycode:SDLK_q size:extraSz accent:extraCol]
              defaultNorm:CGPointMake(0.77, 0.37)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_w" title:@"W" keycode:SDLK_w size:extraSz accent:extraCol]
              defaultNorm:CGPointMake(0.86, 0.35)];

    CGSize sysSz = CGSizeMake(62, 30);
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_menu" title:@"MENU" keycode:SDLK_ESCAPE size:sysSz accent:sysCol]
              defaultNorm:CGPointMake(0.08, 0.11)];
    [self registerControl:[[IkemenActionButton alloc] initWithID:@"btn_start" title:@"START" keycode:SDLK_RETURN size:sysSz accent:sysCol]
              defaultNorm:CGPointMake(0.92, 0.11)];
}

- (void)buildEditorUI {
    self.gearButton = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.gearButton setTitle:@"HUD" forState:UIControlStateNormal];
    self.gearButton.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    [self.gearButton setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    self.gearButton.backgroundColor = [UIColor colorWithWhite:0.15 alpha:0.65];
    self.gearButton.layer.cornerRadius = 14;
    self.gearButton.layer.borderWidth = 1.0;
    self.gearButton.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.5].CGColor;
    [self.gearButton addTarget:self action:@selector(toggleEditMode) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.gearButton];

    self.editorPanel = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 320, 152)];
    self.editorPanel.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.90];
    self.editorPanel.layer.cornerRadius = 14;
    self.editorPanel.layer.borderWidth = 1.2;
    self.editorPanel.layer.borderColor = [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:0.9].CGColor;
    self.editorPanel.hidden = YES;

    UILabel *hint = [[UILabel alloc] initWithFrame:CGRectMake(12, 8, 296, 18)];
    hint.text = @"Keo tung nut de doi vi tri";
    hint.textColor = [UIColor colorWithRed:1.0 green:0.85 blue:0.2 alpha:1.0];
    hint.font = [UIFont boldSystemFontOfSize:13];
    hint.textAlignment = NSTextAlignmentCenter;
    [self.editorPanel addSubview:hint];

    self.opacityLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 34, 110, 22)];
    self.opacityLabel.textColor = UIColor.whiteColor;
    self.opacityLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.opacityLabel];

    self.opacitySlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 32, 182, 26)];
    self.opacitySlider.minimumValue = 0.15f;
    self.opacitySlider.maximumValue = 1.0f;
    self.opacitySlider.value = self.hudOpacity;
    [self.opacitySlider addTarget:self action:@selector(onOpacityChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.opacitySlider];

    self.scaleLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 68, 110, 22)];
    self.scaleLabel.textColor = UIColor.whiteColor;
    self.scaleLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.scaleLabel];

    self.scaleSlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 66, 182, 26)];
    self.scaleSlider.minimumValue = 0.70f;
    self.scaleSlider.maximumValue = 1.35f;
    self.scaleSlider.value = self.hudScale;
    [self.scaleSlider addTarget:self action:@selector(onScaleChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.scaleSlider];

    self.toggleExtraBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    self.toggleExtraBtn.frame = CGRectMake(12, 106, 102, 34);
    self.toggleExtraBtn.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    [self.toggleExtraBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    self.toggleExtraBtn.backgroundColor = [UIColor colorWithRed:0.45 green:0.25 blue:0.75 alpha:0.9];
    self.toggleExtraBtn.layer.cornerRadius = 8;
    [self.toggleExtraBtn addTarget:self action:@selector(onToggleDW) forControlEvents:UIControlEventTouchUpInside];
    [self.editorPanel addSubview:self.toggleExtraBtn];

    UIButton *resetBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    resetBtn.frame = CGRectMake(122, 106, 86, 34);
    [resetBtn setTitle:@"Reset" forState:UIControlStateNormal];
    resetBtn.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    [resetBtn setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    resetBtn.backgroundColor = [UIColor colorWithRed:0.75 green:0.22 blue:0.22 alpha:0.9];
    resetBtn.layer.cornerRadius = 8;
    [resetBtn addTarget:self action:@selector(onResetLayout) forControlEvents:UIControlEventTouchUpInside];
    [self.editorPanel addSubview:resetBtn];

    UIButton *doneBtn = [UIButton buttonWithType:UIButtonTypeSystem];
    doneBtn.frame = CGRectMake(216, 106, 92, 34);
    [doneBtn setTitle:@"Xong" forState:UIControlStateNormal];
    doneBtn.titleLabel.font = [UIFont boldSystemFontOfSize:13];
    [doneBtn setTitleColor:UIColor.blackColor forState:UIControlStateNormal];
    doneBtn.backgroundColor = [UIColor colorWithRed:0.25 green:0.88 blue:0.45 alpha:1.0];
    doneBtn.layer.cornerRadius = 8;
    [doneBtn addTarget:self action:@selector(toggleEditMode) forControlEvents:UIControlEventTouchUpInside];
    [self.editorPanel addSubview:doneBtn];

    [self addSubview:self.editorPanel];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    if (CGSizeEqualToSize(self.bounds.size, self.lastLayoutSize)) return;
    self.lastLayoutSize = self.bounds.size;

    CGFloat w = self.bounds.size.width;
    CGFloat h = self.bounds.size.height;
    self.gearButton.frame = CGRectMake(w * 0.78 - 28, h * 0.11 - 14, 56, 28);
    self.editorPanel.center = CGPointMake(w * 0.5, MAX((CGFloat)95.0, h * 0.28));

    NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        NSString *kx = [NSString stringWithFormat:@"%@pos_%@_x", kHUDPrefix, ctrl.controlID];
        NSString *ky = [NSString stringWithFormat:@"%@pos_%@_y", kHUDPrefix, ctrl.controlID];
        CGFloat nx = [ud objectForKey:kx] ? [ud floatForKey:kx] : ctrl.defaultNormCenter.x;
        CGFloat ny = [ud objectForKey:ky] ? [ud floatForKey:ky] : ctrl.defaultNormCenter.y;
        ctrl.center = CGPointMake(w * nx, h * ny);
    }
}

- (void)applyVisualSettings {
    self.opacityLabel.text = [NSString stringWithFormat:@"Do mo: %d%%", (int)round(self.hudOpacity * 100)];
    self.scaleLabel.text   = [NSString stringWithFormat:@"Co nut: %d%%", (int)round(self.hudScale * 100)];
    [self.toggleExtraBtn setTitle:(self.showExtraButtons ? @"D/W: Bat" : @"D/W: Tat") forState:UIControlStateNormal];

    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        ctrl.alpha = self.editMode ? MAX((CGFloat)0.75, self.hudOpacity) : self.hudOpacity;
        ctrl.transform = CGAffineTransformMakeScale(self.hudScale, self.hudScale);
        if ([ctrl.controlID isEqualToString:@"btn_d"] || [ctrl.controlID isEqualToString:@"btn_w"]) {
            ctrl.hidden = !self.showExtraButtons;
        }
    }
    self.gearButton.alpha = self.editMode ? 1.0 : MAX((CGFloat)0.35, self.hudOpacity);
}

- (void)toggleEditMode {
    self.editMode = !self.editMode;
    self.editorPanel.hidden = !self.editMode;
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        ctrl.editMode = self.editMode;
    }
    [self applyVisualSettings];
}

- (void)onOpacityChanged:(UISlider *)slider {
    self.hudOpacity = slider.value;
    [NSUserDefaults.standardUserDefaults setFloat:self.hudOpacity forKey:[kHUDPrefix stringByAppendingString:@"opacity"]];
    [self applyVisualSettings];
}

- (void)onScaleChanged:(UISlider *)slider {
    self.hudScale = slider.value;
    [NSUserDefaults.standardUserDefaults setFloat:self.hudScale forKey:[kHUDPrefix stringByAppendingString:@"scale"]];
    [self applyVisualSettings];
}

- (void)onToggleDW {
    self.showExtraButtons = !self.showExtraButtons;
    [NSUserDefaults.standardUserDefaults setBool:self.showExtraButtons forKey:[kHUDPrefix stringByAppendingString:@"showDW"]];
    [self applyVisualSettings];
}

- (void)onResetLayout {
    NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        [ud removeObjectForKey:[NSString stringWithFormat:@"%@pos_%@_x", kHUDPrefix, ctrl.controlID]];
        [ud removeObjectForKey:[NSString stringWithFormat:@"%@pos_%@_y", kHUDPrefix, ctrl.controlID]];
    }
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"opacity"]];
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"scale"]];
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"showDW"]];
    self.hudOpacity = 0.55f;
    self.hudScale = 1.0f;
    self.showExtraButtons = YES;
    self.opacitySlider.value = self.hudOpacity;
    self.scaleSlider.value = self.hudScale;
    self.lastLayoutSize = CGSizeZero;
    [self setNeedsLayout];
    [self layoutIfNeeded];
    [self applyVisualSettings];
}

@end