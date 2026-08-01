"""Model the one-shot per-theme redesign of success/warning/danger.

Constraints per (preset, mode, role):
  C1 fill vs --bg2 and vs --panel   >= 3.0   (non-text, WCAG 1.4.11)
  C2 --on-accent text on solid fill >= 4.5
  C3 mixed text (61.8% semantic + text anchor) on bg2/panel >= 4.5
  C4 distance from the theme accent: hue >= HUE_MIN, OR contrast(semantic, accent) >= LUM_MIN
Objective: saturation aligned to the theme accent, hue unmoved, lightness as close
to the shipped value as the constraints allow.
"""
import colorsys, sys, itertools
sys.path.insert(0, "backend")
from studiosaas.presets import VISUAL_STYLE_PRESETS

HUE_MIN = 30.0     # degrees of hue separation that reads as "a different thing"
LUM_MIN = 1.55     # contrast ratio that reads as "a different weight" when hue is close
S_WEIGHT = 0.6     # how far saturation travels toward the accent
S_FLOOR, S_CEIL = 0.20, 0.72

def hex2rgb(h): h=h.lstrip('#'); return tuple(int(h[i:i+2],16)/255 for i in (0,2,4))
def rgb2hex(r): return '#%02X%02X%02X' % tuple(max(0,min(255,round(c*255))) for c in r)
def lum(rgb):
    f=lambda c: c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
    r,g,b=[f(c) for c in rgb]; return 0.2126*r+0.7152*g+0.0722*b
def cr(a,b):
    la,lb=lum(a),lum(b); hi,lo=max(la,lb),min(la,lb); return (hi+0.05)/(lo+0.05)
def hsl(h): r,g,b=hex2rgb(h); hh,l,s=colorsys.rgb_to_hls(r,g,b); return hh*360,s,l
def from_hsl(h,s,l): return colorsys.hls_to_rgb((h%360)/360,l,s)
def hued(a,b): d=abs(a-b)%360; return min(d,360-d)
def mix(a,b,p):  # p of a, rest b, srgb
    return tuple(a[i]*p+b[i]*(1-p) for i in range(3))

ROLES=('success_color','warning_color','danger_color')

def evaluate(rgb, th, accent_rgb, accent_h):
    bg2, panel, anchor, on_acc = (hex2rgb(th['background_alt_color']), hex2rgb(th['panel_color']),
                                  hex2rgb(th['text_color']), hex2rgb(th['accent_text_color']))
    mixed = mix(rgb, anchor, 0.618)
    fails=[]
    c1=min(cr(rgb,bg2), cr(rgb,panel))
    c2=cr(on_acc,rgb)
    c3=min(cr(mixed,bg2), cr(mixed,panel))
    if c1<3.0: fails.append('fill')
    if c2<4.5: fails.append('on-fill')
    if c3<4.5: fails.append('text')
    hh,_,_=colorsys.rgb_to_hls(*rgb); hh*=360
    dist_ok = hued(hh,accent_h)>=HUE_MIN or cr(rgb,accent_rgb)>=LUM_MIN
    if not dist_ok: fails.append('vs-accent')
    return fails,(c1,c2,c3,cr(rgb,accent_rgb),hued(hh,accent_h))

rows=[]; unsolved=[]; worst={'fill':9,'on-fill':9,'text':9}
for key,p in VISUAL_STYLE_PRESETS.items():
    for mode in p['modes']:
        th=p['themes'][mode]
        acc=th['accent_color']; ah,as_,al=hsl(acc); acc_rgb=hex2rgb(acc)
        for role in ROLES:
            cur=th[role]; h,s,l=hsl(cur)
            tgt_s=max(S_FLOOR,min(S_CEIL, s+S_WEIGHT*(as_-s)))
            best=None
            for ds in [0,-0.03,0.03,-0.06,0.06,-0.10,0.10,-0.15,0.15]:
                ss=max(0.10,min(0.90,tgt_s+ds))
                for dl in [i*0.005 for i in range(0,121)]:
                    for sign in ((0,) if dl==0 else (-1,1)):
                        ll=l+sign*dl
                        if not 0.05<=ll<=0.95: continue
                        rgb=from_hsl(h,ss,ll)
                        fails,m=evaluate(rgb,th,acc_rgb,ah)
                        if fails: continue
                        cost=abs(ss-tgt_s)*2+dl
                        if best is None or cost<best[0]: best=(cost,rgb,ss,ll,m)
                if best and best[0]<0.02: break
            if best is None:
                unsolved.append((key,mode,role)); continue
            _,rgb,ss,ll,m=best
            for k,v in zip(('fill','on-fill','text'),m[:3]): worst[k]=min(worst[k],v)
            old_fails,old_m=evaluate(hex2rgb(cur),th,acc_rgb,ah)
            rows.append((key,mode,role.split('_')[0],cur,rgb2hex(rgb),
                         round(s*100),round(ss*100),round(l*100),round(ll*100),
                         round(old_m[4]),round(m[4]),old_fails))

print(f"presets*modes*roles = {len(rows)+len(unsolved)}   unsolved = {len(unsolved)}")
print(f"worst after: fill-on-surface {worst['fill']:.2f} (>=3.0)  text-on-fill {worst['on-fill']:.2f} (>=4.5)  semantic-text {worst['text']:.2f} (>=4.5)")
print(f"\nrows whose SHIPPED value violates a constraint ({sum(1 for r in rows if r[-1])}):")
for r in rows:
    if r[-1]:
        print(f"  {r[0]:<14} {r[1]:<5} {r[2]:<7} {r[3]} -> {r[4]}  S {r[5]:>2}->{r[6]:<2}  L {r[7]:>2}->{r[8]:<2}  dH(acc) {r[9]:>3}  fails={','.join(r[-1])}")
moved=[r for r in rows if r[3].upper()!=r[4].upper()]
print(f"\ntotal values changed: {len(moved)}/{len(rows)}")
print("largest saturation moves:")
for r in sorted(moved,key=lambda r:-abs(r[6]-r[5]))[:8]:
    print(f"  {r[0]:<14} {r[1]:<5} {r[2]:<7} {r[3]} -> {r[4]}  S {r[5]:>2}->{r[6]:<2}  L {r[7]:>2}->{r[8]:<2}")
