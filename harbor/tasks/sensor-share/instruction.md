# sensor-share

<!-- Copied from tasks/sensor-share/task.json. This is the prompt the three fixed agents
     were given, so do NOT reword it: check-submission holds both your runs
     and this file to the descriptor's wording. Add what your verifier needs
     under the heading below instead. -->

Using matplotlib, read readings.csv and draw a horizontal bar chart showing each site's share of all readings, as a percentage. The file has a header row and the columns site, reading; a site appears on several rows. Compute the shares like this:
1. Sum the reading column within each site.
2. Divide each site's sum by the grand total of all readings and multiply by 100 to get a percentage. The four percentages must add up to 100.
Draw one horizontal bar per site on a single set of axes, with the sites ordered ALPHABETICALLY from top to bottom (Alder at the top, then Birch, Cedar, Dogwood below it). The x axis must start at zero and be labeled exactly "Share of total readings (%)". Label the y axis "Site". Write each bar's percentage at the end of the bar, formatted with exactly one decimal place followed by a percent sign (for example "17.5%"). Set the title to exactly "Share of readings by site". Save the figure as figure.png.

## Required outputs

Leave these behind in `/app`, which is also the working directory. In
`plot.py`, refer to these files by bare filename rather than by absolute
path: the grader re-runs the script in a copied workspace, so an absolute
output path would point outside that copy.

Saving extra images is allowed -- an exploratory chart does no harm, and the
answer is graded from the figure saved as `figure.png`. Give any extra image a
different *stem*: a second save named `figure.<anything>` collides with the
graded one.

1. **`/app/plot.py`** - the plotting script. Self-contained and re-runnable:
   `python plot.py` from `/app` must reproduce the figure with no arguments and
   no manual steps. It must compute the shares by reading `readings.csv`
   rather than hard-coding them, and it must render the same image every
   time it runs.
2. **`/app/figure.png`** - the chart, as saved by that script.
3. **`/app/plotted_values.json`** - the values shown in the chart. Generate this
   file from the same variables used to draw the figure. Part 3 requires this
   sidecar because the verifier cannot reliably recover exact values from the
   PNG. It must contain
   one JSON object with exactly four keys, the site names `Alder`, `Birch`,
   `Cedar` and `Dogwood`. Each value must be that site's percentage share of
   the total readings as a JSON number between 0 and 100 (the value the bar
   shows, not the raw sum), with no percent sign. For example:
   `{"Alder": 0.0, "Birch": 0.0, "Cedar": 0.0, "Dogwood": 0.0}`.

Do not modify `readings.csv`.

Only the libraries already installed are available and there is no network
access; everything you need is in the image.
