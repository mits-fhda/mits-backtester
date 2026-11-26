"""Charts for a backtest.

Each chart function builds and returns a matplotlib Figure (so the web app can
show it), and also saves it as a PNG when given a `path` (for the command line).
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw straight to files; no window needed (works on servers too)
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

# One small, consistent color scheme for every chart.
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED_TEXT = "#52514e"
GRID = "#e4e3df"
PRICE_COLOR = "#8a8984"
SHORT_COLOR = "#2a78d6"     # blue
LONG_COLOR = "#eb6834"      # orange
STRATEGY_COLOR = "#2a78d6"  # blue
BUYHOLD_COLOR = "#eb6834"   # orange
IN_MARKET_FILL = "#2a78d6"


def _style_axes(ax):
    """Quiet axes so the data stands out: light grid, no top/right border."""
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED_TEXT, labelsize=9)


def _finish(fig, path):
    """Tidy the layout, save to `path` if one was given, and return the figure."""
    fig.tight_layout()
    if path is not None:
        fig.savefig(path, dpi=150, facecolor=SURFACE)
    return fig


def _label_line_end(ax, series, text, color):
    """Write a label just to the right of the last point of a line."""
    ax.annotate(
        text,
        xy=(series.index[-1], series.iloc[-1]),
        xytext=(6, 0),
        textcoords="offset points",
        va="center",
        fontsize=9,
        color=TEXT,
        bbox=dict(boxstyle="round,pad=0.2", fc=SURFACE, ec=color, lw=1),
    )


def plot_price_and_signals(signals, results, short_window, long_window, title, path=None):
    """Chart (a): price with both moving averages; shaded areas = strategy holds the stock."""
    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor=SURFACE)
    _style_axes(ax)

    ax.plot(signals.index, signals["Price"], color=PRICE_COLOR, lw=1.2, label="Price")
    ax.plot(signals.index, signals["SMA_short"], color=SHORT_COLOR, lw=2,
            label=f"{short_window}-day average")
    ax.plot(signals.index, signals["SMA_long"], color=LONG_COLOR, lw=2,
            label=f"{long_window}-day average")

    in_market = results["Position"] == 1
    ax.fill_between(results.index, 0, 1, where=in_market, transform=ax.get_xaxis_transform(),
                    color=IN_MARKET_FILL, alpha=0.07, lw=0, label="Strategy holds the stock")

    ax.set_title(title, loc="left", fontsize=13, color=TEXT, pad=12)
    ax.set_ylabel("Price ($)", color=MUTED_TEXT)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=TEXT)

    return _finish(fig, path)


def plot_equity_curves(results, initial_capital, title, path=None):
    """Chart (b): growth of the starting capital, strategy vs. buy-and-hold."""
    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor=SURFACE)
    _style_axes(ax)

    strategy = results["Strategy_Equity"]
    buy_hold = results["BuyHold_Equity"]
    ax.plot(strategy.index, strategy, color=STRATEGY_COLOR, lw=2, label="Strategy")
    ax.plot(buy_hold.index, buy_hold, color=BUYHOLD_COLOR, lw=2, label="Buy and hold")
    ax.axhline(initial_capital, color=MUTED_TEXT, lw=0.8, ls="--")

    _label_line_end(ax, strategy, f"${strategy.iloc[-1]:,.0f}", STRATEGY_COLOR)
    _label_line_end(ax, buy_hold, f"${buy_hold.iloc[-1]:,.0f}", BUYHOLD_COLOR)

    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))
    ax.set_title(title, loc="left", fontsize=13, color=TEXT, pad=12)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=TEXT)
    ax.margins(x=0.08)  # room on the right for the end labels

    return _finish(fig, path)


def plot_results(signals, results, short_window, long_window, initial_capital,
                 name="Stock", output_dir="output"):
    """Create both charts and return the paths of the saved PNG files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    price_path = output_dir / f"{name}_price_moving_averages.png"
    equity_path = output_dir / f"{name}_equity_curve.png"

    price_fig = plot_price_and_signals(
        signals, results, short_window, long_window,
        title=f"{name}: price with {short_window}/{long_window}-day moving averages",
        path=price_path,
    )
    equity_fig = plot_equity_curves(
        results, initial_capital,
        title=f"{name}: growth of ${initial_capital:,.0f}, strategy vs. buy and hold",
        path=equity_path,
    )
    plt.close(price_fig)   # free the memory once the files are saved
    plt.close(equity_fig)
    return price_path, equity_path


def plot_monte_carlo_paths(simulations, initial_capital, years, title, path=None):
    """Fan chart: the range of simulated outcomes over time for each strategy.

    Dark band = middle 50% of paths (25th-75th percentile),
    light band = middle 90% (5th-95th), line = median path.
    """

    fig, axes = plt.subplots(1, 2, figsize=(11, 5), sharey=True, facecolor=SURFACE)
    colors = {"Strategy": STRATEGY_COLOR, "Buy & Hold": BUYHOLD_COLOR}

    for ax, (name, sim) in zip(axes, simulations.items()):
        _style_axes(ax)
        equity = sim["equity"]
        x = np.linspace(0, years, equity.shape[1])
        p5, p25, p50, p75, p95 = np.percentile(equity, [5, 25, 50, 75, 95], axis=0)
        color = colors[name]

        ax.fill_between(x, p5, p95, color=color, alpha=0.15, lw=0, label="5th–95th percentile")
        ax.fill_between(x, p25, p75, color=color, alpha=0.30, lw=0, label="25th–75th percentile")
        ax.plot(x, p50, color=color, lw=2, label="Median")
        ax.axhline(initial_capital, color=MUTED_TEXT, lw=0.8, ls="--")

        ax.annotate(f"${p50[-1]:,.0f}", xy=(x[-1], p50[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=TEXT)
        ax.set_title(name, loc="left", fontsize=11, color=TEXT)
        ax.set_xlabel("Years", color=MUTED_TEXT)
        ax.set_xlim(0, years * 1.15)  # room on the right for the end label
        ax.legend(loc="upper left", frameon=False, fontsize=8, labelcolor=TEXT)

    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:,.0f}"))
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, color=TEXT)
    return _finish(fig, path)


def plot_monte_carlo_drawdowns(simulations, title, path=None):
    """Histogram of each simulated path's worst drawdown."""

    fig, ax = plt.subplots(figsize=(11, 5), facecolor=SURFACE)
    _style_axes(ax)
    colors = {"Strategy": STRATEGY_COLOR, "Buy & Hold": BUYHOLD_COLOR}

    all_drawdowns = np.concatenate([sim["max_drawdown"] for sim in simulations.values()])
    bins = np.linspace(all_drawdowns.min(), 0, 40)

    for name, sim in simulations.items():
        drawdowns = sim["max_drawdown"]
        median = np.median(drawdowns)
        ax.hist(drawdowns, bins=bins, histtype="stepfilled", alpha=0.25, color=colors[name])
        ax.hist(drawdowns, bins=bins, histtype="step", lw=2, color=colors[name],
                label=f"{name} (median {median:.0%})")
        ax.axvline(median, color=colors[name], lw=1.5, ls="--")

    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:.0%}"))
    ax.set_xlabel("Worst peak-to-trough drop in each simulated path", color=MUTED_TEXT)
    ax.set_ylabel("Number of paths", color=MUTED_TEXT)
    ax.set_title(title, loc="left", fontsize=13, color=TEXT, pad=12)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=TEXT)

    return _finish(fig, path)


def plot_monte_carlo(simulations, initial_capital, years, num_paths,
                     name="Stock", output_dir="output"):
    """Create both Monte Carlo charts and return the paths of the saved PNG files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths_path = output_dir / f"{name}_monte_carlo_paths.png"
    drawdowns_path = output_dir / f"{name}_monte_carlo_drawdowns.png"

    paths_fig = plot_monte_carlo_paths(
        simulations, initial_capital, years,
        title=f"{name}: {num_paths:,} simulated {years}-year paths for ${initial_capital:,.0f}",
        path=paths_path,
    )
    drawdowns_fig = plot_monte_carlo_drawdowns(
        simulations,
        title=f"{name}: distribution of max drawdowns across {num_paths:,} simulations",
        path=drawdowns_path,
    )
    plt.close(paths_fig)
    plt.close(drawdowns_fig)
    return paths_path, drawdowns_path


def plot_sweep_heatmap(sweep_table, buy_hold_sharpe, highlight=None, title="", path=None):
    """Grid of Sharpe ratios for every (short, long) window pair.

    Color shows how each pair compares with buy-and-hold's Sharpe ratio:
    blue = better, orange = worse, gray = about the same. The number in each
    cell is the Sharpe ratio itself. `highlight` = (short, long) to outline.
    """
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from matplotlib.patches import Rectangle

    grid = sweep_table.pivot(index="Short", columns="Long", values="Sharpe Ratio")
    difference = grid - buy_hold_sharpe

    colormap = LinearSegmentedColormap.from_list(
        "worse_same_better", [BUYHOLD_COLOR, "#e9e8e4", STRATEGY_COLOR]
    )
    spread = max(abs(difference.min().min()), abs(difference.max().max()), 0.05)
    norm = TwoSlopeNorm(vcenter=0, vmin=-spread, vmax=spread)

    fig, ax = plt.subplots(figsize=(8, 5.5), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    image = ax.imshow(difference.to_numpy(), cmap=colormap, norm=norm, aspect="auto")

    # Write the Sharpe ratio in every cell (blank where short >= long).
    for row, short in enumerate(grid.index):
        for col, long in enumerate(grid.columns):
            value = grid.loc[short, long]
            if np.isnan(value):
                continue
            strong = abs(difference.loc[short, long]) > spread * 0.6
            ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=10,
                    color="white" if strong else TEXT)

    if highlight in [(s, l) for s in grid.index for l in grid.columns]:
        row, col = list(grid.index).index(highlight[0]), list(grid.columns).index(highlight[1])
        ax.add_patch(Rectangle((col - 0.5, row - 0.5), 1, 1, fill=False, ec=TEXT, lw=2.5))

    ax.set_xticks(range(len(grid.columns)), labels=grid.columns)
    ax.set_yticks(range(len(grid.index)), labels=grid.index)
    ax.set_xlabel("Long window (days)", color=MUTED_TEXT)
    ax.set_ylabel("Short window (days)", color=MUTED_TEXT)
    ax.tick_params(colors=MUTED_TEXT, length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    colorbar = fig.colorbar(image, ax=ax, shrink=0.85)
    colorbar.set_label(f"Sharpe minus buy & hold ({buy_hold_sharpe:.2f})", color=MUTED_TEXT)
    colorbar.outline.set_visible(False)
    colorbar.ax.tick_params(colors=MUTED_TEXT, labelsize=8)

    ax.set_title(title, loc="left", fontsize=12, color=TEXT, pad=12)
    return _finish(fig, path)
