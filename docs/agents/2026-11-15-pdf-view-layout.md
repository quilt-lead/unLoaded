# PDF Calcs view: give the page the room

- **Status**: done (not yet seen in a browser: no Playwright/Puppeteer in the repo)
- **Branch**: cs/dev
- **Files owned**: `src/components/DocumentBrowser.tsx`, the `FilterBar` render guard in `src/App.tsx`

## What changed and why

The user's reason for being on this tab is the PDF page, so everything else was moved to make room for it:

- **The global FilterBar is not rendered on the `docs` view.** Its search, type, level and trace controls, the mapping legend and the element count act only on the graphs and 3D. `DocumentBrowser` never received `filters`, so nothing on the page changed when you used them. The PDF view keeps its own calc search.
- **The "85 calc documents" page header is gone.** The package name, calc count and search moved to the top of the calc list.
- **The calc list is a fixed sidebar**: 300px wide, or 340px at the `xl` breakpoint and up. It replaces the old 4/12 or 5/12 grid column. Card titles wrap to 3 lines and the subline to 2 lines, instead of being cut to one line. On screens narrower than 900px the list stacks above the page, capped at 42vh.
- **The list can be hidden** (the panel icon in the list header). When it is hidden, a show button appears at the left of the calc toolbar.
- **The calc header card and the PdfPage caption bar are now one toolbar row.** It holds the PDF/DEMO badge, the title, the chips, the region and page stepper, a caption for the highlighted evidence, and the locate buttons. Below `xl` the locate buttons show only their icons. `PdfPage` is rendered `bare`.
- **The calc dependencies and linked elements are a collapsible footer.** Its summary line shows both counts. It is open by default and capped at 9rem (`max-h-36`).
- **The list and footer toggles are remembered** in localStorage under `calcmap.docs.listOpen` and `calcmap.docs.detailsOpen`. Every read and write is wrapped in try/catch.
- **The padding and card frames around the page are removed**, so the page stage runs edge to edge.

## Open / next

- Check it in a real browser. The parts to look at: the toolbar wrapping at about 1024px, and the PdfPage tool buttons (top right) against long titles. The tools are now at the very top of the stage instead of under a caption bar.
- The list width could be made draggable, reusing the dock resize handle pattern from `App.tsx`, if the 300px/340px sizes don't suit.
