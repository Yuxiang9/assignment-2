# stage-attendance

<!-- Copied from tasks/stage-attendance/task.json. This is the prompt the three fixed agents
     were given, so do NOT reword it: check-submission holds both your runs
     and this file to the descriptor's wording. Add what your verifier needs
     under the heading below instead. -->

Using matplotlib, draw a vertical bar chart of peak attendance at the twelve stages of a music festival. Use exactly these stages, in exactly this order from left to right, with these attendance counts:
  Whispering Pines Amphitheater: 4200
  Golden Meadow Pavilion: 3100
  Riverbend Acoustic Grove: 2650
  Starlight Terrace: 5300
  Thundering Falls Main Stage: 8900
  Lantern District Bandshell: 1900
  Cedar Hollow Sessions Tent: 2300
  Aurora Fields Dance Dome: 6100
  Harborlight Jazz Corner: 1450
  Mossy Knoll Folk Circle: 990
  Ironworks Underground Hall: 3750
  Sunset Dunes Beach Stage: 4800
Draw one vertical bar per stage on a single set of axes. Use each stage's FULL name, exactly as written above, as its x tick label; do not abbreviate or truncate any name. Rotate the x tick labels 45 degrees and anchor them right-aligned so neighbouring labels do not overlap. Every tick label, the title, and both axis labels must be completely visible inside the saved image: no text may be cut off by the image edge (make the figure large enough, at least 14 by 6 inches, and lay it out so nothing is clipped). The y axis must start at zero. Set the title to exactly "Peak attendance by stage", label the x axis "Stage", and label the y axis "Peak attendance". Save the figure as figure.png.

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
   one JSON object with exactly twelve keys: the full stage names exactly as
   written in the task above. Each value must be that stage's peak attendance
   as a JSON number. For example: `{"Whispering Pines Amphitheater": 0,
   "Golden Meadow Pavilion": 0, ...}` with one entry per stage.

Do not modify or delete any file you did not create.

Only the libraries already installed are available and there is no network
access; everything you need is in the image.
