# weighted-latency

<!-- Copied from tasks/weighted-latency/task.json. This is the prompt the three fixed agents
     were given, so do NOT reword it: check-submission holds both your runs
     and this file to the descriptor's wording. Add what your verifier needs
     under the heading below instead. -->

Using matplotlib, draw a vertical bar chart of the request-weighted mean latency of four backend services. Each service serves two regions; for each region you are given the number of requests and that region's mean latency in milliseconds:
  auth:     region A 100 requests at 120 ms, region B 300 requests at 80 ms
  search:   region A 250 requests at 60 ms,  region B 250 requests at 100 ms
  checkout: region A 50 requests at 200 ms,  region B 450 requests at 40 ms
  media:    region A 400 requests at 150 ms, region B 100 requests at 50 ms
For each service compute the REQUEST-WEIGHTED mean latency: multiply each region's latency by its request count, add the two products, and divide by the service's total request count. Do not use the plain average of the two regional latencies.
Draw one vertical bar per service on a single set of axes, in exactly this order from left to right: auth, search, checkout, media. Write each bar's value above the bar, formatted with exactly one decimal place (for example "90.0"). The y axis must start at zero. Set the title to exactly "Request-weighted mean latency by service", label the x axis "Service", and label the y axis "Latency (ms)". Save the figure as figure.png.

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
   one JSON object with exactly four keys, the service names `auth`, `search`,
   `checkout` and `media`. Each value must be that service's request-weighted
   mean latency in milliseconds as a JSON number, with no unit suffix. For
   example: `{"auth": 0.0, "search": 0.0, "checkout": 0.0, "media": 0.0}`.

Do not modify or delete any file you did not create.

Only the libraries already installed are available and there is no network
access; everything you need is in the image.
