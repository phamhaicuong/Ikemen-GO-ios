#import <UIKit/UIKit.h>
#import <math.h>
#if __has_include(<SDL2/SDL.h>)
#import <SDL2/SDL.h>
#else
#import "SDL.h"
#endif

static NSString *const kHUDPrefix = @"IkemenCustomHUD_v3_";
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
@property (nonatomic, assign) BOOL p2Tint;
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

- (void)refreshBorderColor {
    CGColorRef border = self.editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : (self.p2Tint
           ? [UIColor colorWithRed:1.0 green:0.55 blue:0.20 alpha:0.88].CGColor
           : [UIColor colorWithWhite:1.0 alpha:0.70].CGColor);
    self.upArrow.layer.borderColor = border;
    self.downArrow.layer.borderColor = border;
    self.leftArrow.layer.borderColor = border;
    self.rightArrow.layer.borderColor = border;
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    [self refreshBorderColor];
}

- (void)setP2Tint:(BOOL)p2Tint {
    _p2Tint = p2Tint;
    [self refreshBorderColor];
}

- (void)stylePad:(UILabel *)pad active:(BOOL)active {
    pad.backgroundColor = active
        ? (self.p2Tint
           ? [UIColor colorWithRed:0.95 green:0.45 blue:0.15 alpha:0.88]
           : [UIColor colorWithRed:0.18 green:0.62 blue:1.0 alpha:0.88])
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
@property (nonatomic, strong) UILabel *badgeLabel;
@property (nonatomic, strong) UITouch *activeTouch;
@property (nonatomic, assign) BOOL heldUp;
@property (nonatomic, assign) BOOL heldDown;
@property (nonatomic, assign) BOOL heldLeft;
@property (nonatomic, assign) BOOL heldRight;
@property (nonatomic, assign) BOOL p2Tint;
@end

@implementation IkemenJoystickView

- (instancetype)initWithID:(NSString *)cid baseSize:(CGFloat)size badge:(NSString *)badge {
    self = [super initWithFrame:CGRectMake(0, 0, size, size)];
    if (self) {
        self.controlID = cid;
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

        if (badge.length > 0) {
            self.badgeLabel = [[UILabel alloc] initWithFrame:self.knobView.bounds];
            self.badgeLabel.text = badge;
            self.badgeLabel.textAlignment = NSTextAlignmentCenter;
            self.badgeLabel.font = [UIFont boldSystemFontOfSize:13];
            self.badgeLabel.textColor = [UIColor colorWithWhite:0.1 alpha:0.9];
            self.badgeLabel.userInteractionEnabled = NO;
            [self.knobView addSubview:self.badgeLabel];
        }
    }
    return self;
}

- (void)refreshBorderColor {
    self.layer.borderColor = self.editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : (self.p2Tint
           ? [UIColor colorWithRed:1.0 green:0.55 blue:0.20 alpha:0.90].CGColor
           : [UIColor colorWithWhite:1.0 alpha:0.65].CGColor);
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    [self refreshBorderColor];
}

- (void)setP2Tint:(BOOL)p2Tint {
    _p2Tint = p2Tint;
    [self refreshBorderColor];
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
@property (nonatomic, assign) SDL_Keycode p1Keycode;
@property (nonatomic, assign) SDL_Keycode p2Keycode;
@property (nonatomic, assign) SDL_Keycode activeKeycode;
@property (nonatomic, assign) BOOL isDedicatedP2;
@property (nonatomic, assign) BOOL isSystemButton;
@property (nonatomic, assign) BOOL isExtraButton;
@property (nonatomic, assign) BOOL pressedState;
@property (nonatomic, assign) BOOL p2Tint;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UIColor *tintAccent;
@property (nonatomic, strong) UITouch *dragTouch;
- (void)setButtonPressed:(BOOL)pressed;
@end

@implementation IkemenActionButton

- (instancetype)initWithID:(NSString *)cid
                     title:(NSString *)title
                     p1Key:(SDL_Keycode)p1k
                     p2Key:(SDL_Keycode)p2k
                      size:(CGSize)size
                    accent:(UIColor *)accent
                  isSystem:(BOOL)isSys
                   isExtra:(BOOL)isExtra
               dedicatedP2:(BOOL)dedP2 {
    self = [super initWithFrame:CGRectMake(0, 0, size.width, size.height)];
    if (self) {
        self.controlID = cid;
        self.p1Keycode = p1k;
        self.p2Keycode = p2k;
        self.activeKeycode = dedP2 ? p2k : p1k;
        self.isDedicatedP2 = dedP2;
        self.isSystemButton = isSys;
        self.isExtraButton = isExtra;
        self.tintAccent = accent;
        self.multipleTouchEnabled = YES;
        self.exclusiveTouch = NO;
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
        self.titleLabel.font = [UIFont boldSystemFontOfSize:(size.height >= 48 ? 18 : 12)];
        self.titleLabel.userInteractionEnabled = NO;
        [self addSubview:self.titleLabel];
    }
    return self;
}

- (void)refreshBorderColor {
    self.layer.borderColor = self.editMode
        ? [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:1.0].CGColor
        : ((self.p2Tint || self.isDedicatedP2)
           ? [UIColor colorWithRed:1.0 green:0.55 blue:0.20 alpha:0.90].CGColor
           : [UIColor colorWithWhite:1.0 alpha:0.75].CGColor);
}

- (void)setEditMode:(BOOL)editMode {
    _editMode = editMode;
    [self releaseAllKeys];
    self.userInteractionEnabled = editMode;
    [self refreshBorderColor];
}

- (void)setP2Tint:(BOOL)p2Tint {
    _p2Tint = p2Tint;
    [self refreshBorderColor];
}

- (void)setButtonPressed:(BOOL)pressed {
    if (self.pressedState == pressed) return;
    self.pressedState = pressed;
    self.backgroundColor = [self.tintAccent colorWithAlphaComponent:(pressed ? 0.88 : 0.42)];
    IkemenSendSDLKey(self.activeKeycode, pressed);
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
@property (nonatomic, strong) IkemenJoystickView *p2JoyView;
@property (nonatomic, strong) UIButton *gearButton;
@property (nonatomic, strong) UIView *editorPanel;
@property (nonatomic, strong) UISlider *opacitySlider;
@property (nonatomic, strong) UISlider *scaleSlider;
@property (nonatomic, strong) UILabel *opacityLabel;
@property (nonatomic, strong) UILabel *scaleLabel;
@property (nonatomic, strong) UIButton *toggleDpadBtn;
@property (nonatomic, strong) UIButton *toggleJoyBtn;
@property (nonatomic, strong) UIButton *toggleExtraBtn;
@property (nonatomic, strong) UIButton *playerModeBtn;
@property (nonatomic, assign) BOOL editMode;
@property (nonatomic, assign) CGFloat hudOpacity;
@property (nonatomic, assign) CGFloat hudScale;
@property (nonatomic, assign) BOOL showDpad;
@property (nonatomic, assign) BOOL showJoystick;
@property (nonatomic, assign) BOOL showExtraButtons;
// 0 = P1 (mac dinh), 1 = P2 (doi nut sang P2), 2 = P1+P2 (hien them cum nut P2)
@property (nonatomic, assign) NSInteger playerMode;
@property (nonatomic, assign) uint8_t p1UpMask;
@property (nonatomic, assign) uint8_t p1DownMask;
@property (nonatomic, assign) uint8_t p1LeftMask;
@property (nonatomic, assign) uint8_t p1RightMask;
@property (nonatomic, assign) uint8_t p2UpMask;
@property (nonatomic, assign) uint8_t p2DownMask;
@property (nonatomic, assign) uint8_t p2LeftMask;
@property (nonatomic, assign) uint8_t p2RightMask;
@property (nonatomic, assign) CGSize lastLayoutSize;
@property (nonatomic, assign) UIEdgeInsets lastSafeInsets;
+ (void)attachToKeyWindow;
@end

@implementation IkemenTouchHUD

+ (void)attachToKeyWindow {}

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
        self.playerMode = [ud integerForKey:[kHUDPrefix stringByAppendingString:@"playerMode"]];
        if (self.playerMode < 0 || self.playerMode > 2) self.playerMode = 0;

        [self buildControls];
        [self buildEditorUI];
        [self applyVisualSettings];

        [[NSNotificationCenter defaultCenter] addObserver:self
                                                 selector:@selector(releaseAllInputs)
                                                     name:UIApplicationWillResignActiveNotification
                                                   object:nil];
    }
    return self;
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)updateP1MaskSrc:(uint8_t)src up:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    BOOL oldU = (self.p1UpMask != 0), oldD = (self.p1DownMask != 0), oldL = (self.p1LeftMask != 0), oldR = (self.p1RightMask != 0);
    if (u) self.p1UpMask |= src;    else self.p1UpMask &= ~src;
    if (d) self.p1DownMask |= src;  else self.p1DownMask &= ~src;
    if (l) self.p1LeftMask |= src;  else self.p1LeftMask &= ~src;
    if (r) self.p1RightMask |= src; else self.p1RightMask &= ~src;
    BOOL newU = (self.p1UpMask != 0), newD = (self.p1DownMask != 0), newL = (self.p1LeftMask != 0), newR = (self.p1RightMask != 0);
    if (newU != oldU) IkemenSendSDLKey(SDLK_UP, newU);
    if (newD != oldD) IkemenSendSDLKey(SDLK_DOWN, newD);
    if (newL != oldL) IkemenSendSDLKey(SDLK_LEFT, newL);
    if (newR != oldR) IkemenSendSDLKey(SDLK_RIGHT, newR);
}

- (void)updateP2MaskSrc:(uint8_t)src up:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    BOOL oldU = (self.p2UpMask != 0), oldD = (self.p2DownMask != 0), oldL = (self.p2LeftMask != 0), oldR = (self.p2RightMask != 0);
    if (u) self.p2UpMask |= src;    else self.p2UpMask &= ~src;
    if (d) self.p2DownMask |= src;  else self.p2DownMask &= ~src;
    if (l) self.p2LeftMask |= src;  else self.p2LeftMask &= ~src;
    if (r) self.p2RightMask |= src; else self.p2RightMask &= ~src;
    BOOL newU = (self.p2UpMask != 0), newD = (self.p2DownMask != 0), newL = (self.p2LeftMask != 0), newR = (self.p2RightMask != 0);
    if (newU != oldU) IkemenSendSDLKey(SDLK_i, newU);
    if (newD != oldD) IkemenSendSDLKey(SDLK_k, newD);
    if (newL != oldL) IkemenSendSDLKey(SDLK_j, newL);
    if (newR != oldR) IkemenSendSDLKey(SDLK_l, newR);
}

- (void)updatePrimaryDirectionSrc:(uint8_t)src up:(BOOL)u down:(BOOL)d left:(BOOL)l right:(BOOL)r {
    if (self.playerMode == 1) {
        [self updateP2MaskSrc:src up:u down:d left:l right:r];
    } else {
        [self updateP1MaskSrc:src up:u down:d left:l right:r];
    }
}

- (void)releaseAllInputs {
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        [ctrl releaseAllKeys];
    }
    [self updateP1MaskSrc:(kDirSrcDpad | kDirSrcJoy) up:NO down:NO left:NO right:NO];
    [self updateP2MaskSrc:(kDirSrcDpad | kDirSrcJoy) up:NO down:NO left:NO right:NO];
}

- (UIView *)hitTest:(CGPoint)point withEvent:(UIEvent *)event {
    if (self.editMode) {
        UIView *hit = [super hitTest:point withEvent:event];
        return (hit == self) ? nil : hit;
    }
    UIView *hit = [super hitTest:point withEvent:event];
    if (hit && hit != self) return hit;
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
                if (CGRectIntersectsRect(CGRectInset(btn.frame, -slop, -slop), fingerRect)) {
                    [nowPressed addObject:btn];
                }
            }
        }
    }
    for (IkemenActionButton *btn in self.actionButtons) {
        if (!btn.hidden) {
            [btn setButtonPressed:[nowPressed containsObject:btn]];
        }
    }
}

- (void)touchesBegan:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self processActionTouches:event.allTouches]; }
- (void)touchesMoved:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self processActionTouches:event.allTouches]; }
- (void)touchesEnded:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self processActionTouches:event.allTouches]; }
- (void)touchesCancelled:(NSSet<UITouch *> *)touches withEvent:(UIEvent *)event { [self processActionTouches:event.allTouches]; }

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

- (void)addBtn:(NSString *)cid title:(NSString *)title p1:(SDL_Keycode)p1 p2:(SDL_Keycode)p2
          size:(CGSize)sz accent:(UIColor *)col sys:(BOOL)isSys extra:(BOOL)isExtra dedP2:(BOOL)dedP2 norm:(CGPoint)norm {
    IkemenActionButton *btn = [[IkemenActionButton alloc] initWithID:cid title:title p1Key:p1 p2Key:p2
                                                                size:sz accent:col isSystem:isSys isExtra:isExtra dedicatedP2:dedP2];
    [self.actionButtons addObject:btn];
    [self registerControl:btn defaultNorm:norm];
}

- (void)buildControls {
    __weak typeof(self) weakSelf = self;

    // 1. Primary Controls (Player 1 mac dinh; doi sang Player 2 khi chon Che do: P2)
    self.dpadView = [[IkemenDPadView alloc] initWithBaseSize:140.0];
    self.dpadView.onDirectionChanged = ^(BOOL u, BOOL d, BOOL l, BOOL r) {
        [weakSelf updatePrimaryDirectionSrc:kDirSrcDpad up:u down:d left:l right:r];
    };
    [self registerControl:self.dpadView defaultNorm:CGPointMake(0.14, 0.45)];

    self.joyView = [[IkemenJoystickView alloc] initWithID:@"joystick" baseSize:118.0 badge:nil];
    self.joyView.onDirectionChanged = ^(BOOL u, BOOL d, BOOL l, BOOL r) {
        [weakSelf updatePrimaryDirectionSrc:kDirSrcJoy up:u down:d left:l right:r];
    };
    [self registerControl:self.joyView defaultNorm:CGPointMake(0.14, 0.78)];

    CGSize btnSz = CGSizeMake(56, 56);
    UIColor *punchCol = [UIColor colorWithRed:0.15 green:0.55 blue:0.95 alpha:1.0];
    UIColor *kickCol  = [UIColor colorWithRed:0.90 green:0.28 blue:0.28 alpha:1.0];
    UIColor *extraCol = [UIColor colorWithRed:0.62 green:0.35 blue:0.90 alpha:1.0];
    UIColor *sysCol   = [UIColor colorWithWhite:0.25 alpha:1.0];

    // Khop chinh xac bang KEY CONFIG P1 & P2:
    // X(a/r), Y(s/t), Z(d/y), A(z/f), B(x/g), C(c/h), D(q/LBRACKET), W(w/RBRACKET), START(RETURN/RSHIFT), MENU(TAB/BACKSLASH)
    [self addBtn:@"btn_x" title:@"X" p1:SDLK_a p2:SDLK_r size:btnSz accent:punchCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.73, 0.58)];
    [self addBtn:@"btn_y" title:@"Y" p1:SDLK_s p2:SDLK_t size:btnSz accent:punchCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.82, 0.52)];
    [self addBtn:@"btn_z" title:@"Z" p1:SDLK_d p2:SDLK_y size:btnSz accent:punchCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.91, 0.56)];

    [self addBtn:@"btn_a" title:@"A" p1:SDLK_z p2:SDLK_f size:btnSz accent:kickCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.71, 0.78)];
    [self addBtn:@"btn_b" title:@"B" p1:SDLK_x p2:SDLK_g size:btnSz accent:kickCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.80, 0.72)];
    [self addBtn:@"btn_c" title:@"C" p1:SDLK_c p2:SDLK_h size:btnSz accent:kickCol sys:NO extra:NO dedP2:NO norm:CGPointMake(0.89, 0.76)];

    CGSize extraSz = CGSizeMake(46, 46);
    [self addBtn:@"btn_d" title:@"D" p1:SDLK_q p2:SDLK_LEFTBRACKET  size:extraSz accent:extraCol sys:NO extra:YES dedP2:NO norm:CGPointMake(0.77, 0.34)];
    [self addBtn:@"btn_w" title:@"W" p1:SDLK_w p2:SDLK_RIGHTBRACKET size:extraSz accent:extraCol sys:NO extra:YES dedP2:NO norm:CGPointMake(0.86, 0.32)];

    CGSize sysSz = CGSizeMake(62, 30);
    [self addBtn:@"btn_menu"  title:@"MENU"  p1:SDLK_TAB    p2:SDLK_BACKSLASH size:sysSz accent:sysCol sys:YES extra:NO dedP2:NO norm:CGPointMake(0.40, 0.09)];
    [self addBtn:@"btn_start" title:@"START" p1:SDLK_RETURN p2:SDLK_RSHIFT    size:sysSz accent:sysCol sys:YES extra:NO dedP2:NO norm:CGPointMake(0.60, 0.09)];

    // 2. Cum nut Player 2 rieng (Chi hien khi chon "Che do: P1+P2" trong bang HUD)
    UIColor *p2Punch = [UIColor colorWithRed:0.95 green:0.52 blue:0.15 alpha:1.0];
    UIColor *p2Kick  = [UIColor colorWithRed:0.85 green:0.25 blue:0.52 alpha:1.0];
    UIColor *p2Sys   = [UIColor colorWithRed:0.55 green:0.30 blue:0.12 alpha:1.0];
    CGSize p2BtnSz   = CGSizeMake(42, 42);
    CGSize p2SysSz   = CGSizeMake(50, 26);

    self.p2JoyView = [[IkemenJoystickView alloc] initWithID:@"p2_joy" baseSize:92.0 badge:@"P2"];
    self.p2JoyView.p2Tint = YES;
    self.p2JoyView.onDirectionChanged = ^(BOOL u, BOOL d, BOOL l, BOOL r) {
        [weakSelf updateP2MaskSrc:kDirSrcJoy up:u down:d left:l right:r];
    };
    [self registerControl:self.p2JoyView defaultNorm:CGPointMake(0.32, 0.78)];

    [self addBtn:@"p2_x" title:@"X2" p1:SDLK_r p2:SDLK_r size:p2BtnSz accent:p2Punch sys:NO extra:NO dedP2:YES norm:CGPointMake(0.46, 0.62)];
    [self addBtn:@"p2_y" title:@"Y2" p1:SDLK_t p2:SDLK_t size:p2BtnSz accent:p2Punch sys:NO extra:NO dedP2:YES norm:CGPointMake(0.53, 0.58)];
    [self addBtn:@"p2_z" title:@"Z2" p1:SDLK_y p2:SDLK_y size:p2BtnSz accent:p2Punch sys:NO extra:NO dedP2:YES norm:CGPointMake(0.60, 0.62)];
    [self addBtn:@"p2_a" title:@"A2" p1:SDLK_f p2:SDLK_f size:p2BtnSz accent:p2Kick  sys:NO extra:NO dedP2:YES norm:CGPointMake(0.46, 0.80)];
    [self addBtn:@"p2_b" title:@"B2" p1:SDLK_g p2:SDLK_g size:p2BtnSz accent:p2Kick  sys:NO extra:NO dedP2:YES norm:CGPointMake(0.53, 0.76)];
    [self addBtn:@"p2_c" title:@"C2" p1:SDLK_h p2:SDLK_h size:p2BtnSz accent:p2Kick  sys:NO extra:NO dedP2:YES norm:CGPointMake(0.60, 0.80)];
    [self addBtn:@"p2_d" title:@"D2" p1:SDLK_LEFTBRACKET  p2:SDLK_LEFTBRACKET  size:CGSizeMake(38, 38) accent:p2Sys sys:NO extra:YES dedP2:YES norm:CGPointMake(0.49, 0.44)];
    [self addBtn:@"p2_w" title:@"W2" p1:SDLK_RIGHTBRACKET p2:SDLK_RIGHTBRACKET size:CGSizeMake(38, 38) accent:p2Sys sys:NO extra:YES dedP2:YES norm:CGPointMake(0.57, 0.44)];
    [self addBtn:@"p2_start" title:@"S2" p1:SDLK_RSHIFT    p2:SDLK_RSHIFT    size:p2SysSz accent:p2Sys sys:YES extra:NO dedP2:YES norm:CGPointMake(0.72, 0.09)];
    [self addBtn:@"p2_menu"  title:@"M2" p1:SDLK_BACKSLASH p2:SDLK_BACKSLASH size:p2SysSz accent:p2Sys sys:YES extra:NO dedP2:YES norm:CGPointMake(0.28, 0.09)];
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

    self.editorPanel = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 344, 238)];
    self.editorPanel.backgroundColor = [UIColor colorWithWhite:0.08 alpha:0.93];
    self.editorPanel.layer.cornerRadius = 14;
    self.editorPanel.layer.borderWidth = 1.2;
    self.editorPanel.layer.borderColor = [UIColor colorWithRed:1.0 green:0.8 blue:0.1 alpha:0.9].CGColor;
    self.editorPanel.hidden = YES;

    UILabel *hint = [[UILabel alloc] initWithFrame:CGRectMake(12, 8, 320, 18)];
    hint.text = @"Keo tung nut de doi vi tri (Tu dong luu)";
    hint.textColor = [UIColor colorWithRed:1.0 green:0.85 blue:0.2 alpha:1.0];
    hint.font = [UIFont boldSystemFontOfSize:12];
    hint.textAlignment = NSTextAlignmentCenter;
    [self.editorPanel addSubview:hint];

    self.opacityLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 34, 110, 22)];
    self.opacityLabel.textColor = UIColor.whiteColor;
    self.opacityLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.opacityLabel];

    self.opacitySlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 32, 204, 26)];
    self.opacitySlider.minimumValue = 0.15f;
    self.opacitySlider.maximumValue = 1.0f;
    self.opacitySlider.value = self.hudOpacity;
    [self.opacitySlider addTarget:self action:@selector(onOpacityChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.opacitySlider];

    self.scaleLabel = [[UILabel alloc] initWithFrame:CGRectMake(14, 68, 110, 22)];
    self.scaleLabel.textColor = UIColor.whiteColor;
    self.scaleLabel.font = [UIFont systemFontOfSize:12];
    [self.editorPanel addSubview:self.scaleLabel];

    self.scaleSlider = [[UISlider alloc] initWithFrame:CGRectMake(124, 66, 204, 26)];
    self.scaleSlider.minimumValue = 0.70f;
    self.scaleSlider.maximumValue = 1.35f;
    self.scaleSlider.value = self.hudScale;
    [self.scaleSlider addTarget:self action:@selector(onScaleChanged:) forControlEvents:UIControlEventValueChanged];
    [self.editorPanel addSubview:self.scaleSlider];

    // Hang chon che do Player 1 / Player 2 / P1+P2
    self.playerModeBtn = [self makePanelButton:@"Dieu khien: Chi Player 1" frame:CGRectMake(12, 102, 320, 34)
                                         color:[UIColor colorWithRed:0.88 green:0.44 blue:0.12 alpha:0.95]
                                        action:@selector(onCyclePlayerMode)];
    [self.editorPanel addSubview:self.playerModeBtn];

    self.toggleDpadBtn = [self makePanelButton:@"D-Pad: Bat" frame:CGRectMake(12, 144, 102, 34)
                                         color:[UIColor colorWithRed:0.15 green:0.48 blue:0.85 alpha:0.92]
                                        action:@selector(onToggleDpad)];
    self.toggleJoyBtn  = [self makePanelButton:@"Analog: Bat" frame:CGRectMake(121, 144, 102, 34)
                                         color:[UIColor colorWithRed:0.15 green:0.48 blue:0.85 alpha:0.92]
                                        action:@selector(onToggleJoy)];
    self.toggleExtraBtn = [self makePanelButton:@"D/W: Bat" frame:CGRectMake(230, 144, 102, 34)
                                          color:[UIColor colorWithRed:0.45 green:0.25 blue:0.75 alpha:0.92]
                                         action:@selector(onToggleDW)];
    [self.editorPanel addSubview:self.toggleDpadBtn];
    [self.editorPanel addSubview:self.toggleJoyBtn];
    [self.editorPanel addSubview:self.toggleExtraBtn];

    UIButton *resetBtn = [self makePanelButton:@"Reset mac dinh" frame:CGRectMake(12, 188, 156, 36)
                                         color:[UIColor colorWithRed:0.75 green:0.22 blue:0.22 alpha:0.92]
                                        action:@selector(onResetLayout)];
    UIButton *doneBtn  = [self makePanelButton:@"Xong" frame:CGRectMake(176, 188, 156, 36)
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
    self.gearButton.frame = CGRectMake(w * 0.5 - 32.0, topY - 14.0, 64.0, 28.0);
    self.editorPanel.center = CGPointMake(w * 0.5, MAX((CGFloat)130.0, h * 0.48));

    NSUserDefaults *ud = NSUserDefaults.standardUserDefaults;
    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        NSString *kx = [NSString stringWithFormat:@"%@pos_%@_x", kHUDPrefix, ctrl.controlID];
        NSString *ky = [NSString stringWithFormat:@"%@pos_%@_y", kHUDPrefix, ctrl.controlID];
        CGFloat nx = [ud objectForKey:kx] ? [ud floatForKey:kx] : ctrl.defaultNormCenter.x;
        CGFloat ny = [ud objectForKey:ky] ? [ud floatForKey:ky] : ctrl.defaultNormCenter.y;
        CGFloat px = MAX(safe.left + 26.0, MIN(w - safe.right - 26.0, w * nx));
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

    BOOL isSingleP2 = (self.playerMode == 1);
    BOOL showDualP2 = (self.playerMode == 2);

    if (self.playerMode == 0) {
        [self.playerModeBtn setTitle:@"Player: Chi P1 (Mac dinh)" forState:UIControlStateNormal];
        [self.gearButton setTitle:@"HUD" forState:UIControlStateNormal];
        self.gearButton.layer.borderColor = [UIColor colorWithWhite:1.0 alpha:0.5].CGColor;
    } else if (self.playerMode == 1) {
        [self.playerModeBtn setTitle:@"Player: Dang dieu khien P2" forState:UIControlStateNormal];
        [self.gearButton setTitle:@"HUD P2" forState:UIControlStateNormal];
        self.gearButton.layer.borderColor = [UIColor colorWithRed:1.0 green:0.55 blue:0.20 alpha:0.95].CGColor;
    } else {
        [self.playerModeBtn setTitle:@"Player: Hien ca P1 + P2" forState:UIControlStateNormal];
        [self.gearButton setTitle:@"HUD 2P" forState:UIControlStateNormal];
        self.gearButton.layer.borderColor = [UIColor colorWithRed:1.0 green:0.75 blue:0.20 alpha:0.95].CGColor;
    }

    self.dpadView.p2Tint = isSingleP2;
    self.joyView.p2Tint  = isSingleP2;

    for (UIView<IkemenHUDControl> *ctrl in self.controls) {
        ctrl.alpha = self.editMode ? MAX((CGFloat)0.75, self.hudOpacity) : self.hudOpacity;
        ctrl.transform = CGAffineTransformMakeScale(self.hudScale, self.hudScale);
        if (ctrl == self.dpadView) {
            ctrl.hidden = !self.showDpad;
        } else if (ctrl == self.joyView) {
            ctrl.hidden = !self.showJoystick;
        } else if (ctrl == self.p2JoyView) {
            ctrl.hidden = !showDualP2;
        } else if ([ctrl isKindOfClass:[IkemenActionButton class]]) {
            IkemenActionButton *btn = (IkemenActionButton *)ctrl;
            if (btn.isDedicatedP2) {
                btn.activeKeycode = btn.p2Keycode;
                btn.hidden = !showDualP2 || (btn.isExtraButton && !self.showExtraButtons);
            } else {
                btn.activeKeycode = isSingleP2 ? btn.p2Keycode : btn.p1Keycode;
                btn.p2Tint = isSingleP2;
                btn.hidden = (btn.isExtraButton && !self.showExtraButtons);
            }
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

- (void)onCyclePlayerMode {
    [self releaseAllInputs];
    self.playerMode = (self.playerMode + 1) % 3;
    [NSUserDefaults.standardUserDefaults setInteger:self.playerMode forKey:[kHUDPrefix stringByAppendingString:@"playerMode"]];
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
    [self releaseAllInputs];
    self.showDpad = !self.showDpad;
    [NSUserDefaults.standardUserDefaults setBool:self.showDpad forKey:[kHUDPrefix stringByAppendingString:@"showDpad"]];
    [self applyVisualSettings];
}

- (void)onToggleJoy {
    [self releaseAllInputs];
    self.showJoystick = !self.showJoystick;
    [NSUserDefaults.standardUserDefaults setBool:self.showJoystick forKey:[kHUDPrefix stringByAppendingString:@"showJoy"]];
    [self applyVisualSettings];
}

- (void)onToggleDW {
    [self releaseAllInputs];
    self.showExtraButtons = !self.showExtraButtons;
    [NSUserDefaults.standardUserDefaults setBool:self.showExtraButtons forKey:[kHUDPrefix stringByAppendingString:@"showDW"]];
    [self applyVisualSettings];
}

- (void)onResetLayout {
    [self releaseAllInputs];
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
    [ud removeObjectForKey:[kHUDPrefix stringByAppendingString:@"playerMode"]];
    self.hudOpacity = 0.58f;
    self.hudScale = 1.0f;
    self.showDpad = YES;
    self.showJoystick = YES;
    self.showExtraButtons = YES;
    self.playerMode = 0;
    self.opacitySlider.value = self.hudOpacity;
    self.scaleSlider.value = self.hudScale;
    self.lastLayoutSize = CGSizeZero;
    [self setNeedsLayout];
    [self layoutIfNeeded];
    [self applyVisualSettings];
}

@end