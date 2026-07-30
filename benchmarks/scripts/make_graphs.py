#!/usr/bin/env python3
import re, os, matplotlib
HERE=os.path.dirname(os.path.abspath(__file__))
GRAPHS=os.path.join(HERE,"..","..","graphs")
os.makedirs(GRAPHS,exist_ok=True)
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

BG="#0d1117"; FG="#e6edf3"; GRID="#30363d"; MUT="#8b949e"
F16="#58a6ff"; FIX="#3fb950"; ACC="#f0883e"; PUB="#d29922"
plt.rcParams.update({
    "figure.facecolor":BG,"axes.facecolor":BG,"savefig.facecolor":BG,
    "text.color":FG,"axes.labelcolor":FG,"xtick.color":MUT,"ytick.color":MUT,
    "axes.edgecolor":GRID,"grid.color":GRID,"font.size":12,
    "axes.titlesize":15,"axes.titleweight":"bold","figure.dpi":170,
})
FOOT="Radeon 8060S (gfx1151, RDNA3.5) | Mesa 26.3.0-devel + llama.cpp | -fa 1, r=3, amd_iommu=off | measured, not projected"

def parse(path):
    out={}
    if not os.path.exists(path): return out
    for ln in open(path):
        if "|" not in ln or ("pp" not in ln and "tg" not in ln): continue
        cells=[c.strip() for c in ln.split("|")]
        test=next((c for c in cells if re.match(r"(pp|tg)\d+",c)),None)
        if not test: continue
        val=cells[-2] if cells[-1]=="" else cells[-1]
        m=re.search(r"([\d.]+)",val.split("±")[0])
        if not m: continue
        d=0; md=re.search(r"@ d(\d+)",test); d=int(md.group(1)) if md else 0
        metric="tg" if test.startswith("tg") else "pp"
        out[(metric,d)]=float(m.group(1))
    return out

def curve(dat,metric):
    ds=sorted(d for (mm,d) in dat if mm==metric)
    return ds,[dat[(metric,d)] for d in ds]

def style(ax):
    ax.grid(True,alpha=.3,lw=.7); [s.set_visible(False) for s in (ax.spines['top'],ax.spines['right'])]
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_: f"{int(x/1024)}k" if x>=1024 else "0"))
    ax.set_xlabel("context depth (tokens)")

RES=os.path.join(HERE,"..","results","kvoff")
P1=os.path.join(RES,"kvoff-p1-results"); P2=os.path.join(RES,"kvoff-p2-results"); P3=os.path.join(RES,"kvoff-q8supp-results")
def parseM(name):  # merge Phase 1 (0-32k) + Phase 2 (0,64k) + q8 supplement per arm; iommu-off canonical
    d=parse(f"{P1}/{name}"); d.update(parse(f"{P2}/{name}")); d.update(parse(f"{P3}/{name}")); return d
# q8 is the featured reference quant (shipping-PR scope, higher KV quality, same win as q4)
c_f16=parseM("base_coder30b_f16.md"); c_q8=parseM("ceil_coder30b_q8.md")
x_f16=parseM("stock_q4kxl_f16.md"); x_q8=parseM("ceil_q4kxl_q8.md")
qc_f16=parseM("base_qwen35b_f16.md"); qc_q8=parseM("ceil_qwen35b_q8.md")
d_f16=parseM("densestock_dense7b_f16.md"); d_q8=parseM("denseceil_dense7b_q8.md")

# ---- Chart 1: Coder-30B prefill headline (2.66x) ----
fig,ax=plt.subplots(figsize=(9,5.2))
ds,y1=curve(c_f16,"pp"); _,y8=curve(c_q8,"pp")
ax.plot(ds,y1,"o-",color=F16,lw=2.6,ms=7,label="stock master 5c3a586, f16 KV")
ax.plot(ds,y8,"o-",color=FIX,lw=2.8,ms=7,label="FA fixes 63f88cc, q8 KV")
r=y8[-1]/y1[-1]
ax.annotate(f"{r:.2f}x\nfaster",(ds[-1],y8[-1]),xytext=(-70,-4),textcoords="offset points",
    color=FIX,fontweight="bold",fontsize=15,ha="center",
    arrowprops=dict(arrowstyle="->",color=FIX,lw=1.6))
ax.set_title("The FA fixes make prefill 2.66x faster at 64k (vs stock master)")
ax.set_ylabel("prefill throughput (tok/s)"); style(ax)
ax.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG,loc="upper right")
fig.text(.5,.012,"Qwen3-Coder-30B-A3B (Q6_K, head-dim 128) | "+FOOT,ha="center",color=MUT,fontsize=8.2)
fig.tight_layout(rect=[0,.04,1,1]); fig.savefig(os.path.join(GRAPHS,"01_coder30b_prefill_2.66x.png")); plt.close(fig)

# ---- Chart 2: 35B Q4_K_XL same-quant (prefill + decode) + kyuz0 decode overlay ----
fig,(a1,a2)=plt.subplots(1,2,figsize=(13,5.4))
ds,y1=curve(x_f16,"pp"); ds8,y2=curve(x_q8,"pp")
a1.plot(ds,y1,"o-",color=F16,lw=2.6,ms=6,label="f16 KV (stock)")
a1.plot(ds8,y2,"o-",color=FIX,lw=2.8,ms=6,label="q8 KV + fixes")
a1.set_title("Prefill  (+9% at 64k)"); a1.set_ylabel("prefill tok/s (pp512)"); style(a1)
a1.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG)
ds,y1=curve(x_f16,"tg"); ds8,y2=curve(x_q8,"tg")
a2.plot(ds,y1,"o-",color=F16,lw=2.6,ms=6,label="f16 KV (stock)")
a2.plot(ds8,y2,"o-",color=FIX,lw=2.8,ms=6,label="q8 KV + fixes")
# kyuz0 published f16 reference points
a2.scatter([32768,65536],[49.2,43.2],color=PUB,marker="X",s=110,zorder=5,label="kyuz0 public f16")
a2.set_title("Decode  (+15% at 64k, vs f16)"); a2.set_ylabel("decode tok/s (tg32)"); style(a2)
a2.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG)
fig.suptitle("Same weights, half the KV memory: q8 KV wins both halves at depth",fontsize=16,fontweight="bold")
fig.text(.5,.012,"Qwen3.6-35B-A3B (UD-Q4_K_XL, head-dim 256) | our stock-f16 matches kyuz0's published f16 (decode) | "+FOOT,ha="center",color=MUT,fontsize=7.6)
fig.tight_layout(rect=[0,.04,1,.96]); fig.savefig(os.path.join(GRAPHS,"02_35b_q4kxl_samequant.png")); plt.close(fig)

# ---- Chart 3: decode both models, f16 vs q4 ----
fig,ax=plt.subplots(figsize=(9,5.2))
for dat,c,lbl,ls in [(c_f16,F16,"Coder-30B  f16","--"),(c_q8,FIX,"Coder-30B  q8 + fixes","-"),
                     (qc_f16,"#8b949e","35B  f16","--"),(qc_q8,"#a371f7","35B  q8 + fixes","-")]:
    ds,y=curve(dat,"tg"); ax.plot(ds,y,("o"+ls),color=c,lw=2.6,ms=6,label=lbl)
ax.set_title("Quantized KV also generates faster than f16 at depth")
ax.set_ylabel("decode throughput (tok/s)"); style(ax)
ax.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG,ncol=2)
fig.text(.5,.012,"f16 KV (dashed) vs q8 KV + fixes (solid); q8 = shipping-PR scope + higher quality, same win as q4 | "+FOOT,ha="center",color=MUT,fontsize=7.8)
fig.tight_layout(rect=[0,.04,1,1]); fig.savefig(os.path.join(GRAPHS,"03_decode_both.png")); plt.close(fig)

# ---- Chart 4: dense-7B f16 vs q8 (the FA dequant-once fix is not MoE-specific) ----
fig,(a1,a2)=plt.subplots(1,2,figsize=(13,5.4))
ds,y1=curve(d_f16,"pp"); ds8,y2=curve(d_q8,"pp")
a1.plot(ds,y1,"o-",color=F16,lw=2.6,ms=6,label="f16 KV (stock)")
a1.plot(ds8,y2,"o-",color=FIX,lw=2.8,ms=6,label="q8 KV + fixes")
a1.set_title(f"Prefill  (+{y2[-1]/y1[-1]*100-100:.0f}% at 64k)"); a1.set_ylabel("prefill tok/s (pp512)"); style(a1)
a1.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG)
ds,y1=curve(d_f16,"tg"); ds8,y2=curve(d_q8,"tg")
a2.plot(ds,y1,"o-",color=F16,lw=2.6,ms=6,label="f16 KV (stock)")
a2.plot(ds8,y2,"o-",color=FIX,lw=2.8,ms=6,label="q8 KV + fixes")
a2.set_title(f"Decode  (+{y2[-1]/y1[-1]*100-100:.0f}% at 64k)"); a2.set_ylabel("decode tok/s (tg32)"); style(a2)
a2.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG)
fig.suptitle("Dense model too: Qwen2.5-7B — the FA dequant-once fix is not MoE-specific",fontsize=15,fontweight="bold")
fig.text(.5,.012,"Qwen2.5-7B-Instruct Q4_K_M (dense, head-dim 128) | "+FOOT,ha="center",color=MUT,fontsize=7.8)
fig.tight_layout(rect=[0,.04,1,.96]); fig.savefig(os.path.join(GRAPHS,"04_dense7b_f16_vs_q8.png")); plt.close(fig)

print("wrote:")
import os
for f in sorted(os.listdir(GRAPHS)): print("  ", os.path.join(GRAPHS, f))
