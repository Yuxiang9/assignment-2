# city-temps

<!-- Copied from tasks/city-temps/task.json. This is the prompt the three fixed agents
     were given, so do NOT reword it: check-submission holds both your runs
     and this file to the descriptor's wording. Add what your verifier needs
     under the heading below instead. -->

Using matplotlib, draw a line chart of monthly mean temperature for six cities over one calendar year, all on a single set of axes. The twelve values for each city are for January through December, in degrees Celsius:
  Aluna:    2, 3, 7, 12, 17, 21, 24, 23, 19, 13, 7, 3
  Brinport: -5, -3, 2, 8, 14, 19, 22, 21, 15, 8, 1, -4
  Calder:   10, 11, 13, 16, 19, 23, 26, 26, 23, 18, 13, 10
  Dunmore:  16, 16, 17, 18, 20, 22, 24, 25, 24, 21, 18, 16
  Eastwick: -12, -10, -4, 3, 10, 16, 19, 17, 11, 4, -4, -10
  Farrow:   21, 22, 22, 23, 23, 24, 25, 25, 24, 23, 22, 21
Draw one line per city with circular markers at each monthly point. Use exactly these line colours so every city is distinguishable: Aluna "tab:blue", Brinport "tab:orange", Calder "tab:green", Dunmore "tab:red", Eastwick "tab:purple", Farrow "tab:brown". The x axis must show all twelve month abbreviations Jan, Feb, Mar, Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec as tick labels. Add a legend listing every city by name; place the legend OUTSIDE the plotting area, to the right of the axes, so that it does not cover any data line, and make sure the legend is still completely visible inside the saved image. Set the title to exactly "Monthly mean temperature by city", label the x axis "Month", and label the y axis "Temperature (deg C)". Save the figure as figure.png.

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
   no manual steps. It must compute the plotted values from the data given in
   the task above, and it must render the same image every time it runs.
2. **`/app/figure.png`** - the chart, as saved by that script.
3. **`/app/plotted_values.json`** - the values shown in the chart. Generate this
   file from the same variables used to draw the figure. Part 3 requires this
   sidecar because the verifier cannot reliably recover exact values from the
   PNG. It must contain
   one JSON object with exactly six keys, the city names `Aluna`, `Brinport`,
   `Calder`, `Dunmore`, `Eastwick` and `Farrow`. Each value must be an array
   of exactly twelve JSON numbers: that city's monthly mean temperatures in
   degrees Celsius, January through December, in order. For example:
   `{"Aluna": [0,0,0,0,0,0,0,0,0,0,0,0], ...}` with one entry per city.

Do not modify or delete any file you did not create.

Only the libraries already installed are available and there is no network
access; everything you need is in the image.
