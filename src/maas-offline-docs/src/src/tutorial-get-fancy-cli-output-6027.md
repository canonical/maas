> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/get-fancy-cli-output" target = "_blank">Let us know.</a>*

The MAAS CLI emits JSON data, which while information-rich, can become cumbersome to sift through, especially when dealing with lists of machines. The `jq` utility emerges as a lifeline, offering robust capabilities for filtering and formatting JSON data directly on the command line.

In this tutorial, we'll journey through essential `jq` functionalities—key selection, array manipulation, and interplay with other CLI tools to transform raw MAAS JSON into neat, analysable tabular output.

## Single key selection

To focus on the `hostname` field for each machine, run the following command:

```nohighlight
maas machines read | jq '.[].hostname'
```
Here, `jq` navigates through each machine in the array (.[]) and picks the `hostname` field.

## Multiple key selection

To fetch multiple keys, such as `hostname` and `status_name`, use:

```nohighlight
maas machines read | jq '.[].hostname, .[].status_name'
```
This will produce output resembling:

```nohighlight
[
	"vm-1",
    "Deployed"
]
[
    "vm-2", 
    "Ready"
]
```

## Basic tables

Utilise the `@tsv` filter to transform JSON arrays into tab-separated values:

```nohighlight
maas machines read | jq -r '.[].hostname, .[].status_name | @tsv'
```
	
Use `-r` to output raw text (devoid of quotes).

## Aligned columns

For better readability, pipe the output to `column -t`:

```nohighlight
maas machines read | jq -r '.[].hostname, .[].status_name | @tsv' | column -t
```

```nohighlight
vm-1       Deployed
vm-2       Ready
```

## Basic headers

Prepend a literal array to `jq` to introduce column headings:

```nohighligh
maas machines read | jq -r '["HOSTNAME", "STATUS"], (.[] | [.hostname, .status_name]) | @tsv' | column -t
```

## Divider rows

Create a separating line between headers and data:

```nohighlight
maas machines read | jq -r '["HOSTNAME", "STATUS"] | (.[], map(length*"-")), (.[] | [.hostname, .status_name]) | @tsv' | column -t
```

## Sorting rows

To sort the output, append `sort -k 1` to the pipeline:

```nohighlight
... | sort -k 1 
```

## Filtering

To sieve out machines by their status, use `select()`:

```nohighlight
... | jq 'select(.status_name == "Ready")'
```

This opens doors for more complex text processing through chaining CLI tools.

## Small + powerful

This tutorial has armed you with practical skills to exploit `jq` for extracting, shaping, and enhancing the JSON output from the MAAS CLI. By coupling `jq` with other command-line utilities, you gain a potent toolkit for dissecting and analysing API outputs.

>Pro-tip: If you need more `jq` skills, try working through the [jq manual](https://jqlang.github.io/jq/manual/), which is freely available online.
