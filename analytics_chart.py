import bar_chart_race as bcr  # python -m pip install git+https://github.com/dexplo/bar_chart_race
import pandas as pd

df = pd.read_csv("analytics_processed.csv", index_col=0)
bcr.bar_chart_race(df, 'players_june.mp4', title="Playtime in minutes (March-June)", n_bars=20, steps_per_period=2,
                   period_length=40, filter_column_colors=True, colors='dark12', bar_kwargs={'alpha': .7},
                   fig_kwargs={'figsize': (6, 3.5), 'dpi': 144})
