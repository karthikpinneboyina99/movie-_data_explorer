# =============================================================================
# Movie Data Explorer — TMDB 5000 Movies Dataset
# =============================================================================
# SETUP: Place tmdb_5000_movies.csv inside the  data/  folder before running.
# Download from: https://www.kaggle.com/datasets/tmdb/tmdb-movie-metadata
#
# Run:  python analysis.py
# Charts are saved to:  charts/
# =============================================================================

import os           # for creating directories
import json         # for parsing JSON columns (genres)
import pandas as pd                     # data manipulation
import matplotlib.pyplot as plt         # base plotting library
import matplotlib.ticker as mticker     # axis formatting helpers
import seaborn as sns                   # higher-level chart styling

# ---------------------------------------------------------------------------
# 0. Global chart style
# ---------------------------------------------------------------------------
sns.set_theme(style="darkgrid", palette="muted")   # consistent look for all charts
plt.rcParams["figure.dpi"] = 120                   # sharper output images

CHARTS_DIR = "charts"                              # folder that receives all PNGs
os.makedirs(CHARTS_DIR, exist_ok=True)             # create it if it doesn't exist yet

CSV_PATH = os.path.join("data", "tmdb_5000_movies.csv")   # expected location of the file

# ---------------------------------------------------------------------------
# 1. Load the dataset
# ---------------------------------------------------------------------------
print("=" * 60)
print("STEP 1 — Loading data")
print("=" * 60)

# Read the CSV into a DataFrame (a table-like structure)
df = pd.read_csv(CSV_PATH)

print(f"Rows loaded        : {len(df):,}")        # total rows before cleaning
print(f"Columns            : {list(df.columns)}")  # show all column names

# ---------------------------------------------------------------------------
# 2. Clean the data
# ---------------------------------------------------------------------------
print("\nSTEP 2 — Cleaning data")
print("=" * 60)

# --- 2a. Drop duplicate rows (same movie appearing more than once) ----------
before_dedup = len(df)                        # record count before
df.drop_duplicates(inplace=True)              # remove exact duplicate rows
print(f"Duplicates removed : {before_dedup - len(df)}")

# --- 2b. Fix data types -----------------------------------------------------
# release_date arrives as plain text; convert to a real date object
df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")

# Extract the year as an integer column — useful for the line chart later
df["release_year"] = df["release_date"].dt.year.astype("Int64")  # Int64 handles NaNs

# budget and revenue can sometimes load as objects; force them to numbers
df["budget"]  = pd.to_numeric(df["budget"],  errors="coerce")
df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")

# vote_average is the IMDb-style rating (0–10)
df["vote_average"] = pd.to_numeric(df["vote_average"], errors="coerce")

# --- 2c. Handle null values -------------------------------------------------
# Drop rows with no title — they are useless for analysis
df.dropna(subset=["title"], inplace=True)

# Replace missing numeric values with 0 (budget/revenue often missing, not truly NaN)
df[["budget", "revenue"]] = df[["budget", "revenue"]].fillna(0)

# Drop rows with no rating — we can't include them in rating analyses
df.dropna(subset=["vote_average"], inplace=True)

# --- 2d. Filter out obviously bad data --------------------------------------
# Movies with a rating of 0 usually have no votes — exclude them from rating charts
df_rated = df[df["vote_average"] > 0].copy()   # copy avoids SettingWithCopyWarning

# Movies where both budget AND revenue are 0 are unusable for the budget→revenue chart
df_money = df[(df["budget"] > 0) & (df["revenue"] > 0)].copy()

print(f"Rows after cleaning: {len(df):,}")
print(f"Rows with ratings  : {len(df_rated):,}")
print(f"Rows with $ data   : {len(df_money):,}")

# ---------------------------------------------------------------------------
# 3. Parse the  genres  column
# ---------------------------------------------------------------------------
# The genres column looks like:  [{"id": 28, "name": "Action"}, ...]
# We need to turn that JSON string into a Python list of genre names.

def extract_genre_names(json_str):
    """Return a list of genre name strings from a JSON-encoded genres cell."""
    try:
        items = json.loads(json_str)          # parse the JSON string into a list
        return [item["name"] for item in items]   # pull out just the 'name' field
    except (ValueError, TypeError):
        return []                              # return empty list if anything goes wrong

# Apply the function to every row in the genres column
df_rated["genre_list"] = df_rated["genres"].apply(extract_genre_names)

# "Explode" turns  ["Action", "Drama"]  into two separate rows, one per genre
df_exploded = df_rated.explode("genre_list")

# Drop rows where the genre ended up empty (movies with no genre info)
df_exploded = df_exploded[df_exploded["genre_list"].notna() & (df_exploded["genre_list"] != "")]

# ---------------------------------------------------------------------------
# 4. Analysis A — Top 10 genres by average rating
# ---------------------------------------------------------------------------
print("\nSTEP 3 — Top 10 genres by average rating")
print("=" * 60)

# Group by genre, average the ratings, keep only genres with at least 20 movies
genre_ratings = (
    df_exploded
    .groupby("genre_list")             # one group per genre
    .agg(
        avg_rating=("vote_average", "mean"),   # mean rating for each genre
        movie_count=("title", "count"),        # how many movies in each genre
    )
    .query("movie_count >= 20")        # filter out tiny genres (unreliable average)
    .sort_values("avg_rating", ascending=False)  # best genres first
    .head(10)                          # keep only the top 10
    .reset_index()                     # turn the index back into a normal column
)

print(genre_ratings.to_string(index=False))   # print the results table

# Draw a horizontal bar chart
fig, ax = plt.subplots(figsize=(10, 6))       # create a figure 10 inches wide, 6 tall

bars = ax.barh(
    genre_ratings["genre_list"],               # genre names on the y-axis
    genre_ratings["avg_rating"],               # rating values on the x-axis
    color=sns.color_palette("muted", 10),      # one colour per bar
)

# Add the exact rating value at the end of each bar
for bar, val in zip(bars, genre_ratings["avg_rating"]):
    ax.text(
        bar.get_width() + 0.02,                # position slightly beyond bar tip
        bar.get_y() + bar.get_height() / 2,    # vertically centred on bar
        f"{val:.2f}",                          # format to 2 decimal places
        va="center", fontsize=9,
    )

ax.set_xlabel("Average Rating (out of 10)")
ax.set_title("Top 10 Movie Genres by Average Rating", fontsize=14, fontweight="bold")
ax.set_xlim(0, genre_ratings["avg_rating"].max() + 0.5)  # leave room for labels
ax.invert_yaxis()                              # highest rating at the top

plt.tight_layout()                             # prevent labels from being clipped
chart_path = os.path.join(CHARTS_DIR, "01_top_genres_by_rating.png")
plt.savefig(chart_path)                        # save the chart as a PNG file
plt.close()                                    # free memory
print(f"Chart saved → {chart_path}")

# ---------------------------------------------------------------------------
# 5. Analysis B — Does budget affect revenue? (scatter plot)
# ---------------------------------------------------------------------------
print("\nSTEP 4 — Budget vs Revenue scatter plot")
print("=" * 60)

# Convert raw dollar amounts to millions so axis labels stay readable
df_money["budget_m"]  = df_money["budget"]  / 1_000_000
df_money["revenue_m"] = df_money["revenue"] / 1_000_000

fig, ax = plt.subplots(figsize=(10, 7))

# scatterplot with semi-transparent dots so dense clusters remain visible
ax.scatter(
    df_money["budget_m"],      # x-axis: budget in millions
    df_money["revenue_m"],     # y-axis: revenue in millions
    alpha=0.4,                 # 40% opacity to show point density
    edgecolors="none",         # no border on dots (cleaner look)
    color=sns.color_palette("muted")[0],
    s=20,                      # dot size
)

# Add a linear regression trend line to show the overall relationship
sns.regplot(
    x="budget_m", y="revenue_m",
    data=df_money,
    ax=ax,
    scatter=False,             # we already drew the scatter above
    color="crimson",           # make the trend line stand out
    line_kws={"linewidth": 2},
)

# Format axis labels in millions (e.g.  250 → "$250M")
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.0f}M"))
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"${y:.0f}M"))

ax.set_xlabel("Production Budget (millions USD)")
ax.set_ylabel("Box Office Revenue (millions USD)")
ax.set_title("Does Budget Affect Revenue?", fontsize=14, fontweight="bold")

# Annotate with the Pearson correlation coefficient
corr = df_money["budget_m"].corr(df_money["revenue_m"])   # correlation −1 to +1
ax.text(
    0.05, 0.92,                # position: 5% from left, 92% from bottom
    f"Pearson r = {corr:.2f}",
    transform=ax.transAxes,   # use axes-relative coordinates (0–1)
    fontsize=10,
    color="crimson",
)

plt.tight_layout()
chart_path = os.path.join(CHARTS_DIR, "02_budget_vs_revenue.png")
plt.savefig(chart_path)
plt.close()
print(f"Chart saved → {chart_path}")
print(f"Correlation (budget→revenue): {corr:.3f}")

# ---------------------------------------------------------------------------
# 6. Analysis C — How have movie ratings changed over the years? (line chart)
# ---------------------------------------------------------------------------
print("\nSTEP 5 — Ratings over time")
print("=" * 60)

# Keep only years with a reasonable sample size to avoid noisy averages
year_ratings = (
    df_rated
    .dropna(subset=["release_year"])                   # remove rows with no year
    .groupby("release_year")
    .agg(
        avg_rating=("vote_average", "mean"),           # mean rating per year
        movie_count=("title", "count"),                # movies released that year
    )
    .query("movie_count >= 10")                        # years with fewer than 10 movies are unreliable
    .query("release_year >= 1960")                     # focus on modern cinema era
    .reset_index()
)

fig, ax = plt.subplots(figsize=(12, 5))

# Main line: average rating per year
ax.plot(
    year_ratings["release_year"],
    year_ratings["avg_rating"],
    color=sns.color_palette("muted")[2],
    linewidth=2,
    label="Avg Rating",
)

# Shaded band: ±0.5 around the average to show rough spread
ax.fill_between(
    year_ratings["release_year"],
    year_ratings["avg_rating"] - 0.5,    # lower bound of band
    year_ratings["avg_rating"] + 0.5,    # upper bound of band
    alpha=0.2,                            # very transparent fill
    color=sns.color_palette("muted")[2],
    label="±0.5 band",
)

ax.set_xlabel("Release Year")
ax.set_ylabel("Average Rating (out of 10)")
ax.set_title("How Have Movie Ratings Changed Over the Years?", fontsize=14, fontweight="bold")
ax.legend()
ax.set_ylim(0, 10)                        # fix y-axis to the full rating range

plt.tight_layout()
chart_path = os.path.join(CHARTS_DIR, "03_ratings_over_years.png")
plt.savefig(chart_path)
plt.close()
print(f"Chart saved → {chart_path}")

# ---------------------------------------------------------------------------
# 7. Analysis D — Top 10 highest grossing movies of all time (bar chart)
# ---------------------------------------------------------------------------
print("\nSTEP 6 — Top 10 highest grossing movies")
print("=" * 60)

# Sort all movies by revenue, pick the top 10
top10_revenue = (
    df[df["revenue"] > 0]             # exclude movies with no revenue data
    .sort_values("revenue", ascending=False)
    .head(10)
    [["title", "revenue", "release_year"]]   # keep only the columns we need
    .reset_index(drop=True)
)

# Revenue in billions makes the axis labels much cleaner
top10_revenue["revenue_b"] = top10_revenue["revenue"] / 1_000_000_000

print(top10_revenue[["title", "revenue_b", "release_year"]].to_string(index=False))

fig, ax = plt.subplots(figsize=(12, 6))

# Colour-code each bar by its decade
decade_colors = {1980: "#4C72B0", 1990: "#55A868", 2000: "#C44E52",
                 2010: "#8172B2", 2020: "#937860"}

bar_colors = [
    decade_colors.get((int(y) // 10) * 10, "#64B5CD")
    for y in top10_revenue["release_year"].fillna(0)
]

bars = ax.bar(
    range(len(top10_revenue)),         # numeric x positions
    top10_revenue["revenue_b"],        # bar heights (revenue in billions)
    color=bar_colors,
)

# Replace numeric x ticks with the actual movie titles, rotated for readability
ax.set_xticks(range(len(top10_revenue)))
ax.set_xticklabels(
    top10_revenue["title"],
    rotation=30,           # tilt 30° so long titles don't overlap
    ha="right",            # align the right end of text to the tick mark
    fontsize=9,
)

# Label each bar with its revenue value
for bar, val in zip(bars, top10_revenue["revenue_b"]):
    ax.text(
        bar.get_x() + bar.get_width() / 2,   # horizontally centred on bar
        bar.get_height() + 0.03,             # just above the bar top
        f"${val:.2f}B",                      # e.g.  $2.79B
        ha="center", va="bottom", fontsize=8,
    )

ax.set_ylabel("Box Office Revenue (billions USD)")
ax.set_title("Top 10 Highest Grossing Movies of All Time", fontsize=14, fontweight="bold")
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda y, _: f"${y:.1f}B"))

plt.tight_layout()
chart_path = os.path.join(CHARTS_DIR, "04_top10_grossing_movies.png")
plt.savefig(chart_path)
plt.close()
print(f"Chart saved → {chart_path}")

# ---------------------------------------------------------------------------
# 8. Print summary of key insights
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("KEY INSIGHTS SUMMARY")
print("=" * 60)

# Insight 1 — best-rated genre
best_genre      = genre_ratings.iloc[0]["genre_list"]
best_genre_rate = genre_ratings.iloc[0]["avg_rating"]
print(f"1. Best-rated genre   : {best_genre} (avg {best_genre_rate:.2f}/10)")

# Insight 2 — budget↔revenue correlation
strength = "strong" if abs(corr) >= 0.6 else ("moderate" if abs(corr) >= 0.3 else "weak")
direction = "positive" if corr > 0 else "negative"
print(f"2. Budget→Revenue     : {strength} {direction} correlation (r={corr:.2f})")
print(f"   → Higher budgets generally {'do' if corr > 0.5 else 'do not strongly'} predict higher revenue.")

# Insight 3 — rating trend
first_decade_avg = year_ratings[year_ratings["release_year"] <= 1970]["avg_rating"].mean()
last_decade_avg  = year_ratings[year_ratings["release_year"] >= 2010]["avg_rating"].mean()
trend = "risen" if last_decade_avg > first_decade_avg else "fallen"
print(f"3. Rating trend       : Avg rating has {trend} from "
      f"{first_decade_avg:.2f} (≤1970) to {last_decade_avg:.2f} (≥2010)")

# Insight 4 — biggest blockbuster
top_movie   = top10_revenue.iloc[0]["title"]
top_revenue = top10_revenue.iloc[0]["revenue_b"]
print(f"4. Highest grossing   : {top_movie} (${top_revenue:.2f}B)")

# Insight 5 — dataset overview
print(f"5. Dataset size       : {len(df):,} movies after cleaning")
print(f"   Date range         : {int(df_rated['release_year'].min())} – "
      f"{int(df_rated['release_year'].max())}")

print("\nAll 4 charts saved to the  charts/  folder.")
print("=" * 60)
