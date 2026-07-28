#!/usr/bin/env python3
# Graph 05: production config (-ub 2048) prefill vs depth, three KV types + pre-PR stock reference.
# Data: ../results/ub2048_contig_coder30b_{f16,q8,q4}.md (build 74434c3)
#     + ../results/ub2048_prepr_coder30b_f16.md (stock upstream master 8161641, canonical glslc).
import re, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

BG="#0d1117"; FG="#e6edf3"; GRID="#30363d"; MUT="#8b949e"
F16="#58a6ff"; FIX="#3fb950"; Q4="#a371f7"; PUB="#d29922"
plt.rcParams.update({
    "figure.facecolor":BG,"axes.facecolor":BG,"savefig.facecolor":BG,
    "text.color":FG,"axes.labelcolor":FG,"xtick.color":MUT,"ytick.color":MUT,
    "axes.edgecolor":GRID,"grid.color":GRID,"font.size":12,
    "axes.titlesize":15,"axes.titleweight":"bold","figure.dpi":170,
})
FOOT="Radeon 8060S (gfx1151, RDNA3.5) | Mesa 26.3.0-devel, canonical glslc (shaderc v2026.3-dev) | -b 2048 -ub 2048 -p 2048, -fa 1, r=3, amd_iommu=off | measured, not projected"

HERE=os.path.dirname(os.path.abspath(__file__)); RES=os.path.join(HERE,"..","results")

def parse(path):
    out={}
    for ln in open(path):
        if "|" not in ln or "pp" not in ln: continue
        cells=[c.strip() for c in ln.split("|")]
        test=next((c for c in cells if re.match(r"pp\d+",c)),None)
        if not test: continue
        val=cells[-2] if cells[-1]=="" else cells[-1]
        m=re.search(r"([\d.]+)",val.split("±")[0])
        if not m: continue
        md=re.search(r"@ d(\d+)",test); d=int(md.group(1)) if md else 0
        out[d]=float(m.group(1))
    return out

def curve(d):
    ds=sorted(d); return ds,[d[k] for k in ds]

f16=parse(f"{RES}/ub2048_contig_coder30b_f16.md")
q8 =parse(f"{RES}/ub2048_contig_coder30b_q8.md")
q4 =parse(f"{RES}/ub2048_contig_coder30b_q4.md")
pre=parse(f"{RES}/ub2048_prepr_coder30b_f16.md")

fig,ax=plt.subplots(figsize=(9.5,5.4))
for dat,c,mk,lbl,lw in [(f16,F16,"o","f16 KV",2.8),(q8,FIX,"s","q8_0 KV",2.4),(q4,Q4,"^","q4_0 KV",2.4)]:
    ds,y=curve(dat); ax.plot(ds,y,mk+"-",color=c,lw=lw,ms=7,label=lbl)
ds,y=curve(pre); ax.plot(ds,y,"X--",color=PUB,lw=1.8,ms=8,alpha=.85,label="pre-PR master, stock (f16)")
r=f16[65536]/pre[65536]
ax.annotate(f"{r:.2f}x vs stock\nat 64k",(65536,f16[65536]),xytext=(-86,30),textcoords="offset points",
    color=FIX,fontweight="bold",fontsize=12.5,ha="center",
    arrowprops=dict(arrowstyle="->",color=FIX,lw=1.4))

# headline at d0 and the convergence note at depth
ax.annotate("1631 t/s at d0\n(+39% vs ub512, same prompt)",(0,f16[0]),xytext=(26,-34),textcoords="offset points",
    color=F16,fontweight="bold",fontsize=12.5,
    arrowprops=dict(arrowstyle="->",color=F16,lw=1.4))
ax.annotate("all three KV types\nwithin 1% at every depth",(16384,q4[16384]),xytext=(40,36),
    textcoords="offset points",color=MUT,fontsize=10.5)

ax.set_title("Production config (-ub 2048): KV type no longer affects prefill")
ax.set_ylabel("prefill throughput (tok/s, pp2048)")
ax.grid(True,alpha=.3,lw=.7); [s.set_visible(False) for s in (ax.spines['top'],ax.spines['right'])]
ax.set_xticks([0,8192,16384,32768,65536])
ax.xaxis.set_major_formatter(FuncFormatter(lambda x,_: f"{int(x/1024)}k" if x>=1024 else "0"))
ax.set_xlabel("context depth (tokens)")
ax.legend(facecolor=BG,edgecolor=GRID,labelcolor=FG,loc="upper right")
fig.text(.5,.030,"Qwen3-Coder-30B-A3B (Q6_K, head-dim 128) | solid = this stack (74434c3) | dashed = stock upstream master 8161641, no fixes (see PROVENANCE)",ha="center",color=MUT,fontsize=8.0)
fig.text(.5,.010,FOOT,ha="center",color=MUT,fontsize=7.0)
fig.tight_layout(rect=[0,.055,1,1])
out=os.path.join(HERE,"..","..","graphs","05_coder30b_ub2048_kvtypes.png")
fig.savefig(out); print("wrote",out,os.path.getsize(out)//1024,"KB")
