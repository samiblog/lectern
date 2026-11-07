<!-- layout: two -->

## Say what the chart shows

::: a
- Write what changed
- Write why
- Write what to do next
:::

::: b
```vega-lite
{
  "width": "container",
  "data": {"values": [{"item": "A", "value": 3}, {"item": "B", "value": 5}, {"item": "C", "value": 4}]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "item", "type": "nominal", "title": null, "axis": {"labelAngle": 0}},
    "y": {"field": "value", "type": "quantitative", "title": null}
  }
}
```
:::
