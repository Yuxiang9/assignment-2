# fine-totals

<!-- Copied from tasks/fine-totals/task.json. This is the prompt the three fixed agents
     were given, so do NOT reword it: check-submission holds both your runs
     and this file to the descriptor's wording. Add what your verifier needs
     under the heading below instead. -->

Using matplotlib, read fines.csv and draw a vertical bar chart of the total library fines actually collected by each branch. The file has a header row and the columns branch, weekday, amount, waived. Compute the totals like this:
1. Keep only the rows whose waived column is exactly "no"; waived fines were never collected and must not be counted.
2. Sum the amount column within each branch.
Draw one vertical bar per branch on a single set of axes, with the branches ordered from left to right in DESCENDING order of their collected total (largest total leftmost). The y axis must start at zero. Set the title to exactly "Collected fines by branch", label the x axis "Branch", and label the y axis "Fines collected (USD)". Save the figure as figure.png.

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
   no manual steps. It must compute the totals by reading `fines.csv`
   rather than hard-coding them, and it must render the same image every
   time it runs.
2. **`/app/figure.png`** - the chart, as saved by that script.
3. **`/app/plotted_values.json`** - the values shown in the chart. Generate this
   file from the same variables used to draw the figure. Part 3 requires this
   sidecar because the verifier cannot reliably recover exact values from the
   PNG. It must contain
   one JSON object with exactly four keys, the branch names `Central`,
   `Eastside`, `Harborview` and `Northgate`. Each value must be that branch's
   collected (non-waived) fine total in USD as a JSON number, with no unit
   suffix or thousands separator. For example:
   `{"Central": 0.0, "Eastside": 0.0, "Harborview": 0.0, "Northgate": 0.0}`.

Do not modify `fines.csv`.

Only the libraries already installed are available and there is no network
access; everything you need is in the image.
