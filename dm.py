import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, Circle, Polygon
plt.rcParams["font.family"] = "DejaVu Sans"
BLUE, BLUEF = "#1F4E79", "#DCE9F5"; GREEN = "#E2F0D9"; YEL = "#FFF2CC"; GREY = "#F4F4F4"; RED = "#F8D7DA"; ORG = "#FCE4D6"
def fig(w, h):
    f = plt.figure(figsize=(w, h), dpi=200); ax = f.add_axes([0, 0, 1, 1]); ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); return f, ax
def box(ax, x, y, w, h, text="", fc=BLUEF, ec=BLUE, fs=8, bold=False, ls="-", lw=1.1, rounding=0.06, color="#111", z=2, va="center", ha="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rounding}", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
    if text:
        tx = x + w / 2 if ha == "center" else x + 0.08
        ax.text(tx, y + h / 2 if va == "center" else y + h - 0.08, text, ha=ha, va=va, fontsize=fs, fontweight="bold" if bold else "normal", color=color, zorder=z + 1, linespacing=1.25)
    return (x, y, w, h)
def cluster(ax, x, y, w, h, label, ec=BLUE, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc="none", ec=ec, lw=1.2, ls=(0, (5, 3)), zorder=1))
    ax.text(x + 0.1, y + h - 0.07, label, ha="left", va="top", fontsize=fs, color=ec, fontweight="bold", zorder=1)
def cx(b): return b[0] + b[2] / 2
def cy(b): return b[1] + b[3] / 2
def side(b, s, t=0.5):
    x, y, w, h = b
    return {"l": (x, y + h * t), "r": (x + w, y + h * t), "t": (x + w * t, y + h), "b": (x + w * t, y)}[s]
def arrow(ax, p, q, label=None, style="-|>", ls="-", color="#333", lw=1.0, fs=7, lt=0.5, loff=(0, 0.07), rad=0.0, both=False, ha="center", z=4, bg=True):
    st = "<|-|>" if both else style
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle=st, color=color, lw=lw, ls=ls, shrinkA=0, shrinkB=0, mutation_scale=9, connectionstyle=f"arc3,rad={rad}"), zorder=z)
    if label:
        mx, my = p[0] + (q[0] - p[0]) * lt + loff[0], p[1] + (q[1] - p[1]) * lt + loff[1]
        ax.text(mx, my, label, ha=ha, va="center", fontsize=fs, color="#222", zorder=z + 1, linespacing=1.15,
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9) if bg else None)
def save(f, name): f.savefig(f"img/{name}.png", dpi=200, facecolor="white"); plt.close(f)
def actor(ax, x, y, label, fs=8, ext=False):
    c = "#7F6000" if ext else "#222"
    ax.add_patch(Circle((x, y + 0.42), 0.09, fc="white", ec=c, lw=1.1, zorder=3))
    for xs, ys in [((x, x), (y + 0.33, y + 0.08)), ((x - 0.17, x + 0.17), (y + 0.25, y + 0.25)), ((x, x - 0.14), (y + 0.08, y - 0.12)), ((x, x + 0.14), (y + 0.08, y - 0.12))]:
        ax.plot(xs, ys, color=c, lw=1.1, zorder=3)
    ax.text(x, y - 0.2, label, ha="center", va="top", fontsize=fs, color=c, linespacing=1.15)
def uc(ax, x, y, text, w=2.5, h=0.56, fs=7.5, fc="#FFFFFF"):
    ax.add_patch(Ellipse((x, y), w, h, fc=fc, ec=BLUE, lw=1.1, zorder=3)); ax.text(x, y, text, ha="center", va="center", fontsize=fs, zorder=4, linespacing=1.15); return (x, y, w, h)
