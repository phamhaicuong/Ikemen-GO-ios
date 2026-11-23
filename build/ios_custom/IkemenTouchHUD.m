#import <UIKit/UIKit.h>
#import <math.h>
#if __has_include(<SDL2/SDL.h>)
#import <SDL2/SDL.h>
#else
#import "SDL.h"
#endif

static NSString *const kHUDPrefix = @"IkemenCustomHUD_v2_";
static const uint8_t kDirSrcJoy  = (1 << 0);
static const uint8_t kDirSrcDpad = (1 << 1);

static void IkemenSendSDLKey(SDL_Keycode key, BOOL isDown) {
    if (SDL_WasInit(SDL_INIT_EVENTS) == 0) return;
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

#pragma mark - PPSSPP-Style 4-Arrow 8-Way D-Pad

@interface IkemenDPadView : UIView <IkemenHUDControl>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
@property (nonatomic, copy) void (^onDirectionChanged)(BOOL up, BOOL down, BOOL left, BOOL right);
@property (nonatomic, strong) UILabel *upArrow;
@property (nonatomic, strong) UILabel *downArrow;
@property (nonatomic, strong) UILabel *leftArrow;
@property (nonatomic, strong) UILabel *rightArrow;
@property (nonatomic, strong) UIView *centerHub;
@property (nonatomic, strong) UITouch *activeTouch;
@property (nonatomic, assign) BOOL heldUp;
@property (nonatomic, assign) BOOL heldDown;
@property (nonatomic, assign) BOOL heldLeft;
@property (nonatomic, assign) BOOL heldRight;
@end

@implementation IkemenDPadView

- (UILabel *)makeArrowPadWithSymbol:(NSString *)sym frame:(CGRect)f {
    UILabel *lbl = [[UILabel alloc] initWithFrame:f];
    lbl.text = sym;
    lbl.textAlignment = NSTextAlignmentCenter;
    lbl.textColor = [UIColor colorWithWhite:1.0 alpha:0.92];
    lbl.font = [UIFont boldSystemFontOfSize:20];
    lbl.backgroundColor = [UIColor colorWithWhite:0.10 alpha:0.55];
    lbl.layer.cornerRadius = 10.0;
    lbl.layer.borderWidth = 1.6;
    lbl.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.70].CGColor;
    lbl.clipsToBounds = YES;
    lbl.userInteractionEnabled = NO;
    return lbl;
}

- (instancetype)initWithBaseSize:(CGFloat)size {
    self = [super initWithFrame:CGRectMake(0, 0, size, size)];
    if (self) {
        self.controlID = @"dpad";
        self.multipleTouchEnabled = YES;
        self.exclusiveTouch = NO;
        self.backgroundColor = UIColor.clearColor;

        CGFloat armW = size * 0.32;
        CGFloat armL = size * 0.34;
        CGFloat mid = (size - armW) * 0.5;

        self.upArrow    = [self makeArrowPadWithSymbol:@"\u25B2" frame:CGRectMake(mid, 2, armW, armL)];
        self.downArrow  = [self makeArrowPadWithSymbol:@"\u25BC" frame:CGRectMake(mid, size - armL - 2, armW, armL)];
        self.leftArrow  = [self makeArrowPadWithSymbol:@"\u25C0" frame:CGRectMake(2, mid, armL, armW)];
        self.rightArrow = [self makeArrowPadWithSymbol:@"\u25B6" frame:CGRectMake(size - armL - 2, mid, armL, armW)];

        CGFloat hubSz = armW * 0.72;
        self.centerHub = [[UIView alloc] initWithFrame:CGRectMake((size - hubSz) * 0.5, (size - hubSz) * 0.5, hubSz, hubSz)];
        self.centerHub.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.42];
        self.centerHub.layer.cornerRadius = hubSz * 0.5;
        self.centerHub.layer.borderWidth = 1.0;
        self.centerHub.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.35].CGColor;
        self.centerHub.userInteractionEnabled = NO;

        [self addSubview:self.centerHub];
        [self addSubview:self.upArrow];
        [self addSubview:self.downArrow];
        [self addSubview:self.leftArrow];
        [self addSubview:self.rightArrow];
    }
    return self;
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    CGColorRef border = editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : [UIColor colorWithWhite:1.0 alpha:0.70].CGColor;
    self.upArrow.layer.borderColor = border;
    self.downArrow.layer.borderColor = border;
    self.leftArrow.layer.borderColor = border;
    self.rightArrow.layer.borderColor = border;
}

- (void)stylePad:(UILabel *)pad active:(BOOL)active {
    pad.backgroundColor = active
        ? [UIColor colorWithRed:0.18 green:0.62 blue:1.0 alpha:0.88]
        : [UIColor colorWithWhite:0.10 alpha:0.55];
}

- (void)applyDirectionUp:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    if (u == self.heldUp && d == self.heldDown && l == self.heldLeft && r == self.heldRight) return;
    self.heldUp = u;
    self.heldDown = d;
    self.heldLeft = l;
    self.heldRight = r;
    [self stylePad:self.upArrow active:u];
    [self stylePad:self.downArrow active:d];
    [self stylePad:self.leftArrow active:l];
    [self stylePad:self.rightArrow active:r];
    if (self.onDirectionChanged) self.onDirectionChanged(u, d, l, r);
}

- (void)releaseAllKeys {
    self.activeTouch = nil;
    [self applyDirectionUp:NO down:NO left:NO right:NO];
}

- (void)updateWithLocalPoint:(CGPoint)pt {
    CGPoint c = CGPointMake(self.bounds.size.width * 0.5, self.bounds.size.height * 0.5);
    CGFloat dx = pt.x - c.x;
    CGFloat dy = pt.y - c.y;
    CGFloat dist = hypot(dx, dy);
    CGFloat radius = self.bounds.size.width * 0.5;
    CGFloat deadzone = radius * 0.17;

    if (dist < deadzone) {
        [self applyDirectionUp:NO down:NO left:NO right:NO];
        return;
    }

    // 8-way octagonal mapping (exact 45-degree sectors for crisp menu + fighting diagonals)
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

#pragma mark - 8-Way Circular Virtual Analog Joystick

@interface IkemenJoystickView : UIView <IkemenHUDControl>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
@property (nonatomic, copy) void (^onDirectionChanged)(BOOL up, BOOL down, BOOL left, BOOL right);
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
    if (u == self.heldUp && d == self.heldDown && l == self.heldLeft && r == self.heldRight) return;
    self.heldUp = u;
    self.heldDown = d;
    self.heldLeft = l;
    self.heldRight = r;
    if (self.onDirectionChanged) self.onDirectionChanged(u, d, l, r);
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

#pragma mark - Multi-Touch Sliding Action Button

@interface IkemenActionButton : UIView <IkemenHUDControl>
@property (nonatomic, copy) NSString *controlID;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGPoint defaultNormCenter;
@property (nonatomic, copy) void (^onMoved)(NSString *cid, CGPoint newCenter);
@property (nonatomic, assign) SDL_Keycode keycode;
@property (nonatomic, assign) BOOL isSystemButton;
@property (nonatomic, assign) BOOL pressedState;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UIColor *tintAccent;
@property (nonatomic, strong) UITouch *dragTouch;
- (void)setButtonPressed:(BOOL)pressed;
@end

@implementation IkemenActionButton

- (instancetype)initWithID:(NSString *)cid
                     title:(NSString *)title
                   keycode:(SDL_Keycode)key
                      size:(CGSize)size
                    accent:(UIColor *)accent
                  isSystem:(BOOL)isSys {
    self = [super initWithFrame:CGRectMake(0, 0, size.width, size.height)];
    if (self) {
        self.controlID = cid;
        self.keycode = key;
        self.tintAccent = accent;
        self.isSystemButton = isSys;
        self.multipleTouchEnabled = YES;
        self.exclusiveTouch = NO;
        // In play mode, container handles multi-touch sliding across buttons
        self.userInteractionEnabled = NO;

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
    self.userInteractionEnabled = editMode;
    self.layer.borderColor = editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : [UIColor colorWithWhite:1.0 alpha:0.75].CGColor;
}

- (void)setButtonPressed:(BOOL)pressed {
    if (self.pressedState == pressed) return;
    self.pressedState = pressed;
    self.backgroundColor = [self.tintAccent colorWithAlphaComponent:(pressed ? 0.88 : 0.42)];
    IkemenSendSDLKey(self.keycode, pressed);
}

- (void)releaseAllKeys {
    [self setButtonPressed:NO];
    self.dragTouch = nil;
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.editMode) self.dragTouch = touches.anyObject;
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
    if (self.editMode && [touches containsObject:self.dragTouch]) self.dragTouch = nil;
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    if (self.editMode && [touches containsObject:self.dragTouch]) self.dragTouch = nil;
}

@end

#pragma mark - Main HUD Overlay Container

@interface IkemenTouchHUD : UIView
@property (nonatomic, strong) NSMutableArray<UIView<IkemenHUDControl> *> *controls;
@property (nonatomic, strong) NSMutableArray<IkemenActionButton *> *actionButtons;
@property (nonatomic, strong) IkemenDPadView *dpadView;
@property (nonatomic, strong) IkemenJoystickView *joyView;
@property (nonatomic, strong) UIButton *gearButton;
@property (nonatomic, strong) UIView *editorPanel;
@property (nonatomic, strong) UISlider *opacitySlider;
@property (nonatomic, strong) UISlider *scaleSlider;
@property (nonatomic, strong) UILabel *opacityLabel;
@property (nonatomic, strong) UILabel *scaleLabel;
@property (nonatomic, strong) UIButton *toggleDpadBtn;
@property (nonatomic, strong) UIButton *toggleJoyBtn;
@property (nonatomic, strong) UIButton *toggleExtraBtn;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGFloat hudOpacity;
@property (nonatomic, assign) CGFloat hudScale;
@property (nonatomic, assign) BOOL showDpad;
@property (nonatomic, assign) BOOL showJoystick;
@property (nonatomic, assign) BOOL showExtraButtons;
@property (nonatomic, assign) uint8_t upMask;
@property (nonatomic, assign) uint8_t downMask;
@property (nonatomic, assign) uint8_t leftMask;
@property (nonatomic, assign) uint8_t rightMask;
@property (nonatomic, assign) CGSize lastLayoutSize;
@property (nonatomic, assign) UIEdgeInsets lastSafeInsets;
+ (void)attachToKeyWindow;
@end

@implementation IkemenTouchHUD

static IkemenTouchHUD *sSharedHUD = nil;

+ (void)attachToKeyWindow {
    // Mounted directly inside TouchOverlayViewController
}

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        self.backgroundColor = UIColor.clearColor;
        self.multipleTouchEnabled = YES;
        self.controls = [NSMutableArray array];
        self.actionButtons = [NSMutableArray array];

        NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
        self.hudOpacity = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"opacity"]]
            ? [ud floatForKey:[kHUDPrefix stringByAppendingString:@"opacity"]] : 0.58f;
        self.hudScale = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"scale"]]
            ? [ud floatForKey:[kHUDPrefix stringByAppendingString:@"scale"]] : 1.0f;
        self.showDpad = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"showDpad"]]
            ? [ud boolForKey:[kHUDPrefix stringByAppendingString:@"showDpad"]] : YES;
        self.showJoystick = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"showJoy"]]
            ? [ud boolForKey:[kHUDPrefix stringByAppendingString:@"showJoy"]] : YES;
        self.showExtraButtons = [ud objectForKey:[kHUDPrefix stringByAppendingString:@"showDW"]]
            ? [ud boolForKey:[kHUDPrefix stringByAppendingString:@"showDW"]] : YES;

        [self buildControls];
        [self buildEditorUI];
        [self applyVisualSettings];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(releaseAllInputs)
                                                     name:UIApplicationWillResignActiveNotification
                                                   object:nil];
        sSharedHUD = self;
    }
    return self;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)updateDirectionSource:(uint8_t)src up:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    BOOL oldU = (self.upMask != 0);
    BOOL oldD = (self.downMask != 0);
    BOOL oldL = (self.leftMask != 0);
    BOOL oldR = (self.rightMask != 0);

    if (u) self.upMask |= src;    else self.upMask &= ~src;
    if (d) self.downMask |= src;  else self.downMask &= ~src;
    if (l) self.leftMask |= src;  else self.leftMask &= ~src;
    if (r) self.rightMask |= src; else self.rightMask &= ~src;

    BOOL newU = (self.upMask != 0);
    BOOL newD = (self.downMask != 0);
    BOOL newL = (self.leftMask != 0);
    BOOL newR = (self.rightMask != 0);

    if (newU != oldU) IkemenSendSDLKey(SDLK_UP, newU);
    if (newD != oldD) IkemenSendSDLKey(SDLK_DOWN, newD);
    if (newL != oldL) IkemenSendSDLKey(SDLK_LEFT, newL);
    if (newR != oldR) IkemenSendSDLKey(SDLK_RIGHT, newR);
}

- (void)releaseAllInputs {
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        [ctrl releaseAllKeys];
    }
    [self updateDirectionSource:kDirSrcDpad up:NO down:NO left:NO right:NO];
    [self updateDirectionSource:kDirSrcJoy up:NO down:NO left:NO right:NO];
}

- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    if (self.editMode) {
        UIView *hit = [super hitTest:point withEvent:event];
        return (hit == self) ? nil : hit;
    }
    UIView *hit = [super hitTest:point withEvent:event];
    if (hit && hit != self) {
        return hit;
    }
    // Check if touch lands on or near any visible action button -> handle at container level for multi-touch sliding
    for (IkemenActionButton *btn in self.actionButtons) {
        if (btn.hidden) continue;
        CGFloat slop = btn.isSystemButton ? 2.0 : 8.0;
        if (CGRectContainsPoint(CGRectInset(btn.frame, -slop, -slop), point)) {
            return self;
        }
    }
    return nil;
}

- (void)processActionTouches:(NSSet<UITouch *> *)allTouches {
    if (self.editMode) return;
    NSMutableSet<IkemenActionButton *> *nowPressed = [NSMutableSet set];

    for (UITouch *t in allTouches) {
        if (t.view != self) continue;
        if (t.phase == UITouchPhaseBegan || t.phase == UITouchPhaseMoved || t.phase == UITouchPhaseStationary) {
            CGPoint loc = [t locationInView:self];
            CGRect fingerRect = CGRectMake(loc.x - 8.0, loc.y - 8.0, 16.0, 16.0);
            for (IkemenActionButton *btn in self.actionButtons) {
                if (btn.hidden) continue;
                CGFloat slop = btn.isSystemButton ? 0.0 : 4.0;
                CGRect hitFrame = CGRectInset(btn.frame, -slop, -slop);
                if (CGRectIntersectsRect(hitFrame, fingerRect)) {
                    [nowPressed addObject:btn];
                }
            }
        }
    }

    for (IkemenActionButton *btn in self.actionButtons) {
        [btn setButtonPressed:[nowPressed containsObject:btn]];
    }
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self processActionTouches:event.allTouches];
}

- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self processActionTouches:event.allTouches];
}

- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self processActionTouches:event.allTouches];
}

- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event {
    [self processActionTouches:event.allTouches];
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

- (void)addActionID:(NSString *)cid title:(NSString *)title key:(SDL_Keycode)key size:(CGSize)sz accent:(UIColor *)col isSys:(BOOL)isSys norm:(CGPoint)norm {
    IkemenActionButton *btn = [[IkemenActionButton alloc] initWithID:cid title:title keycode:key size:sz accent:col isSystem:isSys];
    [self.actionButtons addObject:btn];
    [self registerControl:btn defaultNorm:norm];
}

- (void)buildControls {
    __weak typeof(self) weakSelf = self;

    // 1. PPSSPP-style 4-Arrow 8-Way D-Pad (top-left)
    self.dpadView = [[IkemenDPadView alloc] initWithBaseSize:140.0];
    self.dpadView.onDirectionChanged = ^(BOOL u, BOOL d, BOOL l, BOOL r) {
        [weakSelf updateDirectionSource:kDirSrcDpad up:u down:d left:l right:r];
    };
    [self registerControl:self.dpadView defaultNorm:CGPointMake(0.14, 0.45)];

    // 2. 8-Way Circular Analog Joystick (bottom-left, below D-Pad like PPSSPP)
    self.joyView = [[IkemenJoystickView alloc] initWithBaseSize:118.0];
    self.joyView.onDirectionChanged = ^(BOOL u, BOOL d, BOOL l, BOOL r) {
        [weakSelf updateDirectionSource:kDirSrcJoy up:u down:d left:l right:r];
    };
    [self registerControl:self.joyView defaultNorm:CGPointMake(0.14, 0.78)];

    // 3. Standard Ikemen GO 6 Fighting Buttons + 2 Anime/Macro Buttons (D, W)
    CGSize btnSz = CGSizeMake(56, 56);
    UIColor *punchCol = [UIColor colorWithRed:0.15 green:0.55 blue:0.95 alpha:1.0];
    UIColor *kickCol  = [UIColor colorWithRed:0.90 green:0.28 blue:0.28 alpha:1.0];
    UIColor *extraCol = [UIColor colorWithRed:0.62 green:0.35 blue:0.90 alpha:1.0];
    UIColor *sysCol   = [UIColor colorWithWhite:0.25 alpha:1.0];

    [self addActionID:@"btn_x" title:@"X" key:SDLK_a size:btnSz accent:punchCol isSys:NO norm:CGPointMake(0.73, 0.58)];
    [self addActionID:@"btn_y" title:@"Y" key:SDLK_s size:btnSz accent:punchCol isSys:NO norm:CGPointMake(0.82, 0.52)];
    [self addActionID:@"btn_z" title:@"Z" key:SDLK_d size:btnSz accent:punchCol isSys:NO norm:CGPointMake(0.91, 0.56)];

    [self addActionID:@"btn_a" title:@"A" key:SDLK_z size:btnSz accent:kickCol isSys:NO norm:CGPointMake(0.71, 0.78)];
    [self addActionID:@"btn_b" title:@"B" key:SDLK_x size:btnSz accent:kickCol isSys:NO norm:CGPointMake(0.80, 0.72)];
    [self addActionID:@"btn_c" title:@"C" key:SDLK_c size:btnSz accent:kickCol isSys:NO norm:CGPointMake(0.89, 0.76)];

    CGSize extraSz = CGSizeMake(46, 46);
    [self addActionID:@"btn_d" title:@"D" key:SDLK_q size:extraSz accent:extraCol isSys:NO norm:CGPointMake(0.77, 0.34)];
    [self addActionID:@"btn_w" title:@"W" key:SDLK_w size:extraSz accent:extraCol isSys:NO norm:CGPointMake(0.86, 0.32)];

    // 4. Official System Buttons: MENU (SDLK_TAB -> m: Pause/Back, never quits app) & START (SDLK_RETURN -> s)
    CGSize sysSz = CGSizeMake(62, 30);
    [self addActionID:@"btn_menu"  title:@"MENU"  key:SDLK_TAB    size:sysSz accent:sysCol isSys:YES norm:CGPointMake(0.40, 0.09)];
    [self addActionID:@"btn_start" title:@"START" key:SDLK_RETURN size:sysSz accent:sysCol isSys:YES norm:CGPointMake(0.60, 0.09)];
}

- (UIButton *)makePanelButton:(NSString *)title frame:(CGRect)f color:(UIColor *)bg action:(SEL)sel {
    UIButton *b = [UIButton buttonWithType:UIButtonTypeSystem];
    b.frame = f;
    [b setTitle:title forState:UIControlStateNormal];
    b.titleLabel.font = [UIFont boldSystemFontOfSize:12];
    [b setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    b.backgroundColor = bg;
    b.layer.cornerRadius = 8;
    [b addTarget:self action:sel forControlEvents:UIControlEventTouchUpInside];
    return b;
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

    self.editorPanel = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 336, 194)];
    self.editorPanel.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.92];
    self.editorPanel.layer.cornerRadius = 14;
    self.editorPanel.layer.borderWidth = 1.2;
    self.editorPanel.layer.borderColor = [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:0.9].CGColor;
    self.editorPanel.hidden = YES;

    UILabel *hint = [[UILabel alloc] initWithFrame:CGRectMake(12, 8, 312, 18)];
    hint.text = @"Keo tung nut (D-Pad/Analog/Danh) de doi vi tri";
    hint.textColor = [UIColor colorWithRed:1.0 green:0.85 blue:0.2 alpha:1.0];
    hint.font = [UIFont boldSystemFontOfSize:12];
    hint.textAlignment = NSTextAlignmentCenter;
    [self.editorPanel addSubview:hint];

    self.opacityLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 34, 110, 22)];
    self.opacityLabel.textColor = UIColor.whiteColor;
    self.opacityLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.opacityLabel];

    self.opacitySlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 32, 196, 26)];
    self.opacitySlider.minimumValue = 0.15f;
    self.opacitySlider.maximumValue = 1.0f;
    self.opacitySlider.value = self.hudOpacity;
    [self.opacitySlider addTarget:self action:@selector(onOpacityChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.opacitySlider];

    self.scaleLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 68, 110, 22)];
    self.scaleLabel.textColor = UIColor.whiteColor;
    self.scaleLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.scaleLabel];

    self.scaleSlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 66, 196, 26)];
    self.scaleSlider.minimumValue = 0.70f;
    self.scaleSlider.maximumValue = 1.35f;
    self.scaleSlider.value = self.hudScale;
    [self.scaleSlider addTarget:self action:@selector(onScaleChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.scaleSlider];

    self.toggleDpadBtn = [self makePanelButton:@"D-Pad: Bat" frame:CGRectMake(12, 104, 100, 34)
                                         color:[UIColor colorWithRed:0.15 green:0.48 blue:0.85 alpha:0.92]
                                        action:@selector(onToggleDpad)];
    self.toggleJoyBtn  = [self makePanelButton:@"Analog: Bat" frame:CGRectMake(118, 104, 100, 34)
                                         color:[UIColor colorWithRed:0.15 green:0.48 blue:0.85 alpha:0.92]
                                        action:@selector(onToggleJoy)];
    self.toggleExtraBtn = [self makePanelButton:@"D/W: Bat" frame:CGRectMake(224, 104, 100, 34)
                                          color:[UIColor colorWithRed:0.45 green:0.25 blue:0.75 alpha:0.92]
                                         action:@selector(onToggleDW)];
    [self.editorPanel addSubview:self.toggleDpadBtn];
    [self.editorPanel addSubview:self.toggleJoyBtn];
    [self.editorPanel addSubview:self.toggleExtraBtn];

    UIButton *resetBtn = [self makePanelButton:@"Reset mac dinh" frame:CGRectMake(12, 148, 150, 34)
                                         color:[UIColor colorWithRed:0.75 green:0.22 blue:0.22 alpha:0.92]
                                        action:@selector(onResetLayout)];
    UIButton *doneBtn  = [self makePanelButton:@"Xong" frame:CGRectMake(174, 148, 150, 34)
                                         color:[UIColor colorWithRed:0.25 green:0.88 blue:0.45 alpha:1.0]
                                        action:@selector(toggleEditMode)];
    [doneBtn setTitleColor:UIColor.blackColor forState:UIControlStateNormal];
    [self.editorPanel addSubview:resetBtn];
    [self.editorPanel addSubview:doneBtn];

    [self addSubview:self.editorPanel];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    UIEdgeInsets safe = self.safeAreaInsets;
    if (CGSizeEqualToSize(self.bounds.size, self.lastLayoutSize) && UIEdgeInsetsEqualToEdgeInsets(safe, self.lastSafeInsets)) {
        return;
    }
    self.lastLayoutSize = self.bounds.size;
    self.lastSafeInsets = safe;

    CGFloat w = self.bounds.size.width;
    CGFloat h = self.bounds.size.height;
    CGFloat topY = MAX((CGFloat)26.0, safe.top + 18.0);
    self.gearButton.frame = CGRectMake(w * 0.5 - 28.0, topY - 14.0, 56.0, 28.0);
    self.editorPanel.center = CGPointMake(w * 0.5, MAX((CGFloat)112.0, h * 0.45));

    NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        NSString *kx = [NSString stringWithFormat:@"%@pos_%@_x", kHUDPrefix, ctrl.controlID];
        NSString *ky = [NSString stringWithFormat:@"%@pos_%@_y", kHUDPrefix, ctrl.controlID];
        CGFloat nx = [ud objectForKey:kx] ? [ud floatForKey:kx] : ctrl.defaultNormCenter.x;
        CGFloat ny = [ud objectForKey:ky] ? [ud floatForKey:ky] : ctrl.defaultNormCenter.y;
        CGFloat px = MAX(safe.left + 28.0, MIN(w - safe.right - 28.0, w * nx));
        CGFloat py = MAX(topY, MIN(h - safe.bottom - 24.0, h * ny));
        ctrl.center = CGPointMake(px, py);
    }
}

- (void)applyVisualSettings {
    self.opacityLabel.text = [NSString stringWithFormat:@"Do mo: %d%%", (int)round(self.hudOpacity * 100)];
    self.scaleLabel.text   = [NSString stringWithFormat:@"Co nut: %d%%", (int)round(self.hudScale * 100)];
    [self.toggleDpadBtn setTitle:(self.showDpad ? @"D-Pad: Bat" : @"D-Pad: Tat") forState:UIControlStateNormal];
    [self.toggleJoyBtn setTitle:(self.showJoystick ? @"Analog: Bat" : @"Analog: Tat") forState:UIControlStateNormal];
    [self.toggleExtraBtn setTitle:(self.showExtraButtons ? @"D/W: Bat" : @"D/W: Tat") forState:UIControlStateNormal];

    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        ctrl.alpha = self.editMode ? MAX((CGFloat)0.75, self.hudOpacity) : self.hudOpacity;
        ctrl.transform = CGAffineTransformMakeScale(self.hudScale, self.hudScale);
        if ([ctrl.controlID isEqualToString:@"dpad"]) {
            ctrl.hidden = !self.showDpad;
        } else if ([ctrl.controlID isEqualToString:@"joystick"]) {
            ctrl.hidden = !self.showJoystick;
        } else if ([ctrl.controlID isEqualToString:@"btn_d"] || [ctrl.controlID isEqualToString:@"btn_w"]) {
            ctrl.hidden = !self.showExtraButtons;
        }
    }
    self.gearButton.alpha = self.editMode ? 1.0 : MAX((CGFloat)0.35, self.hudOpacity);
}

- (void)toggleEditMode {
    [self releaseAllInputs];
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

- (void)onToggleDpad {
    self.showDpad = !self.showDpad;
    if (!self.showDpad) [self updateDirectionSource:kDirSrcDpad up:NO down:NO left:NO right:NO];
    [NSUserDefaults.standardUserDefaults setBool:self.showDpad forKey:[kHUDPrefix stringByAppendingString:@"showDpad"]];
    [self applyVisualSettings];
}

- (void)onToggleJoy {
    self.showJoystick = !self.showJoystick;
    if (!self.showJoystick) [self updateDirectionSource:kDirSrcJoy up:NO down:NO left:NO right:NO];
    [NSUserDefaults.standardUserDefaults setBool:self.showJoystick forKey:[kHUDPrefix stringByAppendingString:@"showJoy"]];
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
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"showDpad"]];
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"showJoy"]];
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"showDW"]];
    self.hudOpacity = 0.58f;
    self.hudScale = 1.0f;
    self.showDpad = YES;
    self.showJoystick = YES;
    self.showExtraButtons = YES;
    self.opacitySlider.value = self.hudOpacity;
    self.scaleSlider.value = self.hudScale;
    self.lastLayoutSize = CGSizeZero;
    [self setNeedsLayout];
    [self layoutIfNeeded];
    [self applyVisualSettings];
}

@end