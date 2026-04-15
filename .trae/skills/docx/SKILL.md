---
name: "docx"
description: "DOCX creation, editing, and analysis. Invoke when creating or editing Word documents, handling tracked changes, or converting documents."
---

# DOCX Processing Guide

## Overview

A .docx file is a ZIP archive containing XML files.

## Quick Reference

| Task | Approach |
|------|----------|
| Read/analyze content | `pandoc` or unpack for raw XML |
| Create new document | Use `docx-js` |
| Edit existing document | Unpack → edit XML → repack |

## Creating New Documents

Generate .docx files with JavaScript:

```javascript
const { Document, Packer, Paragraph, TextRun } = require('docx');

const doc = new Document({
  sections: [{
    children: [
      new Paragraph({
        children: [new TextRun("Hello World!")]
      })
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

## Critical Rules

- **Set page size explicitly** - docx-js defaults to A4; use US Letter (12240 x 15840 DXA)
- **Never use unicode bullets** - use `LevelFormat.BULLET` with numbering config
- **PageBreak must be in Paragraph** - standalone creates invalid XML
- **Tables need dual widths** - `columnWidths` AND cell `width`, both must match
- **Always use WidthType.DXA** - never PERCENTAGE (breaks in Google Docs)

## Tables

```javascript
new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [4680, 4680], // Must sum to table width
  rows: [
    new TableRow({
      children: [
        new TableCell({
          width: { size: 4680, type: WidthType.DXA },
          children: [new Paragraph("Cell")]
        })
      ]
    })
  ]
})
```

## Lists

```javascript
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•" }] }
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] })
    ]
  }]
});
```

## Editing Existing Documents

### Step 1: Unpack
```bash
python scripts/office/unpack.py document.docx unpacked/
```

### Step 2: Edit XML
Edit files in `unpacked/word/`

### Step 3: Pack
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```

## Converting

### .doc to .docx
```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### Extract text
```bash
pandoc --track-changes=all document.docx -o output.md
```
