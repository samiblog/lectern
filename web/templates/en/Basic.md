---
marp: true
title: Basic
paginate: true
---

<!-- template: Title -->

<!-- _class: lead -->
<!-- _paginate: false -->

# {{title}}

Write the subtitle

---

<!-- template: Section -->

<!-- _class: lead -->

## Write the section title

Write what this section covers

---

<!-- template: Title and text -->

## State the conclusion in one sentence

- Write the first point
- Write the second point
- Write the third point

---

<!-- template: Text and box -->

<!-- layout: two-left -->

## State the conclusion in one sentence

::: a
- Write the first reason
- Write the second reason
- Write the third reason
:::

::: b card accent
### Key point

Write the most important thing
:::

---

<!-- template: Text and chart -->

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

---

<!-- template: Chart and boxes -->

<!-- layout: left-stack -->

## Say what the chart shows

::: a
```vega-lite
{
  "width": "container",
  "data": {"values": [{"item": "A", "value": 3}, {"item": "B", "value": 5}, {"item": "C", "value": 4}, {"item": "D", "value": 6}]},
  "mark": "bar",
  "encoding": {
    "x": {"field": "item", "type": "nominal", "title": null, "axis": {"labelAngle": 0}},
    "y": {"field": "value", "type": "quantitative", "title": null}
  }
}
```
:::

::: b card
### How to read it

Write where to look in the chart
:::

::: c card accent
### Next step

Write what needs deciding
:::

---

<!-- template: Two columns -->

<!-- layout: two -->

## Compare the two and state the conclusion

::: a card
### First option

- Write the upside
- Write the downside
:::

::: b card
### Second option

- Write the upside
- Write the downside
:::

---

<!-- template: Three columns -->

<!-- layout: three -->

## Split into three and state the conclusion

::: a card
### First

Write the content
:::

::: b card
### Second

Write the content
:::

::: c card
### Third

Write the content
:::

---

<!-- template: Four boxes -->

<!-- layout: quad -->

## Split into four and state the conclusion

::: a card
### First

Write the content
:::

::: b card
### Second

Write the content
:::

::: c card
### Third

Write the content
:::

::: d card
### Fourth

Write the content
:::

---

<!-- template: Four numbers -->

<!-- layout: kpi -->

## State what the numbers say

::: a kpi
**0**
Label
:::

::: b kpi
**0**
Label
:::

::: c kpi
**0**
Label
:::

::: d kpi accent
**0**
Label
:::

::: e accent
Write how to read the numbers
:::

---

<!-- template: Table and note -->

<!-- layout: two-left -->

## State what the table says

::: a
| Item | Value | Note |
|---|---:|---|
| A | 0 | Text |
| B | 0 | Text |
| C | 0 | Text |
:::

::: b card accent
### How to read it

Write where to look in the table
:::

---

<!-- template: Title only -->

## Write the title
