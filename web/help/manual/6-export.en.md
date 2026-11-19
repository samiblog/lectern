# Export

> md documents go out as PDF, print, html or Word; Lectern slides as PDF, pptx or presentation html. Lectern writes one file, only when you choose to save.

```mermaid
flowchart LR
  Q{"For whom,<br>in what form?"}
  Q -->|"Paper · a file not to be edited"| P["PDF · print<br>Print on the tab bar"]
  Q -->|"One file by mail, read in a browser"| H["One html file<br>Save as html…"]
  Q -->|"The reader edits it in Word"| W["Word<br>Save as Word…"]
  Q -->|"Slides to PowerPoint"| X["pptx<br>Convert to pptx on the status bar"]
  Q -->|"Slides as a browser presentation"| I["Presentation html<br>Convert to html on the status bar"]
```

| Format | From | Where to open it | Result |
|---|---|---|---|
| PDF · print | md documents · Lectern slides | **Print** on the tab bar · right-click the body margin → **Save as PDF…** · **Print…** | The A4 report layout or a page layout — slides come out one per page |
| One html file | md documents | Right-click → **Save as html…** | One html file with the images · charts inside |
| Word | md documents | Right-click → **Save as Word…** | A docx to keep editing — it borrows a Word template |
| pptx | Lectern slides | **Convert to pptx** on the status bar | A new pptx next to the document |
| Presentation html | Lectern slides | **Convert to html** on the status bar | An impress.js presentation html next to the document |

PDF, html and Word are made in the same **Export** window by switching the format, and you pick where to save in the save dialog. pptx and presentation html never overwrite a file of the same name; they are made with a new name.

## Documents in this chapter

<!-- 하위 문서 -->
