# Architecture & Database Schema

## Decoupled Data Layer (`data/bim-database.json`)

The viewer loads structural BIM graph data from `data/bim-database.json` on startup or via the **Upload DB** file picker.

### JSON Schema

```json
{
  "projectName": "Hudson Point Tower (14F)",
  "nodes": [
    {
      "id": "col-B2-L01",
      "label": "C-01-L01",
      "type": "Instance",
      "level": 2,
      "parent": "stack-C01",
      "categoryParent": "cat-col",
      "floor": "L01",
      "floorNum": 1,
      "ratedStrength": 85,
      "strengthLabel": "85 MPa Composite",
      "axialLoadKn": 24100,
      "utilization": 0.76,
      "r": 8.5,
      "color": "#10b981",
      "pos3d": [-30.0, 6.0, -30.0],
      "size3d": [2.67, 12.0, 2.67],
      "shape3d": "box",
      "documents": [
        {
          "id": "doc-col-B2-L01",
          "title": "L01 — C-01 (Grid B2) L01 Structural Sheet & Calc",
          "type": "Calculation & Drawing (PDF)",
          "code": "ACI 318-19 / ASCE 7-22",
          "rev": "Rev B",
          "pages": 4,
          "date": "2026-10-21",
          "summary": "Column Stack C-01 floor-to-floor segment at L01."
        }
      ]
    }
  ],
  "links": [
    { "source": "stack-C01", "target": "col-B2-L01" }
  ]
}
```
